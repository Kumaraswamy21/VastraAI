"""Authentication boundary and account-owned session tests."""

from __future__ import annotations

import os
import re
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from fashion_search.api.auth import _hash_password, _verify_password
from fashion_search.catalog.models import User
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine
from fashion_search.main import app
from fashion_search.search.conversation import RevisionConflictError
from fashion_search.search.schemas import SearchState
from fashion_search.search.sessions import search_session_store

SECRET = "test-auth-secret-long-enough-for-hmac-123456789"


def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=os.environ.get("DATABASE_URL", "postgresql://unused"),
        auth_jwt_secret=SECRET,
        auth_frontend_url="http://localhost:3000",
    )


class AuthBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_settings] = test_settings
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_password_hash_is_salted_and_verifies(self) -> None:
        first = _hash_password("a-long-example-password")
        second = _hash_password("a-long-example-password")
        self.assertNotEqual(first, second)
        self.assertTrue(_verify_password("a-long-example-password", first))
        self.assertFalse(_verify_password("incorrect-password", first))

    def test_search_rejects_missing_forged_and_service_identity(self) -> None:
        self.assertEqual(
            self.client.post("/search", json={"query": "dress"}).status_code, 401
        )
        now = datetime.now(UTC)
        claims = {
            "sub": str(uuid4()),
            "iss": "vastraai-web",
            "aud": "vastraai-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "sv": 0,
        }
        forged = jwt.encode(
            claims, "another-long-secret-for-test-signatures-123", algorithm="HS256"
        )
        response = self.client.post(
            "/search",
            json={"query": "dress"},
            headers={"Authorization": f"Bearer {forged}"},
        )
        self.assertEqual(response.status_code, 401)
        service = jwt.encode(
            {**claims, "sub": "nextauth", "scope": "account:sync"},
            SECRET,
            algorithm="HS256",
        )
        response = self.client.post(
            "/search",
            json={"query": "dress"},
            headers={"Authorization": f"Bearer {service}"},
        )
        self.assertEqual(response.status_code, 401)


@unittest.skipUnless(
    os.environ.get("APP_ENVIRONMENT") == "test" and os.environ.get("DATABASE_URL"),
    "Disposable migrated test database required",
)
class AuthDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_settings] = test_settings
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.email = f"auth-{uuid4().hex}@example.com"
        self.addCleanup(self._delete_user)

    def _delete_user(self) -> None:
        with Session(get_engine()) as session, session.begin():
            session.execute(delete(User).where(User.email == self.email))

    def test_email_verification_password_login_and_reset(self) -> None:
        with patch("fashion_search.api.auth._send_email") as send:
            response = self.client.post(
                "/auth/register",
                json={"email": self.email, "password": "original-password-123"},
            )
        self.assertEqual(response.status_code, 202)
        link = send.call_args.kwargs["body"]
        token = re.search(r"token=([^\s]+)", link).group(1)
        self.assertEqual(
            self.client.post(
                "/auth/login",
                json={"email": self.email, "password": "original-password-123"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/auth/verify-email", json={"token": token}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/auth/verify-email", json={"token": token}).status_code,
            400,
        )
        logged_in = self.client.post(
            "/auth/login",
            json={"email": self.email, "password": "original-password-123"},
        )
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(logged_in.json()["auth_version"], 0)

        with patch("fashion_search.api.auth._send_email") as send:
            self.assertEqual(
                self.client.post(
                    "/auth/password-reset/request", json={"email": self.email}
                ).status_code,
                202,
            )
        reset_token = re.search(r"token=([^\s]+)", send.call_args.kwargs["body"]).group(
            1
        )
        self.assertEqual(
            self.client.post(
                "/auth/password-reset/confirm",
                json={"token": reset_token, "password": "replacement-password-123"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/auth/login",
                json={"email": self.email, "password": "original-password-123"},
            ).status_code,
            401,
        )
        renewed = self.client.post(
            "/auth/login",
            json={"email": self.email, "password": "replacement-password-123"},
        )
        self.assertEqual(renewed.json()["auth_version"], 1)

    def test_sessions_are_owner_scoped_and_revisions_are_atomic(self) -> None:
        with Session(get_engine()) as session, session.begin():
            user = User(email=self.email, email_verified_at=datetime.now(UTC))
            session.add(user)
            session.flush()
            user_id = user.id
        state = SearchState(
            original_query="dress", current_query="dress", semantic_query="dress"
        )
        session_id, _ = search_session_store.create(user_id, state)
        self.assertIsNone(search_session_store.get(str(uuid4()), session_id))
        self.assertEqual(search_session_store.get(user_id, session_id).revision, 0)
        next_state = state.model_copy(update={"revision": 1})
        search_session_store.commit(
            user_id, session_id, next_state, expected_revision=0
        )
        self.assertEqual(search_session_store.get(user_id, session_id).revision, 1)
        with self.assertRaises(RevisionConflictError):
            search_session_store.commit(
                user_id, session_id, next_state, expected_revision=0
            )

    def test_google_identity_links_only_to_matching_verified_email(self) -> None:
        with Session(get_engine()) as session, session.begin():
            user = User(
                email=self.email,
                email_verified_at=datetime.now(UTC),
                password_hash=_hash_password("original-password-123"),
            )
            session.add(user)
            session.flush()
            user_id = user.id
        now = datetime.now(UTC)
        service = jwt.encode(
            {
                "sub": "nextauth",
                "scope": "account:sync",
                "iss": "vastraai-web",
                "aud": "vastraai-api",
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            SECRET,
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {service}"}
        linked = self.client.post(
            "/auth/google",
            json={"subject": "google-subject-1", "email": self.email},
            headers=headers,
        )
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(linked.json()["id"], user_id)
        conflict = self.client.post(
            "/auth/google",
            json={"subject": "google-subject-2", "email": self.email},
            headers=headers,
        )
        self.assertEqual(conflict.status_code, 409)
