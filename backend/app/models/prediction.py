import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Section 9 (Personal Learning & ML) + section 19's four ML tables:
# model_features, model_versions, predictions, prediction_feedback.
#
# This is deliberately NOT the same thing as smoking_service.detect_patterns
# (Phase 7): that's a transparent frequency count ("this trigger preceded a
# slip N times") with no trained parameters. This is an actual personal
# model — per (user, prediction_type) — trained on the user's own logged
# outcomes, whose whole job is to output a calibrated probability with an
# honest confidence tier, never a bare guess. See app/ml/model.py for the
# pure-Python logistic regression itself and app/services/prediction_service.py
# for the confidence-tier logic (no_data / baseline / model_limited_data /
# model) that decides whether there's even enough data to train at all.
#
# `prediction_type` is a free string (not an enum table) — same reasoning as
# SmokingEvent.trigger: new prediction types (section 9 lists seven example
# predictions) are added by writing a new feature-extraction function in
# app/ml/features.py, not by a schema migration.


class ModelVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per training run. Kept even after a newer version exists —
    "store model versions and metrics" (section 9) means history, not just
    the latest snapshot."""

    __tablename__ = "model_versions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Always "logistic_regression" today (see app/ml/model.py) — this column
    # exists so a future prediction_type needing a different interpretable
    # model (section 9 also mentions random forest / gradient boosting for
    # nonlinear behavior) doesn't require a schema change.
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False, default="logistic_regression")

    # {"feature_order": [...], "weights": [...], "bias": ..., "feature_means":
    # [...], "feature_stds": [...]} — everything predict_proba needs, so a
    # later prediction can reuse this exact trained model without retraining
    # if desired. Currently retrained fresh on every prediction request (see
    # prediction_service docstring for why that's fine at this data scale),
    # but the version row is kept regardless as the "personal learning loop"
    # audit trail section 9 asks for.
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)

    training_sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Training-set accuracy (0-1) at the decision threshold of 0.5 — a
    # rough, honestly-labeled-as-training-accuracy metric, not a claim of
    # held-out generalization performance (samples are too few for a
    # meaningful train/test split in most users' early data).
    training_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ModelVersion id={self.id} type={self.prediction_type} v={self.version}>"


class ModelFeature(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per labeled training example used to train a model version —
    the persisted output of the "feature engineering" step in section 9's
    pipeline, kept for inspectability (a user or developer can see exactly
    what data point led to what label) rather than only living transiently
    in memory during training."""

    __tablename__ = "model_features"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )

    # Named feature dict, e.g. {"craving_intensity": 7, "is_evening": 1, ...}
    # — named rather than a bare array so a later prediction_type can use a
    # different feature set without a schema change, and so this is legible
    # without cross-referencing ModelVersion.parameters.feature_order.
    features: Mapped[dict] = mapped_column(JSON, nullable=False)
    # The known outcome this example was labeled with (e.g. did this craving
    # end in "smoked"). Every row here is labeled by definition — unlabeled
    # feature snapshots (a live prediction query) live in Prediction.input_features
    # instead, never in this table.
    label: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ModelFeature id={self.id} type={self.prediction_type} label={self.label}>"


class Prediction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "predictions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prediction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True
    )

    # None when confidence is "no_data" — an honest absence, never a
    # fabricated number standing in for "we don't know yet."
    predicted_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    # no_data | baseline_low_data | model_limited_data | model — see
    # prediction_service.CONFIDENCE_* thresholds for exactly what each means
    # and why. Every response surfaces this tier, never just the number.
    confidence: Mapped[str] = mapped_column(String(30), nullable=False)

    input_features: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Human-readable one-liner shown alongside the number, e.g. "Based on 14
    # logged cravings, trained on your own history." Generated deterministically
    # from confidence + sample count, never a free-form AI-written claim.
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Prediction id={self.id} type={self.prediction_type} p={self.predicted_probability}>"


class PredictionFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The outcome-feedback half of section 9's loop. One prediction can only
    be given feedback once — see prediction_service for the enforcement —
    since a prediction is about a single specific future moment, not an
    ongoing thing that gets re-graded."""

    __tablename__ = "prediction_feedback"

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actual_outcome: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PredictionFeedback id={self.id} prediction_id={self.prediction_id} outcome={self.actual_outcome}>"
