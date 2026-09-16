import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

FREQUENCY_PATTERN = "^(one_time|weekly|biweekly|monthly|yearly)$"
GOAL_TYPE_PATTERN = "^(savings|debt_payoff)$"
GOAL_STATUS_PATTERN = "^(active|completed|abandoned)$"


# ---- Income ----


class IncomeCreate(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0, le=100_000_000)
    frequency: str = Field(default="one_time", pattern=FREQUENCY_PATTERN)
    received_at: date
    notes: str | None = Field(default=None, max_length=1000)


class IncomeUpdate(BaseModel):
    source: str | None = Field(default=None, min_length=1, max_length=200)
    amount: float | None = Field(default=None, gt=0, le=100_000_000)
    frequency: str | None = Field(default=None, pattern=FREQUENCY_PATTERN)
    received_at: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class IncomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    amount: float
    frequency: str
    received_at: date
    notes: str | None


# ---- Expense ----


class ExpenseCreate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    amount: float = Field(gt=0, le=100_000_000)
    frequency: str = Field(default="one_time", pattern=FREQUENCY_PATTERN)
    spent_at: date
    notes: str | None = Field(default=None, max_length=1000)


class ExpenseUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    amount: float | None = Field(default=None, gt=0, le=100_000_000)
    frequency: str | None = Field(default=None, pattern=FREQUENCY_PATTERN)
    spent_at: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    description: str
    amount: float
    frequency: str
    spent_at: date
    notes: str | None


# ---- Budget ----


class BudgetSet(BaseModel):
    """Upserted by category — see app/models/finance.py Budget docstring."""

    category: str = Field(min_length=1, max_length=80)
    monthly_limit: float = Field(gt=0, le=100_000_000)


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    monthly_limit: float


class BudgetStatus(BaseModel):
    """A budget plus how much of it has actually been spent this month —
    both numbers come straight from logged expenses, never estimated."""

    category: str
    monthly_limit: float
    spent_this_month: float
    remaining: float


# ---- Financial goal ----


class FinancialGoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    goal_type: str = Field(default="savings", pattern=GOAL_TYPE_PATTERN)
    target_amount: float = Field(gt=0, le=1_000_000_000)
    current_amount: float = Field(default=0, ge=0, le=1_000_000_000)
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class FinancialGoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target_amount: float | None = Field(default=None, gt=0, le=1_000_000_000)
    current_amount: float | None = Field(default=None, ge=0, le=1_000_000_000)
    target_date: date | None = None
    status: str | None = Field(default=None, pattern=GOAL_STATUS_PATTERN)
    notes: str | None = Field(default=None, max_length=1000)


class FinancialGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    goal_type: str
    target_amount: float
    current_amount: float
    target_date: date | None
    status: str
    notes: str | None


# ---- Summary ----


class FinanceSummary(BaseModel):
    """Current-month finance snapshot. Every figure is derived from what the
    user actually logged — an empty list or a 0.0 total is the honest answer
    when nothing has been recorded, never a fabricated estimate."""

    estimated_monthly_income: float
    estimated_recurring_monthly_expenses: float
    income_logged_this_month: float
    expenses_logged_this_month: float
    budgets: list[BudgetStatus]
    active_goals: list[FinancialGoalRead]


# ---- Affordability ----


class AffordabilityRequest(BaseModel):
    amount: float = Field(gt=0, le=1_000_000_000)
    description: str | None = Field(default=None, max_length=500)


class AffordabilityResult(BaseModel):
    """Transparent, assumption-explicit output per section 12 — this shows
    its work and its uncertainty instead of returning a bare yes/no."""

    requested_amount: float
    estimated_monthly_income: float
    estimated_recurring_monthly_expenses: float
    expenses_logged_this_month: float
    # None when there isn't enough data (no income logged yet) to estimate
    # anything — an honest "unknown", never a guess dressed up as a number.
    estimated_available_this_month: float | None
    # None for the same reason: no verdict is safer than a false one.
    likely_affordable: bool | None
    assumptions: list[str]
    caveats: list[str]
