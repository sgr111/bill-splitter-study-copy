import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.group import GroupMember
from app.models.expense import Expense, ExpenseSplit
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.services.split_service import calculate_splits

router = APIRouter(prefix="/expenses", tags=["Expenses"])


async def assert_member(group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession):
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")


@router.post("", response_model=ExpenseResponse, status_code=201)
async def add_expense(
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(payload.group_id, current_user.id, db)

    members_result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == payload.group_id)
    )
    members = members_result.scalars().all()
    member_ids = [m.user_id for m in members]

    try:
        splits = calculate_splits(payload, member_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    expense = Expense(
        group_id=payload.group_id,
        paid_by=current_user.id,
        description=payload.description,
        total_amount=payload.total_amount,
        split_type=payload.split_type,
    )
    db.add(expense)
    await db.flush()

    for split in splits:
        db.add(ExpenseSplit(
            expense_id=expense.id,
            user_id=split["user_id"],
            amount_owed=split["amount_owed"],
        ))

    await db.commit()
    await db.refresh(expense)
    return expense


@router.get("/group/{group_id}", response_model=list[ExpenseResponse])
async def list_expenses(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_member(group_id, current_user.id, db)
    result = await db.execute(
        select(Expense).where(Expense.group_id == group_id, Expense.is_deleted == False)
    )
    return result.scalars().all()


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    await assert_member(expense.group_id, current_user.id, db)
    return expense


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    await assert_member(expense.group_id, current_user.id, db)
    if payload.description:
        expense.description = payload.description
    if payload.total_amount:
        expense.total_amount = payload.total_amount
    await db.commit()
    await db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.paid_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can delete this expense")
    expense.is_deleted = True
    await db.commit()