import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.group import GroupMember
from app.models.expense import Expense, ExpenseSplit
from app.schemas.expense import ExpenseSplitResponse

router = APIRouter(prefix="/splits", tags=["Splits"])


@router.get("/{expense_id}", response_model=list[ExpenseSplitResponse])
async def get_splits(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense_result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.is_deleted == False)
    )
    expense = expense_result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == expense.group_id,
            GroupMember.user_id == current_user.id,
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")

    result = await db.execute(
        select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)
    )
    return result.scalars().all()


@router.post("/{split_id}/settle", response_model=ExpenseSplitResponse)
async def settle_split(
    split_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExpenseSplit).where(ExpenseSplit.id == split_id)
    )
    split = result.scalar_one_or_none()
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    if split.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only settle your own split")
    split.is_settled = True
    await db.commit()
    await db.refresh(split)
    return split