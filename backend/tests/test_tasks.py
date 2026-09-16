from datetime import date

from tests.helpers import register_and_login


def test_create_task_and_complete_it(client):
    headers = register_and_login(client)
    today = date.today().isoformat()

    task = client.post(
        "/api/v1/tasks", json={"title": "Morning run", "due_date": today}, headers=headers
    ).json()
    assert task["status"] == "pending"

    response = client.post(f"/api/v1/tasks/{task['id']}/logs", json={"action": "completed"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_only_one_daily_mission_per_day(client):
    headers = register_and_login(client)
    today = date.today().isoformat()

    first = client.post(
        "/api/v1/tasks",
        json={"title": "Study session", "due_date": today, "is_daily_mission": True},
        headers=headers,
    ).json()
    second = client.post(
        "/api/v1/tasks",
        json={"title": "Gym", "due_date": today, "is_daily_mission": True},
        headers=headers,
    ).json()

    refreshed_first = client.get(f"/api/v1/tasks/{first['id']}", headers=headers).json()
    assert refreshed_first["is_daily_mission"] is False
    assert second["is_daily_mission"] is True


def test_today_endpoint_returns_mission_and_habit_and_goal_count(client):
    headers = register_and_login(client)
    today = date.today().isoformat()

    client.post("/api/v1/goals", json={"title": "Get disciplined"}, headers=headers)
    client.post(
        "/api/v1/tasks",
        json={"title": "Deep work block", "due_date": today, "is_daily_mission": True},
        headers=headers,
    )
    client.post("/api/v1/habits", json={"title": "Drink water", "frequency": "daily"}, headers=headers)

    response = client.get("/api/v1/today", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["mission"]["title"] == "Deep work block"
    assert body["active_goals_count"] == 1
    assert len(body["habits_due_today"]) == 1
    assert body["habits_due_today"][0]["current_streak"] == 0


def test_user_cannot_log_action_on_another_users_task(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    task = client.post("/api/v1/tasks", json={"title": "A's task"}, headers=headers_a).json()

    response = client.post(f"/api/v1/tasks/{task['id']}/logs", json={"action": "completed"}, headers=headers_b)
    assert response.status_code == 404
