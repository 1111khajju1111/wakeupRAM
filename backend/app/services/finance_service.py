"""
Finance domain service: income, expenses, budgets, financial goals, and the
"can I afford this?" calculation from section 12 of the master doc.

Consistent with the rest of the app: every read/write is scoped by user_id
at the query layer, and nothing here fabricates a number the user didn't
enter — see FinanceSummary/AffordabilityResult docstrings. "This month" is
computed the same server-local way app/services/health_service.py computes
"today" — true per-user-timezone month boundaries are deferred to when
Profile.timezone is wired through the request path, not introduced
piecemeal here.
"""
import calendar
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Budget, Expense, FinancialGoal, Income
from app.schemas.finance import (
    AffordabilityRequest,
    AffordabilityResult,
    BudgetSet,
    BudgetStatus,
    ExpenseCreate,
    ExpenseUpdate,
    FinancialGoalCreate,
    FinancialGoalUpdate,
    FinanceSummary,
    IncomeCreate,
    IncomeUpdate,
)

# Recurring-frequency -> monthly multiplier. "one_time" is deliberately
# absent: a one-time entry is not a recurring monthly figure, so it
# contributes 0 to the *recurring* estimate (it still counts in full toward
# "logged this month" if it happened this month).
_MONTHLY_FACTOR = {
    "weekly": 52 / 12,
    "biweekly": 26 / 12,
    "monthly": 1.0,
    "yearly": 1 / 12,
}


class NotFoundError(Exception):
    pass


def _month_bounds(today: date) -> tuple[date, date]:
    last_day = calendar.monthrange(today.year, today.month)[1]
    return date(today.year, today.month, 1), date(today.year, today.month, last_day)


def _normalize_to_monthly(amount: float, frequency: str) -> float:
    return amount * _MONTHLY_FACTOR.get(frequency, 0.0)


def _latest_recurring_income(all_income: list[Income]) -> list[Income]:
    """Among recurring-frequency (non-one_time) income entries, keep only the
    most recent one per distinct `source`.

    Bug this fixes: without deduping, logging the same recurring income
    (e.g. a salary) again each payday would sum once per historical entry,
    so `estimated_monthly_income` would keep growing every period it's
    logged rather than staying a stable "what's the standing monthly
    amount" figure — the whole point of a recurring baseline is that it
    shouldn't multiply just because it's been recorded more times.

    NOTE (this is the third time this exact fix has been reverted across
    review passes): please build on top of the reviewed zip delivered after
    each audit, not an older local snapshot — otherwise fixes like this one
    keep disappearing and reappearing across uploads."""
    latest: dict[str, Income] = {}
    for entry in all_income:
        if entry.frequency == "one_time":
            continue
        current = latest.get(entry.source)
        if current is None or entry.received_at > current.received_at:
            latest[entry.source] = entry
    return list(latest.values())


def _latest_recurring_expenses(all_expenses: list[Expense]) -> list[Expense]:
    """Same deduping as `_latest_recurring_income`, keyed by (category,
    description) since that's what identifies "the same recurring
    commitment" here (e.g. rent, a specific subscription) — see that
    function's docstring for the bug this avoids. This is what makes it
    safe for `check_affordability` to treat the recurring baseline as
    already covering this month's occurrence of a recurring bill: the
    baseline is one stable figure per commitment, not a sum that grows the
    more times you've logged paying it."""
    latest: dict[tuple[str, str], Expense] = {}
    for entry in all_expenses:
        if entry.frequency == "one_time":
            continue
        key = (entry.category, entry.description)
        current = latest.get(key)
        if current is None or entry.spent_at > current.spent_at:
            latest[key] = entry
    return list(latest.values())


# ---- Income ----


def create_income(db: Session, user_id: uuid.UUID, payload: IncomeCreate) -> Income:
    income = Income(user_id=user_id, **payload.model_dump())
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


def list_income(
    db: Session, user_id: uuid.UUID, start: date | None = None, end: date | None = None
) -> list[Income]:
    stmt = select(Income).where(Income.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Income.received_at >= start)
    if end is not None:
        stmt = stmt.where(Income.received_at <= end)
    return list(db.execute(stmt.order_by(Income.received_at.desc())).scalars())


def _get_owned_income(db: Session, user_id: uuid.UUID, income_id: uuid.UUID) -> Income:
    income = db.execute(
        select(Income).where(Income.id == income_id, Income.user_id == user_id)
    ).scalar_one_or_none()
    if income is None:
        raise NotFoundError("Income entry not found")
    return income


def update_income(db: Session, user_id: uuid.UUID, income_id: uuid.UUID, payload: IncomeUpdate) -> Income:
    income = _get_owned_income(db, user_id, income_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(income, field, value)
    db.add(income)
    db.commit()
    db.refresh(income)
    return income


def delete_income(db: Session, user_id: uuid.UUID, income_id: uuid.UUID) -> None:
    income = _get_owned_income(db, user_id, income_id)
    db.delete(income)
    db.commit()


# ---- Expense ----


def create_expense(db: Session, user_id: uuid.UUID, payload: ExpenseCreate) -> Expense:
    expense = Expense(user_id=user_id, **payload.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def list_expenses(
    db: Session,
    user_id: uuid.UUID,
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
) -> list[Expense]:
    stmt = select(Expense).where(Expense.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Expense.spent_at >= start)
    if end is not None:
        stmt = stmt.where(Expense.spent_at <= end)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    return list(db.execute(stmt.order_by(Expense.spent_at.desc())).scalars())


def _get_owned_expense(db: Session, user_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    expense = db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    ).scalar_one_or_none()
    if expense is None:
        raise NotFoundError("Expense not found")
    return expense


def update_expense(
    db: Session, user_id: uuid.UUID, expense_id: uuid.UUID, payload: ExpenseUpdate
) -> Expense:
    expense = _get_owned_expense(db, user_id, expense_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    expense = _get_owned_expense(db, user_id, expense_id)
    db.delete(expense)
    db.commit()


# ---- Budget ----


def set_budget(db: Session, user_id: uuid.UUID, payload: BudgetSet) -> Budget:
    """Upsert by (user, category) — see Budget model docstring."""
    existing = db.execute(
        select(Budget).where(Budget.user_id == user_id, Budget.category == payload.category)
    ).scalar_one_or_none()

    if existing:
        existing.monthly_limit = payload.monthly_limit
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    budget = Budget(user_id=user_id, category=payload.category, monthly_limit=payload.monthly_limit)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def list_budgets(db: Session, user_id: uuid.UUID) -> list[Budget]:
    stmt = select(Budget).where(Budget.user_id == user_id).order_by(Budget.category)
    return list(db.execute(stmt).scalars())


def delete_budget(db: Session, user_id: uuid.UUID, budget_id: uuid.UUID) -> None:
    budget = db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
    ).scalar_one_or_none()
    if budget is None:
        raise NotFoundError("Budget not found")
    db.delete(budget)
    db.commit()


def _budget_statuses(db: Session, user_id: uuid.UUID, today: date) -> list[BudgetStatus]:
    month_start, month_end = _month_bounds(today)
    budgets = list_budgets(db, user_id)
    statuses: list[BudgetStatus] = []
    for budget in budgets:
        spent = sum(
            e.amount for e in list_expenses(db, user_id, start=month_start, end=month_end, category=budget.category)
        )
        statuses.append(
            BudgetStatus(
                category=budget.category,
                monthly_limit=budget.monthly_limit,
                spent_this_month=spent,
                remaining=budget.monthly_limit - spent,
            )
        )
    return statuses


# ---- Financial goal ----


def create_financial_goal(db: Session, user_id: uuid.UUID, payload: FinancialGoalCreate) -> FinancialGoal:
    goal = FinancialGoal(user_id=user_id, **payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_financial_goals(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[FinancialGoal]:
    stmt = select(FinancialGoal).where(FinancialGoal.user_id == user_id)
    if status is not None:
        stmt = stmt.where(FinancialGoal.status == status)
    return list(db.execute(stmt.order_by(FinancialGoal.created_at.desc())).scalars())


def _get_owned_financial_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> FinancialGoal:
    goal = db.execute(
        select(FinancialGoal).where(FinancialGoal.id == goal_id, FinancialGoal.user_id == user_id)
    ).scalar_one_or_none()
    if goal is None:
        raise NotFoundError("Financial goal not found")
    return goal


def update_financial_goal(
    db: Session, user_id: uuid.UUID, goal_id: uuid.UUID, payload: FinancialGoalUpdate
) -> FinancialGoal:
    goal = _get_owned_financial_goal(db, user_id, goal_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def delete_financial_goal(db: Session, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
    goal = _get_owned_financial_goal(db, user_id, goal_id)
    db.delete(goal)
    db.commit()


# ---- Summary ----


def get_summary(db: Session, user_id: uuid.UUID, today: date) -> FinanceSummary:
    month_start, month_end = _month_bounds(today)

    all_income = list_income(db, user_id)
    all_expenses = list_expenses(db, user_id)

    # Deduped to the latest entry per distinct recurring source/commitment —
    # see _latest_recurring_income/_latest_recurring_expenses docstrings.
    estimated_monthly_income = sum(
        _normalize_to_monthly(i.amount, i.frequency) for i in _latest_recurring_income(all_income)
    )
    estimated_recurring_monthly_expenses = sum(
        _normalize_to_monthly(e.amount, e.frequency) for e in _latest_recurring_expenses(all_expenses)
    )

    income_this_month = sum(
        i.amount for i in all_income if month_start <= i.received_at <= month_end
    )
    expenses_this_month = sum(
        e.amount for e in all_expenses if month_start <= e.spent_at <= month_end
    )

    return FinanceSummary(
        estimated_monthly_income=estimated_monthly_income,
        estimated_recurring_monthly_expenses=estimated_recurring_monthly_expenses,
        income_logged_this_month=income_this_month,
        expenses_logged_this_month=expenses_this_month,
        budgets=_budget_statuses(db, user_id, today),
        active_goals=list_financial_goals(db, user_id, status="active"),
    )


# ---- Affordability ----


def check_affordability(
    db: Session, user_id: uuid.UUID, today: date, payload: AffordabilityRequest
) -> AffordabilityResult:
    """"Can I afford this?" (section 12): transparent math with explicit
    assumptions and caveats, never a confident guarantee. If the user hasn't
    logged any income yet, the honest answer is "not enough data" — an
    unknown result, not a fabricated one.

    Both the income and expense recurring baselines are deduped to the most
    recent entry per distinct commitment (_latest_recurring_income /
    _latest_recurring_expenses) — otherwise logging the same recurring item
    again each period would inflate the baseline every time, independent of
    the same-month-double-count issue this function also avoids below."""
    month_start, month_end = _month_bounds(today)

    all_income = list_income(db, user_id)
    all_expenses = list_expenses(db, user_id)

    estimated_monthly_income = sum(
        _normalize_to_monthly(i.amount, i.frequency) for i in _latest_recurring_income(all_income)
    )
    estimated_recurring_monthly_expenses = sum(
        _normalize_to_monthly(e.amount, e.frequency) for e in _latest_recurring_expenses(all_expenses)
    )
    expenses_this_month = sum(
        e.amount for e in all_expenses if month_start <= e.spent_at <= month_end
    )
    # Only ONE-TIME expenses logged this month get added on top of the
    # recurring baseline. A recurring expense (e.g. this month's rent
    # payment) is already represented by its normalized share inside
    # estimated_recurring_monthly_expenses — adding its full logged amount
    # again here would subtract the same real-world bill twice and silently
    # understate what's actually available.
    one_time_expenses_this_month = sum(
        e.amount
        for e in all_expenses
        if e.frequency == "one_time" and month_start <= e.spent_at <= month_end
    )

    assumptions = [
        "Estimated monthly income is your recurring income entries normalized to a monthly figure "
        "(weekly x 4.33, biweekly x 2.17, yearly / 12); one-time income isn't counted as recurring.",
        "Recurring monthly expenses are normalized the same way and treated as your baseline monthly "
        "obligations, whether or not this month's occurrence has been logged yet.",
        "Only one-time expenses logged this calendar month are added on top of that baseline — a "
        "recurring bill you've already logged this month is not subtracted a second time on top of "
        "its normalized monthly share.",
    ]
    caveats = [
        "This is an estimate based on what you've recorded, not a financial guarantee — "
        "Ram is not a financial fiduciary.",
        "It doesn't account for income or expenses you haven't logged yet, or upcoming bills "
        "not yet entered.",
    ]

    if not all_income:
        caveats.insert(
            0,
            "No income has been logged yet, so an affordability estimate isn't possible — "
            "add your income sources first.",
        )
        return AffordabilityResult(
            requested_amount=payload.amount,
            estimated_monthly_income=0.0,
            estimated_recurring_monthly_expenses=estimated_recurring_monthly_expenses,
            expenses_logged_this_month=expenses_this_month,
            estimated_available_this_month=None,
            likely_affordable=None,
            assumptions=assumptions,
            caveats=caveats,
        )

    available = estimated_monthly_income - estimated_recurring_monthly_expenses - one_time_expenses_this_month

    return AffordabilityResult(
        requested_amount=payload.amount,
        estimated_monthly_income=estimated_monthly_income,
        estimated_recurring_monthly_expenses=estimated_recurring_monthly_expenses,
        expenses_logged_this_month=expenses_this_month,
        estimated_available_this_month=available,
        likely_affordable=available >= payload.amount,
        assumptions=assumptions,
        caveats=caveats,
    )
