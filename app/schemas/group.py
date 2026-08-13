import uuid
from pydantic import BaseModel
from datetime import datetime


class GroupCreate(BaseModel):
    name: str


class GroupUpdate(BaseModel):
    name: str


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class GroupMemberResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime

    model_config = {"from_attributes": True}