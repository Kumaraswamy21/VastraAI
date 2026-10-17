"""Authenticated account fixture for existing API contract tests."""

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from fashion_search.auth.security import current_user
from fashion_search.catalog.models import SearchSessionRecord, User
from fashion_search.core.db import get_engine

TEST_USER_ID = "00000000-0000-4000-8000-000000000001"


def fake_user() -> User:
    return User(
        id=TEST_USER_ID,
        email="api-test@example.com",
        email_verified_at=datetime.now(UTC),
        auth_version=0,
    )


def authorize(app) -> None:
    app.dependency_overrides[current_user] = fake_user


def ensure_test_user() -> None:
    with Session(get_engine()) as session, session.begin():
        if session.get(User, TEST_USER_ID) is None:
            session.add(fake_user())


def clear_test_sessions() -> None:
    with Session(get_engine()) as session, session.begin():
        session.execute(
            delete(SearchSessionRecord).where(
                SearchSessionRecord.user_id == TEST_USER_ID
            )
        )
