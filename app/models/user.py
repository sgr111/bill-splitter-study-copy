import uuid
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group_memberships: Mapped[list["GroupMember"]] = relationship(back_populates="user")
    created_groups: Mapped[list["Group"]] = relationship(back_populates="creator")
    expenses_paid: Mapped[list["Expense"]] = relationship(back_populates="paid_by_user")
    splits: Mapped[list["ExpenseSplit"]] = relationship(back_populates="user")
    settlements_made: Mapped[list["Settlement"]] = relationship(foreign_keys="Settlement.paid_by", back_populates="payer")
    settlements_received: Mapped[list["Settlement"]] = relationship(foreign_keys="Settlement.paid_to", back_populates="payee")