"""
Test fixtures.

Uses an in-memory SQLite engine for fast, isolated tests instead of the real
Aiven PostgreSQL — good enough for auth/authorization logic since it goes
through the same SQLAlchemy models. Postgres-specific behavior (JSONB, etc.,
introduced in later phases) will need a real Postgres test database via
docker-compose instead.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app, limiter
from app import models as _models  # noqa: F401  ensures all tables register on Base.metadata


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # `app` (and therefore `limiter`) is a single module-level instance
    # shared by every test in the process — its in-memory request counters
    # don't know a new test function has started. Without this, whichever
    # test happens to run once the suite's cumulative request count crosses
    # RATE_LIMIT_DEFAULT within the same rolling window gets a spurious 429,
    # even though nothing about that test itself is wrong. Real rate-limit
    # behavior within a single test (if one is ever written to check it) is
    # unaffected — this only clears state *between* tests.
    limiter.reset()
    yield


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
