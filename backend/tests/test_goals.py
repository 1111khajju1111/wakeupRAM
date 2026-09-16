from tests.helpers import register_and_login


def test_create_and_list_goal(client):
    headers = register_and_login(client)

    response = client.post("/api/v1/goals", json={"title": "Quit smoking"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["status"] == "active"

    response = client.get("/api/v1/goals", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Quit smoking"


def test_update_goal_status(client):
    headers = register_and_login(client)
    goal = client.post("/api/v1/goals", json={"title": "Finish BTech project"}, headers=headers).json()

    response = client.patch(
        f"/api/v1/goals/{goal['id']}", json={"status": "completed"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_goal_not_found_for_unknown_id(client):
    headers = register_and_login(client)
    response = client.get("/api/v1/goals/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 404


def test_user_cannot_read_another_users_goal(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    goal = client.post("/api/v1/goals", json={"title": "A's private goal"}, headers=headers_a).json()

    response = client.get(f"/api/v1/goals/{goal['id']}", headers=headers_b)
    assert response.status_code == 404  # not 403 — existence isn't leaked either


def test_user_cannot_delete_another_users_goal(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    goal = client.post("/api/v1/goals", json={"title": "A's goal"}, headers=headers_a).json()

    response = client.delete(f"/api/v1/goals/{goal['id']}", headers=headers_b)
    assert response.status_code == 404

    # still there for its actual owner
    still_there = client.get(f"/api/v1/goals/{goal['id']}", headers=headers_a)
    assert still_there.status_code == 200
