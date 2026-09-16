import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { smokingApi } from "../../services/domainApi";
import type { SmokingEvent, SmokingSummary } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

const OUTCOME_OPTIONS: SmokingEvent["outcome"][] = ["resisted", "alternative_used", "smoked"];
const OUTCOME_LABEL_KEYS: Record<SmokingEvent["outcome"], string> = {
  resisted: "smoking.outcomeResisted",
  alternative_used: "smoking.outcomeAlternative",
  smoked: "smoking.outcomeSmoked",
};

/**
 * Phase 7 scope: craving/trigger/outcome logging plus the detected-pattern
 * insights the backend computes deterministically from the user's own
 * history (never ML — that's Phase 10, see smoking_service.py). A "smoked"
 * outcome is logged through the exact same form and styling as any other
 * outcome — no shaming, no different treatment — matching the safety
 * boundaries RAM Core already enforces in conversation.
 */
export function SmokingScreen() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<SmokingSummary | null>(null);
  const [events, setEvents] = useState<SmokingEvent[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const [trigger, setTrigger] = useState("");
  const [intensity, setIntensity] = useState("5");
  const [context, setContext] = useState("");
  const [outcome, setOutcome] = useState<SmokingEvent["outcome"]>("resisted");
  const [alternativeAction, setAlternativeAction] = useState("");
  const [isLogging, setIsLogging] = useState(false);

  const [reflectionDrafts, setReflectionDrafts] = useState<Record<string, string>>({});
  const [savingReflectionId, setSavingReflectionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const [summaryData, eventsData] = await Promise.all([smokingApi.summary(), smokingApi.listEvents()]);
      setSummary(summaryData);
      setEvents(eventsData);
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleLogEvent(event: FormEvent) {
    event.preventDefault();
    const intensityValue = Number(intensity);
    if (!trigger.trim() || !intensityValue || intensityValue < 1 || intensityValue > 10) return;

    setIsLogging(true);
    try {
      await smokingApi.logEvent({
        trigger: trigger.trim(),
        craving_intensity: intensityValue,
        context: context.trim() || undefined,
        outcome,
        alternative_action: outcome === "alternative_used" ? alternativeAction.trim() || undefined : undefined,
      });
      setTrigger("");
      setIntensity("5");
      setContext("");
      setAlternativeAction("");
      setOutcome("resisted");
      await load();
    } finally {
      setIsLogging(false);
    }
  }

  async function handleSaveReflection(eventId: string) {
    const note = reflectionDrafts[eventId]?.trim();
    if (!note) return;
    setSavingReflectionId(eventId);
    try {
      await smokingApi.addReflection(eventId, note);
      setReflectionDrafts((prev) => ({ ...prev, [eventId]: "" }));
      await load();
    } finally {
      setSavingReflectionId(null);
    }
  }

  return (
    <main className="smoking-screen">
      <h1>{t("nav.smoking")}</h1>

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
          <section className="smoking-screen__summary" aria-label={t("smoking.summaryLabel")}>
            <div className="smoking-stat">
              <span className="smoking-stat__label">{t("smoking.streakLabel")}</span>
              <span className="smoking-stat__value">
                {summary.smoke_free_streak_days === null
                  ? t("smoking.streakUnknown")
                  : t("smoking.streakDays", { count: summary.smoke_free_streak_days })}
              </span>
            </div>
            <div className="smoking-stat">
              <span className="smoking-stat__label">{t("smoking.totalEventsLabel")}</span>
              <span className="smoking-stat__value">{summary.total_events}</span>
            </div>
            <div className="smoking-stat">
              <span className="smoking-stat__label">{t("smoking.resistedLabel")}</span>
              <span className="smoking-stat__value">{summary.resisted_count}</span>
            </div>
            <div className="smoking-stat">
              <span className="smoking-stat__label">{t("smoking.smokedLabel")}</span>
              <span className="smoking-stat__value">{summary.smoked_count}</span>
            </div>
          </section>

          <section className="smoking-screen__section" aria-label={t("smoking.insightsTitle")}>
            <h2>{t("smoking.insightsTitle")}</h2>
            {summary.detected_patterns.length === 0 ? (
              <p className="empty-state">{t("smoking.noInsightsYet")}</p>
            ) : (
              <ul className="smoking-screen__pattern-list">
                {summary.detected_patterns.map((pattern, index) => (
                  <li key={index}>{pattern.description}</li>
                ))}
              </ul>
            )}
          </section>

          <section className="smoking-screen__section" aria-label={t("smoking.logCraving")}>
            <h2>{t("smoking.logCraving")}</h2>
            <form onSubmit={handleLogEvent} className="smoking-screen__form">
              <input
                type="text"
                value={trigger}
                onChange={(event) => setTrigger(event.target.value)}
                placeholder={t("smoking.triggerPlaceholder")}
              />
              <label>
                {t("smoking.intensityLabel")}
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={intensity}
                  onChange={(event) => setIntensity(event.target.value)}
                />
              </label>
              <input
                type="text"
                value={context}
                onChange={(event) => setContext(event.target.value)}
                placeholder={t("smoking.contextPlaceholder")}
              />
              <fieldset>
                <legend>{t("smoking.outcomeLabel")}</legend>
                {OUTCOME_OPTIONS.map((option) => (
                  <label key={option}>
                    <input
                      type="radio"
                      name="outcome"
                      value={option}
                      checked={outcome === option}
                      onChange={() => setOutcome(option)}
                    />
                    {t(OUTCOME_LABEL_KEYS[option])}
                  </label>
                ))}
              </fieldset>
              {outcome === "alternative_used" && (
                <input
                  type="text"
                  value={alternativeAction}
                  onChange={(event) => setAlternativeAction(event.target.value)}
                  placeholder={t("smoking.alternativeActionPlaceholder")}
                />
              )}
              <button type="submit" disabled={isLogging || !trigger.trim()}>
                {isLogging ? t("common.loading") : t("common.save")}
              </button>
            </form>
          </section>

          <section className="smoking-screen__section" aria-label={t("smoking.recentEvents")}>
            <h2>{t("smoking.recentEvents")}</h2>
            {events.length === 0 ? (
              <p className="empty-state">{t("smoking.noEventsYet")}</p>
            ) : (
              <ul className="smoking-screen__log-list">
                {events.map((item) => (
                  <li key={item.id} className="smoking-screen__log-item">
                    <div>
                      <strong>{t(OUTCOME_LABEL_KEYS[item.outcome])}</strong> — {item.trigger}
                    </div>
                    {item.reflection_note ? (
                      <p className="smoking-screen__reflection">{item.reflection_note}</p>
                    ) : (
                      <div className="smoking-screen__reflection-form">
                        <p className="smoking-screen__reflection-prompt">{t("smoking.reflectionPrompt")}</p>
                        <textarea
                          value={reflectionDrafts[item.id] ?? ""}
                          onChange={(event) =>
                            setReflectionDrafts((prev) => ({ ...prev, [item.id]: event.target.value }))
                          }
                          placeholder={t("smoking.reflectionPlaceholder")}
                        />
                        <button
                          type="button"
                          disabled={savingReflectionId === item.id || !reflectionDrafts[item.id]?.trim()}
                          onClick={() => void handleSaveReflection(item.id)}
                        >
                          {t("smoking.addReflection")}
                        </button>
                      </div>
                    )}
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
