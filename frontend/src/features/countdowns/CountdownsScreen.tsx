import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { countdownsApi } from "../../services/domainApi";
import type { Countdown } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

const PRIORITY_OPTIONS: Countdown["priority"][] = ["low", "medium", "high"];
const REPEAT_OPTIONS: Countdown["repeat_rule"][] = ["none", "daily", "weekly", "monthly", "yearly"];

function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatTimeRemaining(targetIso: string, t: (key: string, opts?: Record<string, unknown>) => string): string {
  const diffMs = new Date(targetIso).getTime() - Date.now();
  if (diffMs <= 0) return t("countdowns.overdue");

  const totalMinutes = Math.floor(diffMs / 60000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return t("countdowns.remainingDays", { days, hours });
  if (hours > 0) return t("countdowns.remainingHours", { hours, minutes });
  return t("countdowns.remainingMinutes", { minutes });
}

/**
 * Phase 8 scope: countdowns are completely user-created and database-driven
 * (section 17) — there is nothing here to seed or pre-populate, only a form
 * that writes to the real /api/v1/countdowns endpoint. No exam/hackathon/
 * deadline is ever hardcoded anywhere in this screen.
 */
export function CountdownsScreen() {
  const { t } = useTranslation();
  const [countdowns, setCountdowns] = useState<Countdown[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const [title, setTitle] = useState("");
  const [targetDatetime, setTargetDatetime] = useState(() =>
    toDatetimeLocalValue(new Date(Date.now() + 24 * 60 * 60 * 1000)),
  );
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState<Countdown["priority"]>("medium");
  const [repeatRule, setRepeatRule] = useState<Countdown["repeat_rule"]>("none");
  const [isCreating, setIsCreating] = useState(false);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const data = await countdownsApi.list();
      setCountdowns(data);
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
    if (!title.trim() || !targetDatetime) return;

    setIsCreating(true);
    try {
      await countdownsApi.create({
        title: title.trim(),
        target_datetime: new Date(targetDatetime).toISOString(),
        category: category.trim() || undefined,
        priority,
        repeat_rule: repeatRule,
      });
      setTitle("");
      setCategory("");
      setPriority("medium");
      setRepeatRule("none");
      await load();
    } finally {
      setIsCreating(false);
    }
  }

  async function handleToggleActive(countdown: Countdown) {
    await countdownsApi.update(countdown.id, { is_active: !countdown.is_active });
    await load();
  }

  async function handleDelete(id: string) {
    await countdownsApi.remove(id);
    await load();
  }

  return (
    <main className="countdowns-screen">
      <h1>{t("nav.countdowns")}</h1>

      {loadState === "loading" && <p className="empty-state">{t("common.loading")}</p>}

      {loadState === "error" && (
        <div className="empty-state empty-state--error">
          <p>{t("common.somethingWentWrong")}</p>
          <button type="button" onClick={() => void load()}>
            {t("common.retry")}
          </button>
        </div>
      )}

      {loadState === "loaded" && (
        <>
          <section className="countdowns-screen__section" aria-label={t("countdowns.createTitle")}>
            <h2>{t("countdowns.createTitle")}</h2>
            <form onSubmit={handleCreate} className="countdowns-screen__form">
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t("countdowns.titlePlaceholder")}
              />
              <label>
                {t("countdowns.targetLabel")}
                <input
                  type="datetime-local"
                  value={targetDatetime}
                  onChange={(event) => setTargetDatetime(event.target.value)}
                />
              </label>
              <input
                type="text"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                placeholder={t("countdowns.categoryPlaceholder")}
              />
              <label>
                {t("countdowns.priorityLabel")}
                <select value={priority} onChange={(event) => setPriority(event.target.value as Countdown["priority"])}>
                  {PRIORITY_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {t(`countdowns.priority.${option}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("countdowns.repeatLabel")}
                <select
                  value={repeatRule}
                  onChange={(event) => setRepeatRule(event.target.value as Countdown["repeat_rule"])}
                >
                  {REPEAT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {t(`countdowns.repeat.${option}`)}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" disabled={isCreating || !title.trim()}>
                {isCreating ? t("common.loading") : t("common.add")}
              </button>
            </form>
          </section>

          <section className="countdowns-screen__section" aria-label={t("countdowns.listTitle")}>
            <h2>{t("countdowns.listTitle")}</h2>
            {countdowns.length === 0 ? (
              <p className="empty-state">{t("countdowns.noCountdownsYet")}</p>
            ) : (
              <ul className="countdowns-screen__list">
                {countdowns.map((countdown) => (
                  <li
                    key={countdown.id}
                    className={`countdowns-screen__item${countdown.is_active ? "" : " countdowns-screen__item--inactive"}`}
                  >
                    <div className="countdowns-screen__item-main">
                      <strong>{countdown.title}</strong>
                      <span className="countdowns-screen__remaining">{formatTimeRemaining(countdown.target_datetime, t)}</span>
                    </div>
                    <div className="countdowns-screen__item-meta">
                      {countdown.category && <span>{countdown.category}</span>}
                      <span>{t(`countdowns.priority.${countdown.priority}`)}</span>
                      {countdown.repeat_rule !== "none" && <span>{t(`countdowns.repeat.${countdown.repeat_rule}`)}</span>}
                    </div>
                    <div className="countdowns-screen__item-actions">
                      <button type="button" onClick={() => void handleToggleActive(countdown)}>
                        {countdown.is_active ? t("countdowns.deactivate") : t("countdowns.activate")}
                      </button>
                      <button type="button" onClick={() => void handleDelete(countdown.id)}>
                        {t("common.delete")}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
