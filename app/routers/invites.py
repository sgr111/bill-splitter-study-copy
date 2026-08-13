import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.invite import InviteLink
from app.schemas.invite import InviteLinkResponse, InviteJoinResponse
from app.services.invite_service import generate_short_code, get_expiry
from app.config import settings

router = APIRouter(tags=["Invites"])


def to_response(invite: InviteLink) -> dict:
    return {
        "id": invite.id,
        "group_id": invite.group_id,
        "short_code": invite.short_code,
        "expires_at": invite.expires_at,
        "is_active": invite.is_active,
        "invite_url": f"{settings.BASE_URL}/join/{invite.short_code}",
    }


@router.post("/invites/{group_id}", response_model=InviteLinkResponse, status_code=201)
async def generate_invite(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.is_active == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only group admin can generate invite links")

    invite = InviteLink(
        group_id=group_id,
        short_code=generate_short_code(),
        expires_at=get_expiry(),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return to_response(invite)


@router.get("/invites/{group_id}", response_model=list[InviteLinkResponse])
async def list_invites(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Group).where(Group.id == group_id, Group.is_active == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only group admin can view invite links")

    result = await db.execute(
        select(InviteLink).where(InviteLink.group_id == group_id, InviteLink.is_active == True)
    )
    invites = result.scalars().all()
    return [to_response(i) for i in invites]


@router.post("/join/{short_code}", response_model=InviteJoinResponse)
async def join_via_invite(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InviteLink).where(
            InviteLink.short_code == short_code,
            InviteLink.is_active == True,
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite link not found or inactive")

    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite link has expired")

    existing = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == invite.group_id,
            GroupMember.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You are already a member of this group")

    member = GroupMember(group_id=invite.group_id, user_id=current_user.id)
    db.add(member)
    await db.commit()
    return InviteJoinResponse(message="Successfully joined the group", group_id=invite.group_id)


@router.delete("/invites/{invite_id}", status_code=204)
async def deactivate_invite(
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InviteLink).where(InviteLink.id == invite_id)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite link not found")

    group_result = await db.execute(
        select(Group).where(Group.id == invite.group_id)
    )
    group = group_result.scalar_one_or_none()
    if group.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only group admin can deactivate invite links")

    invite.is_active = False
    await db.commit()