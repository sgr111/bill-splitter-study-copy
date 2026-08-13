import uuid
from pydantic import BaseModel
from datetime import datetime


class InviteLinkResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    short_code: str
    expires_at: datetime
    is_active: bool
    invite_url: str

    model_config = {"from_attributes": True}


class InviteJoinResponse(BaseModel):
    message: str
    group_id: uuid.UUID