import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.group import GroupMember
from app.models.expense import Expense, ExpenseSplit
from app.ai.langchain_qa import ask_expense_question, categorize_expense
from app.ai.langgraph_agent import run_agent

router = APIRouter(prefix="/ai", tags=["AI"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    group_id: uuid.UUID
    question: str


class CategorizeRequest(BaseModel):
    description: str


def handle_ai_error(e: Exception):
    logger.error(f"AI call failed: {type(e).__name__}: {e}", exc_info=True)
    error_str = str(e)
    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
        raise HTTPException(
            status_code=429,
            detail="AI service is temporarily unavailable due to rate limits. Please try again later."
        )
    raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")


async def assert_member(group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession):
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")


@router.post("/ask")
@limiter.limit("10/minute")
async def ask_question(
    request: Request,
    payload: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(payload.group_id, current_user.id, db)

    expenses_result = await db.execute(
        select(Expense).where(
            Expense.group_id == payload.group_id,
            Expense.is_deleted == False,
        )
    )
    expenses = expenses_result.scalars().all()

    if not expenses:
        return {"answer": "No expenses found in this group yet."}

    expense_data = "\n".join([
        f"- {e.description}: Rs.{e.total_amount} (split: {e.split_type}, paid by: {e.paid_by})"
        for e in expenses
    ])

    splits_result = await db.execute(
        select(ExpenseSplit)
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .where(
            Expense.group_id == payload.group_id,
            Expense.is_deleted == False,
        )
    )
    splits = splits_result.scalars().all()
    splits_data = "\n".join([
        f"  User {s.user_id} owes Rs.{s.amount_owed} (settled: {s.is_settled})"
        for s in splits
    ])

    full_data = f"Expenses:\n{expense_data}\n\nSplits:\n{splits_data}"

    try:
        answer = await ask_expense_question(full_data, payload.question)
        return {"answer": answer}
    except Exception as e:
        handle_ai_error(e)


@router.post("/categorize")
@limiter.limit("20/minute")
async def categorize(
    request: Request,
    payload: CategorizeRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        category = await categorize_expense(payload.description)
        return {"description": payload.description, "category": category}
    except Exception as e:
        handle_ai_error(e)


@router.post("/agent/{group_id}")
@limiter.limit("5/minute")
async def run_group_agent(
    request: Request,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(group_id, current_user.id, db)

    expenses_result = await db.execute(
        select(Expense).where(
            Expense.group_id == group_id,
            Expense.is_deleted == False,
        )
    )
    expenses = expenses_result.scalars().all()
    expenses_list = [
        {
            "id": str(e.id),
            "description": e.description,
            "total_amount": e.total_amount,
            "paid_by": str(e.paid_by),
            "split_type": e.split_type,
        }
        for e in expenses
    ]

    members_result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    member_ids = [m.user_id for m in members_result.scalars().all()]
    balances = {uid: 0.0 for uid in member_ids}

    for expense in expenses:
        if expense.paid_by in balances:
            balances[expense.paid_by] += expense.total_amount

    splits_result = await db.execute(
        select(ExpenseSplit)
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .where(
            Expense.group_id == group_id,
            Expense.is_deleted == False,
            ExpenseSplit.is_settled == False,
        )
    )
    for split in splits_result.scalars().all():
        if split.user_id in balances:
            balances[split.user_id] -= split.amount_owed

    balances_str_keys = {str(k): v for k, v in balances.items()}

    try:
        result = await run_agent(str(group_id), expenses_list, balances_str_keys)
        return {
            "group_id": str(group_id),
            "summary": result["summary"],
            "reminders": result["reminders"],
            "final_report": result["final_report"],
        }
    except Exception as e:
        handle_ai_error(e)