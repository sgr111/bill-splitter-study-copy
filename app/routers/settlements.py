import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.expense import ExpenseSplit, Expense
from app.models.settlement import Settlement
from app.schemas.settlement import SettlementCreate, SettlementResponse, SettleUpSuggestion
from app.services.settle_service import calculate_minimum_settlements

router = APIRouter(tags=["Settlements"])


async def assert_member(group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession):
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")


@router.post("/settlements", response_model=SettlementResponse, status_code=201)
async def record_settlement(
    payload: SettlementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(payload.group_id, current_user.id, db)
    settlement = Settlement(
        group_id=payload.group_id,
        paid_by=current_user.id,
        paid_to=payload.paid_to,
        amount=payload.amount,
    )
    db.add(settlement)
    await db.commit()
    await db.refresh(settlement)
    return settlement


@router.get("/settlements/{group_id}", response_model=list[SettlementResponse])
async def list_settlements(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(group_id, current_user.id, db)
    result = await db.execute(
        select(Settlement).where(Settlement.group_id == group_id)
    )
    return result.scalars().all()


@router.get("/settle-up/{group_id}", response_model=list[SettleUpSuggestion])
async def settle_up(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(group_id, current_user.id, db)

    members_result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    member_ids = [m.user_id for m in members_result.scalars().all()]

    balances = {uid: 0.0 for uid in member_ids}

    expenses_result = await db.execute(
        select(Expense).where(Expense.group_id == group_id, Expense.is_deleted == False)
    )
    for expense in expenses_result.scalars().all():
        if expense.paid_by in balances:
            balances[expense.paid_by] += expense.total_amount

    splits_result = await db.execute(
        select(ExpenseSplit)
        .join(Expense, ExpenseSplit.expense_id == Expense.id)
        .where(Expense.group_id == group_id, Expense.is_deleted == False, ExpenseSplit.is_settled == False)
    )
    for split in splits_result.scalars().all():
        if split.user_id in balances:
            balances[split.user_id] -= split.amount_owed

    return calculate_minimum_settlements(balances)