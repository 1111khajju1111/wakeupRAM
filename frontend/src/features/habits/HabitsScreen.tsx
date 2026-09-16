import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { habitsApi } from "../../services/domainApi";
import type { Habit } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

export function HabitsScreen() {
  const { t } = useTranslation();
  const [habits, setHabits] = useState<Habit[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [newTitle, setNewTitle] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const data = await habitsApi.list(true);
      setHabits(data);
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!newTitle.trim()) return;
    setIsSubmitting(true);
    try {
      await habitsApi.create({ title: newTitle.trim(), frequency: "daily" });
      setNewTitle("");
      await load();
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLog(habitId: string) {
    setHabits((prev) =>
      prev.map((h) =>
        h.id === habitId ? { ...h, completed_today: true, current_streak: h.current_streak + 1 } : h
      )
    );
    try {
      await habitsApi.logCompletion(habitId);
    } catch {
      await load();
    }
  }

  return (
    <main className="habits-screen">
      <h1>{t("nav.habits")}</h1>

      <form onSubmit={handleCreate} className="habits-screen__new-habit">
        <input
          type="text"
          value={newTitle}
          onChange={(event) => setNewTitle(event.target.value)}
          placeholder={t("habits.addHabitPlaceholder")}
        />
        <button type="submit" disabled={isSubmitting || !newTitle.trim()}>
          {isSubmitting ? t("common.loading") : t("common.add")}
        </button>
      </form>

      {loadState === "loading" && <p className="empty-state">{t("common.loading")}</p>}

      {loadState === "error" && (
        <div className="empty-state empty-state--error">
          <p>{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void load()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {loadState === "loaded" && habits.length === 0 && (
        <p className="empty-state">{t("habits.noHabitsYet")}</p>
      )}

      {loadState === "loaded" && habits.length > 0 && (
        <ul className="habit-list">
          {habits.map((habit) => (
            <li key={habit.id} className="habit-list__item">
              <div>
                <span>{habit.title}</span>
                <span className="habit-list__streak">{habit.current_streak}🔥</span>
              </div>
              <button
                type="button"
                disabled={habit.completed_today}
                onClick={() => handleLog(habit.id)}
              >
                {habit.completed_today ? t("habits.doneToday") : t("habits.markDone")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
