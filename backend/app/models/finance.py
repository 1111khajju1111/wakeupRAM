import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Table names follow section 19 of the master doc exactly: income, expenses,
# budgets, financial_goals. As with health.py (Phase 5), these four get one
# file because they share the finance domain, not because they share a
# schema — each has a genuinely different shape.
#
# "savings" and "debt" (section 12/19) are represented as FinancialGoal rows
# distinguished by `goal_type` (savings | debt_payoff) rather than as two
# more tables: a savings goal and a debt-payoff goal are the same shape
# (title, target_amount, current_amount, target_date, status) and differ
# only in which direction "progress" means — documented here rather than
# hidden, same as the Memory/lessons/behavior_patterns merge in Phase 3.
#
# Nothing here guesses or estimates a number the user didn't enter — see
# app/services/finance_service.py for how "can I afford this?" stays
# transparent about its assumptions instead of pretending to certainty
# (section 12, section 28 safety boundaries).

FREQUENCY_VALUES = ("one_time", "weekly", "biweekly", "monthly", "yearly")


class Income(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "income"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    # one_time | weekly | biweekly | monthly | yearly — "one_time" means this
    # entry is not treated as recurring when estimating monthly income (see
    # finance_service._normalize_to_monthly).
    frequency: Mapped[str] = mapped_column(String(20), default="one_time", nullable=False)
    received_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Income id={self.id} source={self.source!r} amount={self.amount}>"


class Expense(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "expenses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="one_time", nullable=False)
    spent_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Expense id={self.id} category={self.category!r} amount={self.amount}>"


class Budget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per (user, category). Setting a budget for a category the
    user already has a budget for updates that row rather than creating a
    duplicate — same upsert-by-natural-key pattern as SleepLog (Phase 5),
    for the same reason: a category should have exactly one current limit,
    not a history of superseded ones."""

    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budgets_user_id_category"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_limit: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Budget id={self.id} category={self.category!r} monthly_limit={self.monthly_limit}>"


class FinancialGoal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "financial_goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # savings | debt_payoff — see module docstring above.
    goal_type: Mapped[str] = mapped_column(String(20), default="savings", nullable=False)
    target_amount: Mapped[float] = mapped_column(Float, nullable=False)
    current_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # active | completed | abandoned — same vocabulary as Goal (Phase 2).
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FinancialGoal id={self.id} title={self.title!r} goal_type={self.goal_type}>"
