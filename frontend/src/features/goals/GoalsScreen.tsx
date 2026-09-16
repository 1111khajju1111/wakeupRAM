import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { goalsApi } from "../../services/domainApi";
import type { Goal } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

export function GoalsScreen() {
  const { t } = useTranslation();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      setGoals(await goalsApi.list("active"));
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onChanged = () => void load();
    window.addEventListener("wakeupram:goals-changed", onChanged);
    return () => window.removeEventListener("wakeupram:goals-changed", onChanged);
  }, [load]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) return;

    setSaving(true);
    try {
      const created = await goalsApi.create({
        title: cleanTitle,
        description: description.trim() || undefined,
        category: category.trim() || undefined,
        target_date: targetDate || undefined,
      });
      setGoals((current) => [created, ...current]);
      setTitle("");
      setDescription("");
      setCategory("");
      setTargetDate("");
      window.dispatchEvent(new Event("wakeupram:goals-changed"));
    } catch {
      setLoadState("error");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatus(goal: Goal, status: "completed" | "abandoned") {
    setUpdatingId(goal.id);
    try {
      await goalsApi.update(goal.id, { status });
      setGoals((current) => current.filter((item) => item.id !== goal.id));
      window.dispatchEvent(new Event("wakeupram:goals-changed"));
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <main className="goals-screen">
      <div className="goals-screen__heading">
        <div>
          <span className="section-label">03 / GOALS</span>
          <h1>{t("nav.goals")}</h1>
        </div>
        <span className="goals-screen__count">{goals.length.toString().padStart(2, "0")}</span>
      </div>

      <form className="goals-form" onSubmit={handleCreate}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t("goals.titlePlaceholder")} aria-label={t("goals.titlePlaceholder")} />
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("goals.descriptionPlaceholder")} aria-label={t("goals.descriptionPlaceholder")} />
        <div className="goals-form__row">
          <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder={t("goals.categoryPlaceholder")} aria-label={t("goals.categoryPlaceholder")} />
          <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} aria-label={t("goals.targetDate")} />
        </div>
        <button type="submit" disabled={saving || !title.trim()}>{saving ? t("common.loading") : t("goals.create")}</button>
      </form>

      {loadState === "loading" && <p className="empty-state">{t("common.loading")}</p>}
      {loadState === "error" && (
        <div className="empty-state empty-state--error">
          <p>{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void load()}>{t("common.retry")}</button>
        </div>
      )}
      {loadState === "loaded" && goals.length === 0 && <p className="empty-state">{t("goals.empty")}</p>}

      {goals.length > 0 && (
        <ul className="goal-list">
          {goals.map((goal) => (
            <li key={goal.id} className="goal-list__item">
              <div className="goal-list__main">
                <span className="card-index">{goal.category || t("goals.active")}</span>
                <h2>{goal.title}</h2>
                {goal.description && <p>{goal.description}</p>}
                {goal.target_date && <time dateTime={goal.target_date}>{goal.target_date}</time>}
              </div>
              <div className="goal-list__actions">
                <button type="button" disabled={updatingId === goal.id} onClick={() => void handleStatus(goal, "completed")}>{t("goals.complete")}</button>
                <button type="button" disabled={updatingId === goal.id} onClick={() => void handleStatus(goal, "abandoned")}>{t("goals.abandon")}</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
