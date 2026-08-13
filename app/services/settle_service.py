import uuid
from app.schemas.settlement import SettleUpSuggestion


def calculate_minimum_settlements(balances: dict[uuid.UUID, float]) -> list[SettleUpSuggestion]:
    creditors = []
    debtors = []

    for user_id, balance in balances.items():
        if balance > 0.01:
            creditors.append([balance, user_id])
        elif balance < -0.01:
            debtors.append([balance, user_id])

    creditors.sort(reverse=True)
    debtors.sort()

    suggestions = []

    while creditors and debtors:
        credit_amount, creditor = creditors.pop(0)
        debt_amount, debtor = debtors.pop(0)

        settle_amount = round(min(credit_amount, abs(debt_amount)), 2)

        suggestions.append(SettleUpSuggestion(
            from_user=debtor,
            to_user=creditor,
            amount=settle_amount,
        ))

        remaining_credit = round(credit_amount - settle_amount, 2)
        remaining_debt = round(abs(debt_amount) - settle_amount, 2)

        if remaining_credit > 0.01:
            creditors.insert(0, [remaining_credit, creditor])
            creditors.sort(reverse=True)

        if remaining_debt > 0.01:
            debtors.insert(0, [-remaining_debt, debtor])
            debtors.sort()

    return suggestions