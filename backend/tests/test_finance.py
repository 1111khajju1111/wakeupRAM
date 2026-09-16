from datetime import date

from tests.helpers import register_and_login


def _today_str() -> str:
    return date.today().isoformat()


def test_create_income_and_list(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/finance/income",
        json={"source": "Salary", "amount": 60000, "frequency": "monthly", "received_at": _today_str()},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["source"] == "Salary"

    incomes = client.get("/api/v1/finance/income", headers=headers).json()
    assert len(incomes) == 1


def test_create_expense_and_list(client):
    headers = register_and_login(client)

    response = client.post(
        "/api/v1/finance/expenses",
        json={"category": "groceries", "description": "Weekly shop", "amount": 2000, "spent_at": _today_str()},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["category"] == "groceries"

    expenses = client.get("/api/v1/finance/expenses", headers=headers).json()
    assert len(expenses) == 1


def test_setting_budget_twice_for_same_category_updates_not_duplicates(client):
    headers = register_and_login(client)

    client.post("/api/v1/finance/budgets", json={"category": "groceries", "monthly_limit": 8000}, headers=headers)
    response = client.post(
        "/api/v1/finance/budgets", json={"category": "groceries", "monthly_limit": 9000}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["monthly_limit"] == 9000

    budgets = client.get("/api/v1/finance/budgets", headers=headers).json()
    assert len(budgets) == 1


def test_summary_reflects_recurring_income_and_expenses(client):
    headers = register_and_login(client)

    # 60,000/month recurring income
    client.post(
        "/api/v1/finance/income",
        json={"source": "Salary", "amount": 60000, "frequency": "monthly", "received_at": _today_str()},
        headers=headers,
    )
    # 5,000/week recurring expense -> ~21,667/month
    client.post(
        "/api/v1/finance/expenses",
        json={
            "category": "rent",
            "description": "Weekly rent share",
            "amount": 5000,
            "frequency": "weekly",
            "spent_at": _today_str(),
        },
        headers=headers,
    )

    summary = client.get("/api/v1/finance/summary", headers=headers).json()
    assert summary["estimated_monthly_income"] == 60000
    assert round(summary["estimated_recurring_monthly_expenses"], 2) == round(5000 * 52 / 12, 2)
    assert summary["income_logged_this_month"] == 60000
    assert summary["expenses_logged_this_month"] == 5000


def test_budget_status_tracks_spend_against_limit(client):
    headers = register_and_login(client)

    client.post("/api/v1/finance/budgets", json={"category": "groceries", "monthly_limit": 8000}, headers=headers)
    client.post(
        "/api/v1/finance/expenses",
        json={"category": "groceries", "description": "Shop", "amount": 3000, "spent_at": _today_str()},
        headers=headers,
    )

    summary = client.get("/api/v1/finance/summary", headers=headers).json()
    groceries = next(b for b in summary["budgets"] if b["category"] == "groceries")
    assert groceries["spent_this_month"] == 3000
    assert groceries["remaining"] == 5000


def test_affordability_with_no_income_returns_unknown_not_a_guess(client):
    headers = register_and_login(client)

    response = client.post("/api/v1/finance/affordability", json={"amount": 10000}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_available_this_month"] is None
    assert body["likely_affordable"] is None
    assert any("No income" in c for c in body["caveats"])


def test_affordability_with_income_computes_available_and_verdict(client):
    headers = register_and_login(client)

    client.post(
        "/api/v1/finance/income",
        json={"source": "Salary", "amount": 60000, "frequency": "monthly", "received_at": _today_str()},
        headers=headers,
    )
    client.post(
        "/api/v1/finance/expenses",
        json={
            "category": "rent",
            "description": "Rent",
            "amount": 20000,
            "frequency": "monthly",
            "spent_at": _today_str(),
        },
        headers=headers,
    )

    response = client.post("/api/v1/finance/affordability", json={"amount": 50000}, headers=headers)
    body = response.json()
    # 60,000 income - 20,000 recurring rent baseline = 40,000 available.
    # This month's rent entry is recurring, so it's already represented by
    # its normalized monthly share and must NOT be subtracted again just
    # because it happens to have been logged this month.
    assert body["estimated_available_this_month"] == 40000
    assert body["likely_affordable"] is False

    response_afford = client.post("/api/v1/finance/affordability", json={"amount": 10000}, headers=headers)
    assert response_afford.json()["likely_affordable"] is True


def test_affordability_adds_one_time_expenses_on_top_of_recurring_baseline(client):
    headers = register_and_login(client)

    client.post(
        "/api/v1/finance/income",
        json={"source": "Salary", "amount": 60000, "frequency": "monthly", "received_at": _today_str()},
        headers=headers,
    )
    client.post(
        "/api/v1/finance/expenses",
        json={
            "category": "rent",
            "description": "Rent",
            "amount": 20000,
            "frequency": "monthly",
            "spent_at": _today_str(),
        },
        headers=headers,
    )
    # A genuinely separate, non-recurring expense logged this month SHOULD
    # reduce what's available — unlike the recurring rent entry above.
    client.post(
        "/api/v1/finance/expenses",
        json={
            "category": "misc",
            "description": "One-off repair",
            "amount": 5000,
            "frequency": "one_time",
            "spent_at": _today_str(),
        },
        headers=headers,
    )

    response = client.post("/api/v1/finance/affordability", json={"amount": 34000}, headers=headers)
    body = response.json()
    # 60,000 - 20,000 recurring - 5,000 one-time this month = 35,000 available.
    assert body["estimated_available_this_month"] == 35000
    assert body["likely_affordable"] is True


def test_relogging_the_same_recurring_expense_each_month_does_not_inflate_the_baseline(client):
    headers = register_and_login(client)
    today = date.today()

    for months_ago in range(3):
        spent_month = today.month - months_ago
        spent_year = today.year
        while spent_month <= 0:
            spent_month += 12
            spent_year -= 1
        spent_at = date(spent_year, spent_month, min(today.day, 28))
        client.post(
            "/api/v1/finance/expenses",
            json={
                "category": "subscriptions",
                "description": "Streaming service",
                "amount": 500,
                "frequency": "monthly",
                "spent_at": spent_at.isoformat(),
            },
            headers=headers,
        )

    summary = client.get("/api/v1/finance/summary", headers=headers).json()
    # Logged three separate months of the SAME recurring subscription — the
    # baseline should still read as one standing 500/month commitment, not
    # 1500 (3x) from summing every historical entry.
    assert summary["estimated_recurring_monthly_expenses"] == 500


def test_two_distinct_recurring_expenses_in_the_same_category_both_count(client):
    headers = register_and_login(client)

    client.post(
        "/api/v1/finance/expenses",
        json={
            "category": "subscriptions",
            "description": "Streaming service",
            "amount": 500,
            "frequency": "monthly",
            "spent_at": _today_str(),
        },
        headers=headers,
    )
    client.post(
        "/api/v1/finance/expenses",
        json={
            "category": "subscriptions",
            "description": "Music service",
            "amount": 150,
            "frequency": "monthly",
            "spent_at": _today_str(),
        },
        headers=headers,
    )

    summary = client.get("/api/v1/finance/summary", headers=headers).json()
    # Different `description` = a genuinely different recurring commitment,
    # so deduping by (category, description) must not collapse these into one.
    assert summary["estimated_recurring_monthly_expenses"] == 650


def test_financial_goal_progress_and_update(client):
    headers = register_and_login(client)

    created = client.post(
        "/api/v1/finance/goals",
        json={"title": "Emergency fund", "goal_type": "savings", "target_amount": 100000, "current_amount": 20000},
        headers=headers,
    ).json()
    assert created["status"] == "active"

    updated = client.patch(
        f"/api/v1/finance/goals/{created['id']}", json={"current_amount": 45000}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["current_amount"] == 45000

    summary = client.get("/api/v1/finance/summary", headers=headers).json()
    assert any(g["id"] == created["id"] for g in summary["active_goals"])


def test_user_cannot_access_another_users_finance_records(client):
    headers_a = register_and_login(client, email="a@example.com")
    headers_b = register_and_login(client, email="b@example.com")

    expense = client.post(
        "/api/v1/finance/expenses",
        json={"category": "misc", "description": "Something", "amount": 500, "spent_at": _today_str()},
        headers=headers_a,
    ).json()

    response = client.patch(
        f"/api/v1/finance/expenses/{expense['id']}", json={"description": "Hacked"}, headers=headers_b
    )
    assert response.status_code == 404

    response = client.delete(f"/api/v1/finance/expenses/{expense['id']}", headers=headers_b)
    assert response.status_code == 404


def test_invalid_frequency_is_rejected(client):
    headers = register_and_login(client)
    response = client.post(
        "/api/v1/finance/income",
        json={"source": "Salary", "amount": 1000, "frequency": "hourly", "received_at": _today_str()},
        headers=headers,
    )
    assert response.status_code == 422
