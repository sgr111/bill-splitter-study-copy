import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.group import Group, GroupMember
from app.schemas.group import GroupCreate, GroupUpdate, GroupResponse, GroupMemberResponse

router = APIRouter(prefix="/groups", tags=["Groups"])


async def get_group_or_404(group_id: uuid.UUID, db: AsyncSession) -> Group:
    result = await db.execute(select(Group).where(Group.id == group_id, Group.is_active == True))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


async def assert_member(group_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession):
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = Group(name=payload.name, created_by=current_user.id)
    db.add(group)
    await db.flush()
    member = GroupMember(group_id=group.id, user_id=current_user.id)
    db.add(member)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == current_user.id, Group.is_active == True)
    )
    return result.scalars().all()


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = await get_group_or_404(group_id, db)
    await assert_member(group_id, current_user.id, db)
    return group


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = await get_group_or_404(group_id, db)
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only group admin can update")
    group.name = payload.name
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = await get_group_or_404(group_id, db)
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only group admin can delete")
    group.is_active = False
    await db.commit()


@router.post("/{group_id}/leave", status_code=200)
async def leave_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_group_or_404(group_id, db)
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=400, detail="You are not in this group")
    await db.delete(member)
    await db.commit()
    return {"message": "Left group successfully"}