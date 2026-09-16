import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { financeApi } from "../../services/domainApi";
import type { AffordabilityResult, FinanceSummary } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Phase 6 scope: income/expense logging, budgets (upserted by category),
 * financial goals, and the "can I afford this?" calculation from section 12
 * of the master doc. Every number here is either something the user typed
 * or a clearly-labelled estimate derived from it — never a guess dressed up
 * as a fact (see AffordabilityResult.assumptions/caveats, always rendered
 * alongside the numbers, not hidden behind them).
 */
export function FinanceScreen() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const [incomeSource, setIncomeSource] = useState("");
  const [incomeAmount, setIncomeAmount] = useState("");
  const [incomeFrequency, setIncomeFrequency] = useState<
    "one_time" | "weekly" | "biweekly" | "monthly" | "yearly"
  >("monthly");
  const [isLoggingIncome, setIsLoggingIncome] = useState(false);

  const [expenseCategory, setExpenseCategory] = useState("");
  const [expenseDescription, setExpenseDescription] = useState("");
  const [expenseAmount, setExpenseAmount] = useState("");
  const [isLoggingExpense, setIsLoggingExpense] = useState(false);

  const [affordAmount, setAffordAmount] = useState("");
  const [affordResult, setAffordResult] = useState<AffordabilityResult | null>(null);
  const [isCheckingAfford, setIsCheckingAfford] = useState(false);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const data = await financeApi.summary();
      setSummary(data);
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleLogIncome(event: FormEvent) {
    event.preventDefault();
    const amount = Number(incomeAmount);
    if (!incomeSource.trim() || !amount || amount <= 0) return;
    setIsLoggingIncome(true);
    try {
      await financeApi.logIncome({
        source: incomeSource.trim(),
        amount,
        frequency: incomeFrequency,
        received_at: todayIso(),
      });
      setIncomeSource("");
      setIncomeAmount("");
      await load();
    } finally {
      setIsLoggingIncome(false);
    }
  }

  async function handleLogExpense(event: FormEvent) {
    event.preventDefault();
    const amount = Number(expenseAmount);
    if (!expenseCategory.trim() || !expenseDescription.trim() || !amount || amount <= 0) return;
    setIsLoggingExpense(true);
    try {
      await financeApi.logExpense({
        category: expenseCategory.trim(),
        description: expenseDescription.trim(),
        amount,
        spent_at: todayIso(),
      });
      setExpenseCategory("");
      setExpenseDescription("");
      setExpenseAmount("");
      await load();
    } finally {
      setIsLoggingExpense(false);
    }
  }

  async function handleCheckAffordability(event: FormEvent) {
    event.preventDefault();
    const amount = Number(affordAmount);
    if (!amount || amount <= 0) return;
    setIsCheckingAfford(true);
    try {
      const result = await financeApi.checkAffordability(amount);
      setAffordResult(result);
    } finally {
      setIsCheckingAfford(false);
    }
  }

  return (
    <main className="finance-screen">
      <h1>{t("nav.money")}</h1>

      {loadState === "loading" && <p className="empty-state">{t("common.loading")}</p>}

      {loadState === "error" && (
        <div className="empty-state empty-state--error">
          <p>{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void load()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {loadState === "loaded" && summary && (
        <>
          <section className="finance-screen__summary" aria-label={t("finance.summaryLabel")}>
            <div className="finance-stat">
              <span className="finance-stat__label">{t("finance.estimatedMonthlyIncome")}</span>
              <span className="finance-stat__value">{summary.estimated_monthly_income.toFixed(0)}</span>
            </div>
            <div className="finance-stat">
              <span className="finance-stat__label">{t("finance.estimatedRecurringExpenses")}</span>
              <span className="finance-stat__value">
                {summary.estimated_recurring_monthly_expenses.toFixed(0)}
              </span>
            </div>
            <div className="finance-stat">
              <span className="finance-stat__label">{t("finance.incomeLoggedThisMonth")}</span>
              <span className="finance-stat__value">{summary.income_logged_this_month.toFixed(0)}</span>
            </div>
            <div className="finance-stat">
              <span className="finance-stat__label">{t("finance.expensesLoggedThisMonth")}</span>
              <span className="finance-stat__value">{summary.expenses_logged_this_month.toFixed(0)}</span>
            </div>
          </section>

          {summary.budgets.length > 0 && (
            <section className="finance-screen__section" aria-label={t("finance.budgets")}>
              <h2>{t("finance.budgets")}</h2>
              <ul className="finance-screen__log-list">
                {summary.budgets.map((budget) => (
                  <li key={budget.category}>
                    <strong>{budget.category}</strong> — {budget.spent_this_month.toFixed(0)} /{" "}
                    {budget.monthly_limit.toFixed(0)} ({t("finance.remaining")}: {budget.remaining.toFixed(0)})
                  </li>
                ))}
              </ul>
            </section>
          )}

          {summary.active_goals.length > 0 && (
            <section className="finance-screen__section" aria-label={t("finance.goals")}>
              <h2>{t("finance.goals")}</h2>
              <ul className="finance-screen__log-list">
                {summary.active_goals.map((goal) => (
                  <li key={goal.id}>
                    <strong>{goal.title}</strong> — {goal.current_amount.toFixed(0)} /{" "}
                    {goal.target_amount.toFixed(0)}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="finance-screen__section" aria-label={t("finance.canIAfford")}>
            <h2>{t("finance.canIAfford")}</h2>
            <form onSubmit={handleCheckAffordability} className="finance-screen__form">
              <input
                type="number"
                min="0"
                step="1"
                value={affordAmount}
                onChange={(event) => setAffordAmount(event.target.value)}
                placeholder={t("finance.amountPlaceholder")}
              />
              <button type="submit" disabled={isCheckingAfford || !affordAmount}>
                {isCheckingAfford ? t("common.loading") : t("finance.check")}
              </button>
            </form>
            {affordResult && (
              <div className="finance-screen__afford-result">
                {affordResult.likely_affordable === null ? (
                  <p className="empty-state">{t("finance.notEnoughData")}</p>
                ) : (
                  <p className="finance-screen__afford-verdict">
                    {affordResult.likely_affordable
                      ? t("finance.likelyAffordable")
                      : t("finance.likelyNotAffordable")}{" "}
                    ({t("finance.estimatedAvailable")}: {affordResult.estimated_available_this_month?.toFixed(0)})
                  </p>
                )}
                <ul className="finance-screen__caveats">
                  {affordResult.caveats.map((caveat) => (
                    <li key={caveat}>{caveat}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section className="finance-screen__section" aria-label={t("finance.logIncome")}>
            <h2>{t("finance.logIncome")}</h2>
            <form onSubmit={handleLogIncome} className="finance-screen__form">
              <input
                type="text"
                value={incomeSource}
                onChange={(event) => setIncomeSource(event.target.value)}
                placeholder={t("finance.incomeSourcePlaceholder")}
              />
              <input
                type="number"
                min="0"
                step="1"
                value={incomeAmount}
                onChange={(event) => setIncomeAmount(event.target.value)}
                placeholder={t("finance.amountPlaceholder")}
              />
              <select
                value={incomeFrequency}
                onChange={(event) => setIncomeFrequency(event.target.value as typeof incomeFrequency)}
              >
                <option value="one_time">{t("finance.frequencyOneTime")}</option>
                <option value="weekly">{t("finance.frequencyWeekly")}</option>
                <option value="biweekly">{t("finance.frequencyBiweekly")}</option>
                <option value="monthly">{t("finance.frequencyMonthly")}</option>
                <option value="yearly">{t("finance.frequencyYearly")}</option>
              </select>
              <button type="submit" disabled={isLoggingIncome || !incomeSource.trim() || !incomeAmount}>
                {isLoggingIncome ? t("common.loading") : t("common.add")}
              </button>
            </form>
          </section>

          <section className="finance-screen__section" aria-label={t("finance.logExpense")}>
            <h2>{t("finance.logExpense")}</h2>
            <form onSubmit={handleLogExpense} className="finance-screen__form">
              <input
                type="text"
                value={expenseCategory}
                onChange={(event) => setExpenseCategory(event.target.value)}
                placeholder={t("finance.categoryPlaceholder")}
              />
              <input
                type="text"
                value={expenseDescription}
                onChange={(event) => setExpenseDescription(event.target.value)}
                placeholder={t("finance.expenseDescriptionPlaceholder")}
              />
              <input
                type="number"
                min="0"
                step="1"
                value={expenseAmount}
                onChange={(event) => setExpenseAmount(event.target.value)}
                placeholder={t("finance.amountPlaceholder")}
              />
              <button
                type="submit"
                disabled={
                  isLoggingExpense || !expenseCategory.trim() || !expenseDescription.trim() || !expenseAmount
                }
              >
                {isLoggingExpense ? t("common.loading") : t("common.add")}
              </button>
            </form>
          </section>
        </>
      )}
    </main>
  );
}
