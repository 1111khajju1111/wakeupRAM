def _register(client, email="ram@example.com", password="strongpassword123"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def _login(client, email="ram@example.com", password="strongpassword123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_register_creates_user_and_profile(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ram@example.com"
    assert body["profile"]["preferred_language"] == "en"
    assert body["profile"]["onboarding_completed"] is False


def test_register_duplicate_email_rejected(client):
    _register(client)
    response = _register(client)
    assert response.status_code == 409


def test_login_wrong_password_rejected(client):
    _register(client)
    response = _login(client, password="wrong-password")
    assert response.status_code == 401


def test_login_success_returns_token_pair(client):
    _register(client)
    response = _login(client)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_me_requires_auth(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client):
    _register(client)
    token = _login(client).json()["access_token"]

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "ram@example.com"


def test_user_cannot_access_another_users_data_via_token(client):
    """
    Authorization test: a valid token for user A must never resolve to user B's
    data, and there is no endpoint that accepts a user_id from the client —
    /users/me always resolves strictly from the verified JWT subject.
    """
    _register(client, email="a@example.com")
    _register(client, email="b@example.com")

    token_a = _login(client, email="a@example.com").json()["access_token"]
    token_b = _login(client, email="b@example.com").json()["access_token"]

    resp_a = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token_a}"})
    resp_b = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token_b}"})

    assert resp_a.json()["email"] == "a@example.com"
    assert resp_b.json()["email"] == "b@example.com"
    assert resp_a.json()["id"] != resp_b.json()["id"]


def test_profile_update_only_changes_sent_fields(client):
    _register(client)
    token = _login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        "/api/v1/users/me/profile", json={"display_name": "Ram"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["display_name"] == "Ram"
    # untouched fields keep their defaults
    assert body["profile"]["preferred_language"] == "en"
    assert body["profile"]["theme_preference"] == "system"
