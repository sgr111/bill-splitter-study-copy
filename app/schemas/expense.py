import uuid
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Literal, Optional


class SplitInput(BaseModel):
    user_id: uuid.UUID
    amount_owed: Optional[float] = None
    percentage: Optional[float] = None


class ExpenseCreate(BaseModel):
    group_id: uuid.UUID
    description: str
    total_amount: float
    split_type: Literal["equal", "unequal", "percentage"]
    splits: Optional[list[SplitInput]] = None

    @field_validator("total_amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("total_amount must be positive")
        return v


class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    total_amount: Optional[float] = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    paid_by: uuid.UUID
    description: str
    total_amount: float
    split_type: str
    created_at: datetime
    is_deleted: bool

    model_config = {"from_attributes": True}


class ExpenseSplitResponse(BaseModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    user_id: uuid.UUID
    amount_owed: float
    is_settled: bool

    model_config = {"from_attributes": True}