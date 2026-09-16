import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { habitsApi, predictionsApi } from "../../services/domainApi";
import type { Habit, ModelVersion, Prediction } from "../../types/domain";

type LoadState = "loading" | "loaded" | "error";

function confidenceLabelKey(confidence: Prediction["confidence"]): string {
  return `insights.confidence.${confidence}`;
}

/**
 * Phase 10 scope: section 9's personal-learning loop, surfaced as two
 * concrete prediction types (smoking risk, habit adherence) — see
 * app/services/prediction_service.py for the confidence-tier logic this
 * screen renders. Every prediction shown here carries its confidence tier
 * and explanation alongside the number; there is no bare probability
 * anywhere in this screen, on purpose.
 */
export function InsightsScreen() {
  const { t } = useTranslation();

  const [habits, setHabits] = useState<Habit[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [modelVersions, setModelVersions] = useState<ModelVersion[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const [trigger, setTrigger] = useState("");
  const [intensity, setIntensity] = useState("5");
  const [stress, setStress] = useState("");
  const [isPredictingSmoking, setIsPredictingSmoking] = useState(false);

  const [selectedHabitId, setSelectedHabitId] = useState("");
  const [isPredictingHabit, setIsPredictingHabit] = useState(false);

  const [feedbackGivenIds, setFeedbackGivenIds] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoadState("loading");
    try {
      const [habitList, predictionList, versions] = await Promise.all([
        habitsApi.list(true),
        predictionsApi.list(),
        predictionsApi.listModelVersions(),
      ]);
      setHabits(habitList);
      setPredictions(predictionList);
      setModelVersions(versions);
      if (!selectedHabitId && habitList.length > 0) {
        setSelectedHabitId(habitList[0].id);
      }
      setLoadState("loaded");
    } catch {
      setLoadState("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handlePredictSmokingRisk(event: FormEvent) {
    event.preventDefault();
    const intensityNum = Number(intensity);
    if (!trigger.trim() || !intensityNum) return;
    setIsPredictingSmoking(true);
    try {
      await predictionsApi.predictSmokingRisk({
        trigger: trigger.trim(),
        craving_intensity: intensityNum,
        stress_level: stress ? Number(stress) : undefined,
      });
      setTrigger("");
      setStress("");
      await load();
    } finally {
      setIsPredictingSmoking(false);
    }
  }

  async function handlePredictHabitAdherence() {
    if (!selectedHabitId) return;
    setIsPredictingHabit(true);
    try {
      await predictionsApi.predictHabitAdherence(selectedHabitId);
      await load();
    } finally {
      setIsPredictingHabit(false);
    }
  }

  async function handleFeedback(predictionId: string, actualOutcome: boolean) {
    await predictionsApi.giveFeedback(predictionId, actualOutcome);
    setFeedbackGivenIds((prev) => new Set(prev).add(predictionId));
  }

  return (
    <main className="insights-screen">
      <h1>{t("nav.insights")}</h1>

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
          <section className="insights-screen__section" aria-label={t("insights.smokingRiskLabel")}>
            <h2>{t("insights.smokingRiskLabel")}</h2>
            <form onSubmit={handlePredictSmokingRisk} className="insights-screen__form">
              <input
                type="text"
                value={trigger}
                onChange={(e) => setTrigger(e.target.value)}
                placeholder={t("smoking.triggerPlaceholder")}
              />
              <input
                type="number"
                min="1"
                max="10"
                value={intensity}
                onChange={(e) => setIntensity(e.target.value)}
                placeholder={t("smoking.intensityLabel")}
              />
              <input
                type="number"
                min="1"
                max="5"
                value={stress}
                onChange={(e) => setStress(e.target.value)}
                placeholder={t("insights.stressOptionalPlaceholder")}
              />
              <button type="submit" disabled={isPredictingSmoking || !trigger.trim()}>
                {isPredictingSmoking ? t("common.loading") : t("insights.checkRisk")}
              </button>
            </form>
          </section>

          {habits.length > 0 && (
            <section className="insights-screen__section" aria-label={t("insights.habitAdherenceLabel")}>
              <h2>{t("insights.habitAdherenceLabel")}</h2>
              <div className="insights-screen__form">
                <select value={selectedHabitId} onChange={(e) => setSelectedHabitId(e.target.value)}>
                  {habits.map((habit) => (
                    <option key={habit.id} value={habit.id}>
                      {habit.title}
                    </option>
                  ))}
                </select>
                <button type="button" onClick={() => void handlePredictHabitAdherence()} disabled={isPredictingHabit}>
                  {isPredictingHabit ? t("common.loading") : t("insights.checkAdherence")}
                </button>
              </div>
            </section>
          )}

          <section className="insights-screen__section" aria-label={t("insights.recentPredictionsLabel")}>
            <h2>{t("insights.recentPredictionsLabel")}</h2>
            {predictions.length === 0 ? (
              <p className="empty-state">{t("insights.noPredictionsYet")}</p>
            ) : (
              <ul className="insights-screen__prediction-list">
                {predictions.map((prediction) => (
                  <li key={prediction.id} className="insights-screen__prediction">
                    <div className="insights-screen__prediction-header">
                      <strong>
                        {prediction.prediction_type === "smoking_risk"
                          ? t("insights.smokingRiskLabel")
                          : t("insights.habitAdherenceLabel")}
                      </strong>
                      <span className="insights-screen__confidence-tag">
                        {t(confidenceLabelKey(prediction.confidence))}
                      </span>
                    </div>
                    {prediction.predicted_probability !== null && (
                      <p className="insights-screen__probability">
                        {(prediction.predicted_probability * 100).toFixed(0)}%
                      </p>
                    )}
                    <p className="insights-screen__explanation">{prediction.explanation}</p>
                    {!feedbackGivenIds.has(prediction.id) && prediction.predicted_probability !== null && (
                      <div className="insights-screen__feedback-buttons">
                        <span>{t("insights.whatActuallyHappened")}</span>
                        <button type="button" onClick={() => void handleFeedback(prediction.id, true)}>
                          {t("insights.outcomeYes")}
                        </button>
                        <button type="button" onClick={() => void handleFeedback(prediction.id, false)}>
                          {t("insights.outcomeNo")}
                        </button>
                      </div>
                    )}
                    {feedbackGivenIds.has(prediction.id) && (
                      <p className="insights-screen__feedback-recorded">{t("insights.feedbackRecorded")}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {modelVersions.length > 0 && (
            <section className="insights-screen__section" aria-label={t("insights.modelHistoryLabel")}>
              <h2>{t("insights.modelHistoryLabel")}</h2>
              <ul className="insights-screen__log-list">
                {modelVersions.map((version) => (
                  <li key={version.id}>
                    {version.prediction_type} v{version.version} — {version.training_sample_count}{" "}
                    {t("insights.samplesLabel")}
                    {version.training_accuracy !== null &&
                      ` (${(version.training_accuracy * 100).toFixed(0)}% ${t("insights.trainingAccuracyLabel")})`}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </main>
  );
}
