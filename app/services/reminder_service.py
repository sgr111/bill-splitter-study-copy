import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from app.models.expense import ExpenseSplit, Expense
from app.config import settings

logger = logging.getLogger(__name__)


async def check_unsettled_splits():
    engine = create_async_engine(settings.DATABASE_URL, connect_args={"ssl": "require"})
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        result = await db.execute(
            select(ExpenseSplit, Expense)
            .join(Expense, ExpenseSplit.expense_id == Expense.id)
            .where(
                ExpenseSplit.is_settled == False,
                Expense.is_deleted == False,
                Expense.created_at < cutoff,
            )
        )
        rows = result.all()
        if rows:
            logger.info(f"REMINDER: {len(rows)} unsettled splits older than 3 days found.")
            for split, expense in rows:
                logger.info(
                    f"  User {split.user_id} owes Rs.{split.amount_owed} "
                    f"for expense '{expense.description}' (group: {expense.group_id})"
                )
        else:
            logger.info("REMINDER CHECK: No overdue unsettled splits found.")

    await engine.dispose()