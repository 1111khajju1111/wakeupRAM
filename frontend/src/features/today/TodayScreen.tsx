import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { tasksApi } from "../../services/domainApi";
import type { Task } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function TodayScreen() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [makeMission, setMakeMission] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const data = await tasksApi.list({ due_date: todayIso() });
      setTasks(data);
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
      await tasksApi.create({
        title: newTitle.trim(),
        description: newDescription.trim() || undefined,
        due_date: todayIso(),
        is_daily_mission: makeMission,
      });
      setNewTitle("");
      setNewDescription("");
      setMakeMission(false);
      await load();
      window.dispatchEvent(new Event("wakeupram:today-changed"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAction(taskId: string, action: "completed" | "skipped") {
    setTasks((prev) =>
      prev.map((task) => (task.id === taskId ? { ...task, status: action } : task))
    );
    try {
      await tasksApi.logAction(taskId, action);
      window.dispatchEvent(new Event("wakeupram:today-changed"));
    } catch {
      await load();
    }
  }

  async function handleMissionChange(task: Task, isMission: boolean) {
    setUpdatingId(task.id);
    try {
      const updated = await tasksApi.update(task.id, { is_daily_mission: isMission });
      setTasks((prev) =>
        prev.map((item) =>
          item.id === updated.id
            ? updated
            : isMission && item.is_daily_mission
              ? { ...item, is_daily_mission: false }
              : item
        )
      );
      window.dispatchEvent(new Event("wakeupram:today-changed"));
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <main className="today-screen">
      <div className="today-screen__heading">
        <div>
          <span className="section-label">01 / TODAY</span>
          <h1>{t("nav.today")}</h1>
        </div>
        <span className="today-screen__date">{todayIso()}</span>
      </div>

      <form onSubmit={handleCreate} className="today-screen__new-task">
        <input
          type="text"
          value={newTitle}
          onChange={(event) => setNewTitle(event.target.value)}
          placeholder={t("today.addTaskPlaceholder")}
          aria-label={t("today.addTaskPlaceholder")}
        />
        <input
          type="text"
          value={newDescription}
          onChange={(event) => setNewDescription(event.target.value)}
          placeholder={t("today.descriptionPlaceholder")}
          aria-label={t("today.descriptionPlaceholder")}
        />
        <label className="today-screen__mission-toggle">
          <input
            type="checkbox"
            checked={makeMission}
            onChange={(event) => setMakeMission(event.target.checked)}
          />
          <span>{t("today.setAsMission")}</span>
        </label>
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

      {loadState === "loaded" && tasks.length === 0 && (
        <p className="empty-state">{t("today.noTasksYet")}</p>
      )}

      {loadState === "loaded" && tasks.length > 0 && (
        <ul className="task-list">
          {tasks.map((task) => (
            <li key={task.id} className={`task-list__item task-list__item--${task.status}`}>
              <div>
                <span>{task.title}</span>
                {task.is_daily_mission && <span className="task-list__mission-tag">{t("today.missionTag")}</span>}
                {task.description && <p className="task-list__description">{task.description}</p>}
              </div>
              <div className="task-list__actions">
                {task.status === "pending" && (
                  <>
                    <button
                      type="button"
                      disabled={updatingId === task.id}
                      onClick={() => void handleMissionChange(task, !task.is_daily_mission)}
                    >
                      {task.is_daily_mission ? t("today.clearMission") : t("today.setMission")}
                    </button>
                    <button type="button" onClick={() => void handleAction(task.id, "completed")}>
                      {t("today.done")}
                    </button>
                    <button type="button" onClick={() => void handleAction(task.id, "skipped")}>
                      {t("today.skip")}
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
