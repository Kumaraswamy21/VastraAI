"""Durable, owner-scoped search session storage with atomic revisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from fashion_search.catalog.models import AuthRateLimit, AuthToken, SearchSessionRecord
from fashion_search.core.db import get_engine
from fashion_search.search.conversation import RevisionConflictError
from fashion_search.search.schemas import SearchState

SESSION_TTL_DAYS = 30


class SearchSessionStore:
    """Persist search state and enforce account ownership at every operation."""

    def create(self, user_id: str, state: SearchState) -> tuple[str, SearchState]:
        session_id = str(uuid4())
        with Session(get_engine()) as session, session.begin():
            session.add(
                SearchSessionRecord(
                    id=session_id,
                    user_id=user_id,
                    state=state.model_dump(mode="json"),
                    expires_at=datetime.now(UTC) + timedelta(days=SESSION_TTL_DAYS),
                )
            )
        return session_id, state

    def get(self, user_id: str, session_id: str) -> SearchState | None:
        now = datetime.now(UTC)
        with Session(get_engine()) as session, session.begin():
            session.execute(
                delete(SearchSessionRecord).where(
                    SearchSessionRecord.id == session_id,
                    SearchSessionRecord.user_id == user_id,
                    SearchSessionRecord.expires_at <= now,
                )
            )
            row = session.scalar(
                select(SearchSessionRecord).where(
                    SearchSessionRecord.id == session_id,
                    SearchSessionRecord.user_id == user_id,
                    SearchSessionRecord.expires_at > now,
                )
            )
            if row is None:
                return None
            row.expires_at = now + timedelta(days=SESSION_TTL_DAYS)
            return SearchState.model_validate(row.state)

    def commit(
        self,
        user_id: str,
        session_id: str,
        state: SearchState,
        *,
        expected_revision: int,
    ) -> None:
        with Session(get_engine()) as session, session.begin():
            result = session.execute(
                update(SearchSessionRecord)
                .where(
                    SearchSessionRecord.id == session_id,
                    SearchSessionRecord.user_id == user_id,
                    SearchSessionRecord.expires_at > datetime.now(UTC),
                    SearchSessionRecord.state["revision"].astext
                    == str(expected_revision),
                )
                .values(
                    state=state.model_dump(mode="json"),
                    expires_at=datetime.now(UTC) + timedelta(days=SESSION_TTL_DAYS),
                    updated_at=datetime.now(UTC),
                )
            )
            if result.rowcount != 1:
                exists = session.scalar(
                    select(SearchSessionRecord.id).where(
                        SearchSessionRecord.id == session_id,
                        SearchSessionRecord.user_id == user_id,
                        SearchSessionRecord.expires_at > datetime.now(UTC),
                    )
                )
                if exists is None:
                    raise KeyError(session_id)
                raise RevisionConflictError("stale search state")

    def cleanup(self) -> dict[str, int]:
        """Remove expired sessions, one-time tokens, and old throttle counters."""
        now = datetime.now(UTC)
        with Session(get_engine()) as session, session.begin():
            sessions = (
                session.execute(
                    delete(SearchSessionRecord).where(
                        SearchSessionRecord.expires_at <= now
                    )
                ).rowcount
                or 0
            )
            tokens = (
                session.execute(
                    delete(AuthToken).where(AuthToken.expires_at <= now)
                ).rowcount
                or 0
            )
            limits = (
                session.execute(
                    delete(AuthRateLimit).where(
                        AuthRateLimit.window_start < now - timedelta(days=1)
                    )
                ).rowcount
                or 0
            )
        return {
            "search_sessions": sessions,
            "auth_tokens": tokens,
            "auth_rate_limits": limits,
        }


search_session_store = SearchSessionStore()
