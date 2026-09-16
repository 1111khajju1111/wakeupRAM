import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { healthApi } from "../../services/domainApi";
import type { HealthTodaySummary, MoodLog } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

const WATER_QUICK_ADD_ML = [250, 500];
const MOOD_OPTIONS: MoodLog["mood"][] = ["very_low", "low", "neutral", "good", "great"];
const MOOD_LABEL_KEYS: Record<MoodLog["mood"], string> = {
  very_low: "health.moodVeryLow",
  low: "health.moodLow",
  neutral: "health.moodNeutral",
  good: "health.moodGood",
  great: "health.moodGreat",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Phase 5 scope: configurable diet/water/sleep/workout/mood logging plus a
 * same-day summary. This never diagnoses anything and never estimates a
 * number the user didn't log (see HealthTodaySummary.calories_total being
 * `null`, not 0, when nothing logged calories) — consistent with the safety
 * boundaries RAM Core already enforces in conversation.
 */
export function HealthScreen() {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<HealthTodaySummary | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const [mealDescription, setMealDescription] = useState("");
  const [mealType, setMealType] = useState<"breakfast" | "lunch" | "dinner" | "snack">("breakfast");
  const [isLoggingMeal, setIsLoggingMeal] = useState(false);

  const [workoutType, setWorkoutType] = useState("");
  const [workoutMinutes, setWorkoutMinutes] = useState("");
  const [isLoggingWorkout, setIsLoggingWorkout] = useState(false);

  const [sleepHours, setSleepHours] = useState("");
  const [isLoggingSleep, setIsLoggingSleep] = useState(false);

  const [isLoggingWater, setIsLoggingWater] = useState(false);
  const [isLoggingMood, setIsLoggingMood] = useState(false);

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const data = await healthApi.today();
      setSummary(data);
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAddWater(amountMl: number) {
    setIsLoggingWater(true);
    try {
      await healthApi.logWater(amountMl);
      await load();
    } finally {
      setIsLoggingWater(false);
    }
  }

  async function handleLogMeal(event: FormEvent) {
    event.preventDefault();
    if (!mealDescription.trim()) return;
    setIsLoggingMeal(true);
    try {
      await healthApi.logDiet({ meal_type: mealType, description: mealDescription.trim() });
      setMealDescription("");
      await load();
    } finally {
      setIsLoggingMeal(false);
    }
  }

  async function handleLogWorkout(event: FormEvent) {
    event.preventDefault();
    const minutes = Number(workoutMinutes);
    if (!workoutType.trim() || !minutes || minutes <= 0) return;
    setIsLoggingWorkout(true);
    try {
      await healthApi.logWorkout({ activity_type: workoutType.trim(), duration_minutes: minutes });
      setWorkoutType("");
      setWorkoutMinutes("");
      await load();
    } finally {
      setIsLoggingWorkout(false);
    }
  }

  async function handleLogSleep(event: FormEvent) {
    event.preventDefault();
    const hours = Number(sleepHours);
    if (!hours || hours <= 0) return;
    setIsLoggingSleep(true);
    try {
      await healthApi.logSleep({ sleep_date: todayIso(), duration_minutes: Math.round(hours * 60) });
      setSleepHours("");
      await load();
    } finally {
      setIsLoggingSleep(false);
    }
  }

  async function handleLogMood(mood: MoodLog["mood"]) {
    setIsLoggingMood(true);
    try {
      await healthApi.logMood({ mood });
      await load();
    } finally {
      setIsLoggingMood(false);
    }
  }

  return (
    <main className="health-screen">
      <h1>{t("nav.health")}</h1>

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
          <section className="health-screen__summary" aria-label={t("health.summaryLabel")}>
            <div className="health-stat">
              <span className="health-stat__label">{t("health.waterLabel")}</span>
              <span className="health-stat__value">{summary.water_ml_total} ml</span>
            </div>
            <div className="health-stat">
              <span className="health-stat__label">{t("health.caloriesLabel")}</span>
              <span className="health-stat__value">
                {summary.calories_total === null ? "—" : summary.calories_total}
              </span>
            </div>
            <div className="health-stat">
              <span className="health-stat__label">{t("health.lastNightSleepLabel")}</span>
              <span className="health-stat__value">
                {summary.last_night_sleep?.duration_minutes
                  ? `${(summary.last_night_sleep.duration_minutes / 60).toFixed(1)}h`
                  : "—"}
              </span>
            </div>
            <div className="health-stat">
              <span className="health-stat__label">{t("health.moodLabel")}</span>
              <span className="health-stat__value">
                {summary.latest_mood_today ? t(MOOD_LABEL_KEYS[summary.latest_mood_today.mood]) : "—"}
              </span>
            </div>
          </section>

          <section className="health-screen__section" aria-label={t("health.waterLabel")}>
            <h2>{t("health.waterLabel")}</h2>
            <div className="health-screen__quick-actions">
              {WATER_QUICK_ADD_ML.map((amount) => (
                <button
                  key={amount}
                  type="button"
                  disabled={isLoggingWater}
                  onClick={() => void handleAddWater(amount)}
                >
                  +{amount} ml
                </button>
              ))}
            </div>
          </section>

          <section className="health-screen__section" aria-label={t("health.moodCheckIn")}>
            <h2>{t("health.moodCheckIn")}</h2>
            <div className="health-screen__quick-actions">
              {MOOD_OPTIONS.map((mood) => (
                <button
                  key={mood}
                  type="button"
                  disabled={isLoggingMood}
                  onClick={() => void handleLogMood(mood)}
                  className={
                    summary.latest_mood_today?.mood === mood ? "health-screen__mood--active" : undefined
                  }
                >
                  {t(MOOD_LABEL_KEYS[mood])}
                </button>
              ))}
            </div>
          </section>

          <section className="health-screen__section" aria-label={t("health.logMeal")}>
            <h2>{t("health.logMeal")}</h2>
            <form onSubmit={handleLogMeal} className="health-screen__form">
              <select value={mealType} onChange={(event) => setMealType(event.target.value as typeof mealType)}>
                <option value="breakfast">{t("health.mealBreakfast")}</option>
                <option value="lunch">{t("health.mealLunch")}</option>
                <option value="dinner">{t("health.mealDinner")}</option>
                <option value="snack">{t("health.mealSnack")}</option>
              </select>
              <input
                type="text"
                value={mealDescription}
                onChange={(event) => setMealDescription(event.target.value)}
                placeholder={t("health.mealDescriptionPlaceholder")}
              />
              <button type="submit" disabled={isLoggingMeal || !mealDescription.trim()}>
                {isLoggingMeal ? t("common.loading") : t("common.add")}
              </button>
            </form>
            {summary.meals_logged.length > 0 && (
              <ul className="health-screen__log-list">
                {summary.meals_logged.map((meal) => (
                  <li key={meal.id}>
                    <strong>{meal.meal_type}</strong> — {meal.description}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="health-screen__section" aria-label={t("health.logWorkout")}>
            <h2>{t("health.logWorkout")}</h2>
            <form onSubmit={handleLogWorkout} className="health-screen__form">
              <input
                type="text"
                value={workoutType}
                onChange={(event) => setWorkoutType(event.target.value)}
                placeholder={t("health.workoutTypePlaceholder")}
              />
              <input
                type="number"
                min="1"
                value={workoutMinutes}
                onChange={(event) => setWorkoutMinutes(event.target.value)}
                placeholder={t("health.workoutMinutesPlaceholder")}
              />
              <button
                type="submit"
                disabled={isLoggingWorkout || !workoutType.trim() || !workoutMinutes}
              >
                {isLoggingWorkout ? t("common.loading") : t("common.add")}
              </button>
            </form>
            {summary.workouts_today.length > 0 && (
              <ul className="health-screen__log-list">
                {summary.workouts_today.map((workout) => (
                  <li key={workout.id}>
                    {workout.activity_type} — {workout.duration_minutes} min
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="health-screen__section" aria-label={t("health.logSleep")}>
            <h2>{t("health.logSleep")}</h2>
            <form onSubmit={handleLogSleep} className="health-screen__form">
              <input
                type="number"
                min="0"
                step="0.5"
                value={sleepHours}
                onChange={(event) => setSleepHours(event.target.value)}
                placeholder={t("health.sleepHoursPlaceholder")}
              />
              <button type="submit" disabled={isLoggingSleep || !sleepHours}>
                {isLoggingSleep ? t("common.loading") : t("common.save")}
              </button>
            </form>
          </section>
        </>
      )}
    </main>
  );
}
