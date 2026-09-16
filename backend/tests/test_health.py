from datetime import date, timedelta

from tests.helpers import register_and_login


def test_create_diet_log_and_list(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/health/diet",
        json={"meal_type": "breakfast", "description": "Idli and sambar", "calories": 350},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["meal_type"] == "breakfast"
    assert response.json()["calories"] == 350

    logs = client.get("/api/v1/health/diet", headers=headers).json()
    assert len(logs) == 1


def test_water_log_totals_in_today_summary(client):
    headers = register_and_login(client)

    client.post("/api/v1/health/water", json={"amount_ml": 250}, headers=headers)
    client.post("/api/v1/health/water", json={"amount_ml": 500}, headers=headers)

    summary = client.get("/api/v1/health/today", headers=headers).json()
    assert summary["water_ml_total"] == 750


def test_today_summary_calories_total_is_none_when_no_meal_logged_calories(client):
    headers = register_and_login(client)

    client.post(
        "/api/v1/health/diet", json={"meal_type": "snack", "description": "Tea"}, headers=headers
    )

    summary = client.get("/api/v1/health/today", headers=headers).json()
    assert summary["calories_total"] is None
    assert len(summary["meals_logged"]) == 1


def test_logging_same_night_sleep_twice_updates_not_duplicates(client):
    headers = register_and_login(client)
    today = date.today().isoformat()

    client.post(
        "/api/v1/health/sleep",
        json={"sleep_date": today, "duration_minutes": 360, "quality": 3},
        headers=headers,
    )
    response = client.post(
        "/api/v1/health/sleep",
        json={"sleep_date": today, "duration_minutes": 420, "quality": 4},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["duration_minutes"] == 420

    logs = client.get("/api/v1/health/sleep", headers=headers).json()
    assert len(logs) == 1


def test_sleep_duration_derived_from_bedtime_and_wake_time(client):
    headers = register_and_login(client)
    today = date.today().isoformat()

    response = client.post(
        "/api/v1/health/sleep",
        json={
            "sleep_date": today,
            "bedtime": "2026-10-04T23:00:00+00:00",
            "wake_time": "2026-10-05T06:30:00+00:00",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["duration_minutes"] == 450  # 7.5 hours


def test_today_summary_falls_back_to_yesterdays_sleep_if_not_yet_logged_today(client):
    headers = register_and_login(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    client.post(
        "/api/v1/health/sleep", json={"sleep_date": yesterday, "duration_minutes": 400}, headers=headers
    )

    summary = client.get("/api/v1/health/today", headers=headers).json()
    assert summary["last_night_sleep"]["duration_minutes"] == 400


def test_today_summary_does_not_surface_a_week_old_sleep_log_as_last_night(client):
    headers = register_and_login(client)
    long_ago = (date.today() - timedelta(days=10)).isoformat()

    client.post(
        "/api/v1/health/sleep", json={"sleep_date": long_ago, "duration_minutes": 400}, headers=headers
    )

    summary = client.get("/api/v1/health/today", headers=headers).json()
    assert summary["last_night_sleep"] is None


def test_workout_log_appears_in_today_summary(client):
    headers = register_and_login(client)

    client.post(
        "/api/v1/health/workouts",
        json={"activity_type": "Running", "duration_minutes": 30, "intensity": "high"},
        headers=headers,
    )

    summary = client.get("/api/v1/health/today", headers=headers).json()
    assert len(summary["workouts_today"]) == 1
    assert summary["workouts_today"][0]["activity_type"] == "Running"


def test_mood_log_and_latest_mood_in_today_summary(client):
    headers = register_and_login(client)

    client.post("/api/v1/health/mood", json={"mood": "low", "stress_level": 4}, headers=headers)
    client.post("/api/v1/health/mood", json={"mood": "good", "stress_level": 2}, headers=headers)

    summary = client.get("/api/v1/health/today", headers=headers).json()
    assert summary["latest_mood_today"]["mood"] == "good"


def test_user_cannot_access_another_users_health_logs(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    log = client.post(
        "/api/v1/health/diet", json={"meal_type": "lunch", "description": "Rice"}, headers=headers_a
    ).json()

    response = client.patch(
        f"/api/v1/health/diet/{log['id']}", json={"description": "Hacked"}, headers=headers_b
    )
    assert response.status_code == 404

    response = client.delete(f"/api/v1/health/diet/{log['id']}", headers=headers_b)
    assert response.status_code == 404


def test_invalid_meal_type_is_rejected(client):
    headers = register_and_login(client)
    response = client.post(
        "/api/v1/health/diet",
        json={"meal_type": "brunch", "description": "Not a real meal_type"},
        headers=headers,
    )
    assert response.status_code == 422
