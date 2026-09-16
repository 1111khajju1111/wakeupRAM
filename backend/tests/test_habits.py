from datetime import date, timedelta

from tests.helpers import register_and_login


def test_create_habit_and_log_completion(client):
    headers = register_and_login(client)

    habit = client.post(
        "/api/v1/habits", json={"title": "No smoking today", "frequency": "daily"}, headers=headers
    ).json()
    assert habit["current_streak"] == 0
    assert habit["completed_today"] is False

    response = client.post(f"/api/v1/habits/{habit['id']}/logs", json={}, headers=headers)
    assert response.status_code == 201
    assert response.json()["completed_on"] == date.today().isoformat()


def test_logging_same_day_twice_is_idempotent(client):
    headers = register_and_login(client)
    habit = client.post("/api/v1/habits", json={"title": "Read"}, headers=headers).json()

    client.post(f"/api/v1/habits/{habit['id']}/logs", json={"notes": "first"}, headers=headers)
    client.post(f"/api/v1/habits/{habit['id']}/logs", json={"notes": "second"}, headers=headers)

    habits = client.get("/api/v1/habits", headers=headers).json()
    assert habits[0]["current_streak"] == 1  # not 2 — same day logged twice


def test_streak_breaks_on_missed_day(client):
    headers = register_and_login(client)
    habit = client.post("/api/v1/habits", json={"title": "Meditate"}, headers=headers).json()

    two_days_ago = (date.today() - timedelta(days=2)).isoformat()
    client.post(f"/api/v1/habits/{habit['id']}/logs", json={"completed_on": two_days_ago}, headers=headers)
    # yesterday and today are NOT logged, so streak should be 0

    habits = client.get("/api/v1/habits", headers=headers).json()
    assert habits[0]["current_streak"] == 0


def test_weekly_habit_due_today_uses_repeat_days(client):
    headers = register_and_login(client)
    today_sunday_indexed = (date.today().weekday() + 1) % 7

    client.post(
        "/api/v1/habits",
        json={"title": "Weekly review", "frequency": "weekly", "repeat_days": [today_sunday_indexed]},
        headers=headers,
    )

    today_view = client.get("/api/v1/today", headers=headers).json()
    assert len(today_view["habits_due_today"]) == 1


def test_user_cannot_log_another_users_habit(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    habit = client.post("/api/v1/habits", json={"title": "A's habit"}, headers=headers_a).json()

    response = client.post(f"/api/v1/habits/{habit['id']}/logs", json={}, headers=headers_b)
    assert response.status_code == 404
