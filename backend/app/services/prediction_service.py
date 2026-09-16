"""
Personal ML orchestration (section 9's loop: extract -> feature engineer ->
train -> predict -> feedback -> improve).

The confidence-tier thresholds below are this module's central honesty
mechanism: section 9 says "avoid training if insufficient data" and "return
uncertainty/confidence," and the master prompt says "if ML has insufficient
observations, say so and use a deterministic baseline rather than
fabricating a prediction." Every prediction this service returns carries one
of four tiers, and the tier — not just the number — is what the caller
should act on:

- no_data: zero relevant history. predicted_probability is None. There is
  nothing to say yet.
- baseline_low_data (1-9 labeled examples): too few to fit a personal model
  responsibly. Returns the user's own Laplace-smoothed empirical rate —
  their real history, just not conditioned on the specific context of this
  request.
- model_limited_data (10-29 examples): enough to fit app/ml/model.py's
  logistic regression, but explicitly labeled as still-thin.
- model (30+ examples): a personal model fit on a reasonably-sized personal
  history. Still not "certain" — see PredictionRead.explanation, which
  always states the sample count so the number is never presented bare.

Retraining happens on-demand rather than on a schedule — but NOT on every
single prediction request regardless of whether anything changed: if the
training set is the same size as what the currently active ModelVersion for
this (user, prediction_type) was trained on, that version is reused rather
than retrained (see the reuse check in _run_prediction — this was a real
bug, fixed after being caught in review: an earlier version of this
function retrained and persisted a brand-new ModelVersion, plus a full
duplicate set of ModelFeature rows, on every call, which meant simply
checking your own risk repeatedly would grow both tables without bound even
with zero new logged events in between). When the training set HAS grown,
retraining is still cheap — a few hundred rows of gradient descent
completes in milliseconds, so there's no need for more elaborate
cache-invalidation than a sample-count comparison (this is not the "retrain
a large neural network after every response" section 9 warns against).
Each genuine retrain is persisted as its own ModelVersion (section 9:
"store model versions and metrics"), so the training history itself stays
inspectable.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import features as feature_lib
from app.ml.model import fit_standardizer, apply_standardizer, predict_proba, train, training_accuracy
from app.models.habit import Habit
from app.models.prediction import ModelFeature, ModelVersion, Prediction, PredictionFeedback
from app.services import habit_service
from app.services.habit_service import _get_owned_habit

MIN_SAMPLES_FOR_MODEL = 10
MIN_SAMPLES_FOR_HIGHER_CONFIDENCE = 30


class NotFoundError(Exception):
    pass


class AlreadyGivenFeedbackError(Exception):
    pass


def _laplace_smoothed_rate(labels: list[bool]) -> float:
    """(#true + 1) / (n + 2) — the standard Bayesian-with-a-uniform-prior
    correction, so a user with e.g. 2 events and both "smoked" doesn't get
    told a bare, overconfident 100%."""
    positives = sum(1 for label in labels if label)
    return (positives + 1) / (len(labels) + 2)


def _run_prediction(
    db: Session,
    user_id: uuid.UUID,
    prediction_type: str,
    feature_order: list[str],
    training_rows: list[feature_lib.Features],
    training_labels: list[bool],
    training_occurred_ats: list,
    query_features: feature_lib.Features,
    no_history_explanation: str,
) -> Prediction:
    n = len(training_labels)

    if n == 0:
        prediction = Prediction(
            user_id=user_id,
            prediction_type=prediction_type,
            predicted_probability=None,
            confidence="no_data",
            model_version_id=None,
            input_features=query_features,
            explanation=no_history_explanation,
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
        return prediction

    if n < MIN_SAMPLES_FOR_MODEL:
        baseline = _laplace_smoothed_rate(training_labels)
        prediction = Prediction(
            user_id=user_id,
            prediction_type=prediction_type,
            predicted_probability=baseline,
            confidence="baseline_low_data",
            model_version_id=None,
            input_features=query_features,
            explanation=(
                f"Based on your own history so far ({n} logged), but not enough yet to train a "
                "personalized model — this is your overall rate, not adjusted for today's specific context."
            ),
        )
        db.add(prediction)
        db.commit()
        db.refresh(prediction)
        return prediction

    # Enough data to train. Reuse the latest existing version if nothing
    # about the training set has changed since it was trained, rather than
    # unconditionally retraining and persisting a brand-new ModelVersion (and
    # a full duplicate set of ModelFeature rows) on every single prediction
    # request. Without this check, calling this endpoint repeatedly — a very
    # likely usage pattern for "what's my risk right now?" — grows both
    # tables without bound even when the user's underlying history hasn't
    # changed at all between calls. `training_sample_count` matching is a
    # pragmatic approximation of "unchanged" (not a full content hash): an
    # edit to a historical event's label/features without any change in
    # count would go undetected here and reuse a now-slightly-stale version
    # until the next new event triggers a real retrain. Documented as a
    # known simplification rather than hidden, since the far more common
    # case by far — new events accumulating — is handled correctly.
    latest_version = db.execute(
        select(ModelVersion)
        .where(ModelVersion.user_id == user_id, ModelVersion.prediction_type == prediction_type)
        .order_by(ModelVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_version is not None and latest_version.training_sample_count == n:
        model_version = latest_version
        params = model_version.parameters
        weights, bias = params["weights"], params["bias"]
        means, stds = params["feature_means"], params["feature_stds"]
        accuracy = model_version.training_accuracy
    else:
        x_rows = [feature_lib.features_to_row(row, feature_order) for row in training_rows]
        y = [1 if label else 0 for label in training_labels]
        means, stds = fit_standardizer(x_rows)
        x_standardized = [apply_standardizer(row, means, stds) for row in x_rows]
        weights, bias = train(x_standardized, y)
        accuracy = training_accuracy(weights, bias, x_standardized, y)

        prior_versions = db.execute(
            select(ModelVersion).where(
                ModelVersion.user_id == user_id, ModelVersion.prediction_type == prediction_type
            )
        ).scalars()
        next_version = max((v.version for v in prior_versions), default=0) + 1

        model_version = ModelVersion(
            user_id=user_id,
            prediction_type=prediction_type,
            version=next_version,
            algorithm="logistic_regression",
            parameters={
                "feature_order": feature_order,
                "weights": weights,
                "bias": bias,
                "feature_means": means,
                "feature_stds": stds,
            },
            training_sample_count=n,
            training_accuracy=accuracy,
            trained_at=datetime.now(timezone.utc),
        )
        db.add(model_version)
        db.flush()  # need model_version.id before attaching ModelFeature rows

        for row, label, occurred_at in zip(training_rows, training_labels, training_occurred_ats):
            db.add(
                ModelFeature(
                    user_id=user_id,
                    prediction_type=prediction_type,
                    model_version_id=model_version.id,
                    features=row,
                    label=label,
                    occurred_at=occurred_at
                    if isinstance(occurred_at, datetime)
                    else datetime.combine(occurred_at, datetime.min.time(), tzinfo=timezone.utc),
                )
            )

    query_row = apply_standardizer(feature_lib.features_to_row(query_features, feature_order), means, stds)
    probability = predict_proba(weights, bias, query_row)

    confidence = "model" if n >= MIN_SAMPLES_FOR_HIGHER_CONFIDENCE else "model_limited_data"
    explanation = (
        f"Based on a personal model trained on {n} logged examples "
        f"(training accuracy {accuracy:.0%}). "
        + ("Enough history for a reasonably steady estimate." if confidence == "model" else "Still early — accuracy improves as you log more.")
    )

    prediction = Prediction(
        user_id=user_id,
        prediction_type=prediction_type,
        predicted_probability=probability,
        confidence=confidence,
        model_version_id=model_version.id,
        input_features=query_features,
        explanation=explanation,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def predict_smoking_risk(
    db: Session, user_id: uuid.UUID, trigger: str, craving_intensity: int, stress_level: int | None
) -> Prediction:
    training_rows, labels, occurred_ats = feature_lib.build_smoking_risk_training_set(db, user_id)
    query_features = feature_lib.build_smoking_risk_query_features(
        db, user_id, trigger, craving_intensity, stress_level
    )
    return _run_prediction(
        db,
        user_id,
        "smoking_risk",
        feature_lib.FEATURE_ORDER_SMOKING_RISK,
        training_rows,
        labels,
        occurred_ats,
        query_features,
        no_history_explanation="No cravings logged yet, so there's no history to estimate risk from.",
    )


def predict_habit_adherence(db: Session, user_id: uuid.UUID, habit_id: uuid.UUID, today: date) -> Prediction:
    try:
        habit: Habit = _get_owned_habit(db, user_id, habit_id)
    except habit_service.NotFoundError as exc:
        raise NotFoundError(str(exc)) from exc
    training_rows, labels, due_days = feature_lib.build_habit_adherence_training_set(db, user_id, habit, today)
    query_features = feature_lib.build_habit_adherence_query_features(db, user_id, habit, today)
    return _run_prediction(
        db,
        user_id,
        "habit_adherence",
        feature_lib.FEATURE_ORDER_HABIT_ADHERENCE,
        training_rows,
        labels,
        due_days,
        query_features,
        no_history_explanation="No due-days logged yet for this habit, so there's no history to estimate from.",
    )


# ---- Reads ----


def list_predictions(db: Session, user_id: uuid.UUID, prediction_type: str | None = None) -> list[Prediction]:
    stmt = select(Prediction).where(Prediction.user_id == user_id)
    if prediction_type is not None:
        stmt = stmt.where(Prediction.prediction_type == prediction_type)
    return list(db.execute(stmt.order_by(Prediction.created_at.desc())).scalars())


def list_model_versions(db: Session, user_id: uuid.UUID, prediction_type: str | None = None) -> list[ModelVersion]:
    stmt = select(ModelVersion).where(ModelVersion.user_id == user_id)
    if prediction_type is not None:
        stmt = stmt.where(ModelVersion.prediction_type == prediction_type)
    return list(db.execute(stmt.order_by(ModelVersion.trained_at.desc())).scalars())


def _get_owned_prediction(db: Session, user_id: uuid.UUID, prediction_id: uuid.UUID) -> Prediction:
    prediction = db.execute(
        select(Prediction).where(Prediction.id == prediction_id, Prediction.user_id == user_id)
    ).scalar_one_or_none()
    if prediction is None:
        raise NotFoundError("Prediction not found")
    return prediction


def record_feedback(
    db: Session, user_id: uuid.UUID, prediction_id: uuid.UUID, actual_outcome: bool
) -> PredictionFeedback:
    """Stores the user's own confirmation of what actually happened.

    Honesty note (this matters, so it's spelled out rather than left
    implicit): for BOTH prediction types currently implemented, this
    feedback does NOT feed back into training. `build_smoking_risk_training_set`
    labels every training row directly from `SmokingEvent.outcome`, and
    `build_habit_adherence_training_set` labels every row directly from
    `HabitLog` presence — both already have an automatically-observed
    ground truth elsewhere in the app, so there is nothing for this endpoint
    to add to the training set that isn't already there once the user logs
    the smoking event / habit completion through their normal flow.

    This endpoint still exists and is worth keeping because: (1) not every
    future prediction_type will have an automatic ground truth this clean —
    section 9's example list includes things like "spending-risk trend" or
    "goal completion probability" where a user's own confirmation may be
    the ONLY source of a label, and this is the mechanism for that once
    such a type is added; and (2) it gives the user an explicit record of
    "was Ram's estimate right?" for their own reflection, independent of
    whether it currently changes the model. If you're adding a new
    prediction_type that has no other ground-truth source, wire its
    training-set builder to read from PredictionFeedback instead of (or in
    addition to) domain data, following this same pattern."""
    _get_owned_prediction(db, user_id, prediction_id)  # 404s before the uniqueness check below

    existing = db.execute(
        select(PredictionFeedback).where(PredictionFeedback.prediction_id == prediction_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise AlreadyGivenFeedbackError("Feedback already recorded for this prediction")

    feedback = PredictionFeedback(
        prediction_id=prediction_id,
        user_id=user_id,
        actual_outcome=actual_outcome,
        recorded_at=datetime.now(timezone.utc),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
