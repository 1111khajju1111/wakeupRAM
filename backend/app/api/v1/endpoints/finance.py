import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.finance import (
    AffordabilityRequest,
    AffordabilityResult,
    BudgetRead,
    BudgetSet,
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    FinancialGoalCreate,
    FinancialGoalRead,
    FinancialGoalUpdate,
    FinanceSummary,
    IncomeCreate,
    IncomeRead,
    IncomeUpdate,
)
from app.services import finance_service

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/summary", response_model=FinanceSummary)
def get_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FinanceSummary:
    return finance_service.get_summary(db, current_user.id, date.today())


@router.post("/affordability", response_model=AffordabilityResult)
def check_affordability(
    payload: AffordabilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AffordabilityResult:
    return finance_service.check_affordability(db, current_user.id, date.today(), payload)


# ---- Income ----


@router.post("/income", response_model=IncomeRead, status_code=status.HTTP_201_CREATED)
def create_income(
    payload: IncomeCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> IncomeRead:
    return finance_service.create_income(db, current_user.id, payload)


@router.get("/income", response_model=list[IncomeRead])
def list_income(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IncomeRead]:
    return finance_service.list_income(db, current_user.id, start=start, end=end)


@router.patch("/income/{income_id}", response_model=IncomeRead)
def update_income(
    income_id: uuid.UUID,
    payload: IncomeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IncomeRead:
    try:
        return finance_service.update_income(db, current_user.id, income_id, payload)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/income/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(
    income_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        finance_service.delete_income(db, current_user.id, income_id)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Expenses ----


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ExpenseRead:
    return finance_service.create_expense(db, current_user.id, payload)


@router.get("/expenses", response_model=list[ExpenseRead])
def list_expenses(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ExpenseRead]:
    return finance_service.list_expenses(db, current_user.id, start=start, end=end, category=category)


@router.patch("/expenses/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExpenseRead:
    try:
        return finance_service.update_expense(db, current_user.id, expense_id, payload)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        finance_service.delete_expense(db, current_user.id, expense_id)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Budgets ----


@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_200_OK)
def set_budget(
    payload: BudgetSet, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BudgetRead:
    """200, not 201: upsert by category, same reasoning as health.log_sleep."""
    return finance_service.set_budget(db, current_user.id, payload)


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[BudgetRead]:
    return finance_service.list_budgets(db, current_user.id)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        finance_service.delete_budget(db, current_user.id, budget_id)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---- Financial goals ----


@router.post("/goals", response_model=FinancialGoalRead, status_code=status.HTTP_201_CREATED)
def create_financial_goal(
    payload: FinancialGoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialGoalRead:
    return finance_service.create_financial_goal(db, current_user.id, payload)


@router.get("/goals", response_model=list[FinancialGoalRead])
def list_financial_goals(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FinancialGoalRead]:
    return finance_service.list_financial_goals(db, current_user.id, status=status_filter)


@router.patch("/goals/{goal_id}", response_model=FinancialGoalRead)
def update_financial_goal(
    goal_id: uuid.UUID,
    payload: FinancialGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FinancialGoalRead:
    try:
        return finance_service.update_financial_goal(db, current_user.id, goal_id, payload)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_financial_goal(
    goal_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    try:
        finance_service.delete_financial_goal(db, current_user.id, goal_id)
    except finance_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
