import uuid
from pydantic import BaseModel
from datetime import datetime


class SettlementCreate(BaseModel):
    group_id: uuid.UUID
    paid_to: uuid.UUID
    amount: float


class SettlementResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    paid_by: uuid.UUID
    paid_to: uuid.UUID
    amount: float
    settled_at: datetime

    model_config = {"from_attributes": True}


class SettleUpSuggestion(BaseModel):
    from_user: uuid.UUID
    to_user: uuid.UUID
    amount: float