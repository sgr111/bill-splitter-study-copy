import uuid
from app.schemas.expense import ExpenseCreate, SplitInput


def calculate_splits(payload: ExpenseCreate, member_ids: list[uuid.UUID]) -> list[dict]:
    splits = []

    if payload.split_type == "equal":
        per_person = round(payload.total_amount / len(member_ids), 2)
        for user_id in member_ids:
            splits.append({"user_id": user_id, "amount_owed": per_person})

    elif payload.split_type == "unequal":
        if not payload.splits:
            raise ValueError("splits required for unequal split_type")
        total = sum(s.amount_owed for s in payload.splits)
        if round(total, 2) != round(payload.total_amount, 2):
            raise ValueError(f"Split amounts {total} do not equal total_amount {payload.total_amount}")
        for s in payload.splits:
            splits.append({"user_id": s.user_id, "amount_owed": s.amount_owed})

    elif payload.split_type == "percentage":
        if not payload.splits:
            raise ValueError("splits required for percentage split_type")
        total_pct = sum(s.percentage for s in payload.splits)
        if round(total_pct, 2) != 100.0:
            raise ValueError(f"Percentages must add up to 100, got {total_pct}")
        for s in payload.splits:
            amount = round((s.percentage / 100) * payload.total_amount, 2)
            splits.append({"user_id": s.user_id, "amount_owed": amount})

    return splits