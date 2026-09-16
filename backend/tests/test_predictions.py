import uuid
from datetime import date, datetime, timedelta, timezone

from app.models.habit import Habit, HabitLog
from tests.helpers import register_and_login


def _get_user_id(client, headers):
    return uuid.UUID(client.get("/api/v1/users/me", headers=headers).json()["id"])


def _log_smoking_event(client, headers, *, trigger, intensity, stress=None, outcome):
    payload = {"trigger": trigger, "craving_intensity": intensity, "outcome": outcome}
    if stress is not None:
        payload["stress_level"] = stress
    return client.post("/api/v1/smoking/events", json=payload, headers=headers)


def test_smoking_risk_with_no_history_returns_no_data(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "after lunch", "craving_intensity": 7},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["confidence"] == "no_data"
    assert body["predicted_probability"] is None


def test_smoking_risk_with_a_few_events_returns_laplace_smoothed_baseline(client):
    headers = register_and_login(client)

    # 2 smoked, 1 resisted -> Laplace-smoothed rate = (2+1)/(3+2) = 0.6
    _log_smoking_event(client, headers, trigger="boredom", intensity=5, outcome="smoked")
    _log_smoking_event(client, headers, trigger="boredom", intensity=6, outcome="smoked")
    _log_smoking_event(client, headers, trigger="boredom", intensity=4, outcome="resisted")

    response = client.post(
        "/api/v1/predictions/smoking-risk", json={"trigger": "boredom", "craving_intensity": 5}, headers=headers
    )
    body = response.json()
    assert body["confidence"] == "baseline_low_data"
    assert round(body["predicted_probability"], 2) == 0.6


def test_smoking_risk_with_enough_events_trains_a_model_and_separates_risk(client):
    headers = register_and_login(client)

    # Clearly separable synthetic pattern: high intensity -> smoked, low intensity -> resisted.
    for i in range(8):
        _log_smoking_event(client, headers, trigger="stress", intensity=9, stress=5, outcome="smoked")
        _log_smoking_event(client, headers, trigger="calm moment", intensity=2, stress=1, outcome="resisted")

    high_risk = client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "stress", "craving_intensity": 9, "stress_level": 5},
        headers=headers,
    ).json()
    low_risk = client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "calm moment", "craving_intensity": 2, "stress_level": 1},
        headers=headers,
    ).json()

    assert high_risk["confidence"] in ("model_limited_data", "model")
    assert low_risk["confidence"] in ("model_limited_data", "model")
    assert high_risk["predicted_probability"] > low_risk["predicted_probability"]
    assert high_risk["predicted_probability"] > 0.5
    assert low_risk["predicted_probability"] < 0.5


def test_repeated_identical_prediction_reuses_model_and_does_not_duplicate_feature_rows(client, db_session):
    from app.models.prediction import ModelFeature

    headers = register_and_login(client)

    for _ in range(8):
        _log_smoking_event(client, headers, trigger="stress", intensity=9, stress=5, outcome="smoked")
        _log_smoking_event(client, headers, trigger="calm moment", intensity=2, stress=1, outcome="resisted")

    client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "stress", "craving_intensity": 9, "stress_level": 5},
        headers=headers,
    )
    client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "calm moment", "craving_intensity": 2, "stress_level": 1},
        headers=headers,
    )

    versions = client.get("/api/v1/predictions/model-versions", headers=headers).json()
    # Both predict calls above were trained on the exact same 16 events —
    # this must reuse one ModelVersion, not create a second one. (Regression
    # test for a real bug: an earlier version of _run_prediction retrained
    # and persisted a brand-new ModelVersion, plus a full duplicate set of
    # ModelFeature rows, on every single predict call regardless of whether
    # the training data had actually changed.)
    assert len(versions) == 1
    assert versions[0]["training_sample_count"] == 16
    assert versions[0]["algorithm"] == "logistic_regression"

    feature_rows = db_session.query(ModelFeature).filter(ModelFeature.prediction_type == "smoking_risk").all()
    assert len(feature_rows) == 16


def test_repredicting_after_a_new_event_creates_exactly_one_new_version(client):
    """Companion to the reuse test above: when the training set genuinely
    DOES grow, a real retrain (and exactly one new ModelVersion) should
    still happen — the fix must not overcorrect into never retraining."""
    headers = register_and_login(client)

    for _ in range(8):
        _log_smoking_event(client, headers, trigger="stress", intensity=9, stress=5, outcome="smoked")
        _log_smoking_event(client, headers, trigger="calm moment", intensity=2, stress=1, outcome="resisted")

    client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "stress", "craving_intensity": 9, "stress_level": 5},
        headers=headers,
    )
    _log_smoking_event(client, headers, trigger="stress", intensity=9, stress=5, outcome="smoked")
    client.post(
        "/api/v1/predictions/smoking-risk",
        json={"trigger": "stress", "craving_intensity": 9, "stress_level": 5},
        headers=headers,
    )

    versions = client.get("/api/v1/predictions/model-versions", headers=headers).json()
    assert len(versions) == 2
    assert sorted(v["training_sample_count"] for v in versions) == [16, 17]


def test_habit_adherence_with_no_due_history_returns_no_data(client):
    headers = register_and_login(client)
    habit = client.post("/api/v1/habits", json={"title": "Read"}, headers=headers).json()

    response = client.post(f"/api/v1/predictions/habit-adherence/{habit['id']}", headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["confidence"] == "no_data"
    assert body["predicted_probability"] is None


def test_habit_adherence_with_backdated_history_computes_a_rate(client, db_session):
    headers = register_and_login(client)
    user_id = _get_user_id(client, headers)

    habit = client.post("/api/v1/habits", json={"title": "Exercise"}, headers=headers).json()
    habit_row = db_session.get(Habit, uuid.UUID(habit["id"]))

    # Backdate creation so there's 20 days of daily due-history to learn from.
    today = date.today()
    habit_row.created_at = datetime.now(timezone.utc) - timedelta(days=25)
    db_session.add(habit_row)
    db_session.commit()

    # Complete every day except the most recent 3 -> today should look "at risk."
    for offset in range(4, 21):
        db_session.add(
            HabitLog(habit_id=habit_row.id, user_id=user_id, completed_on=today - timedelta(days=offset))
        )
    db_session.commit()

    response = client.post(f"/api/v1/predictions/habit-adherence/{habit['id']}", headers=headers)
    body = response.json()
    assert body["confidence"] in ("baseline_low_data", "model_limited_data", "model")
    assert body["predicted_probability"] is not None


def test_prediction_feedback_can_only_be_recorded_once(client):
    headers = register_and_login(client)
    prediction = client.post(
        "/api/v1/predictions/smoking-risk", json={"trigger": "x", "craving_intensity": 5}, headers=headers
    ).json()

    first = client.post(
        f"/api/v1/predictions/{prediction['id']}/feedback", json={"actual_outcome": False}, headers=headers
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/predictions/{prediction['id']}/feedback", json={"actual_outcome": True}, headers=headers
    )
    assert second.status_code == 409


def test_user_cannot_access_or_give_feedback_on_another_users_prediction(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    prediction = client.post(
        "/api/v1/predictions/smoking-risk", json={"trigger": "x", "craving_intensity": 5}, headers=headers_a
    ).json()

    response = client.post(
        f"/api/v1/predictions/{prediction['id']}/feedback", json={"actual_outcome": True}, headers=headers_b
    )
    assert response.status_code == 404


def test_user_cannot_predict_adherence_for_another_users_habit(client):
    headers_a = register_and_login(client, email="a2@example.com")
    headers_b = register_and_login(client, email="b2@example.com")

    habit = client.post("/api/v1/habits", json={"title": "A's habit"}, headers=headers_a).json()

    response = client.post(f"/api/v1/predictions/habit-adherence/{habit['id']}", headers=headers_b)
    assert response.status_code == 404
