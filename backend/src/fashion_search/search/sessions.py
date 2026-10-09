"""Lightweight process-local search session storage with optimistic locking."""

from __future__ import annotations

from threading import RLock
from uuid import uuid4

from fashion_search.search.conversation import RevisionConflictError
from fashion_search.search.schemas import SearchState


class SearchSessionStore:
    """Store validated structured state; suitable for the current single-service milestone."""

    def __init__(self) -> None:
        self._states: dict[str, SearchState] = {}
        self._lock = RLock()

    def create(self, state: SearchState) -> tuple[str, SearchState]:
        session_id = str(uuid4())
        with self._lock:
            self._states[session_id] = state.model_copy(deep=True)
        return session_id, state

    def get(self, session_id: str) -> SearchState | None:
        with self._lock:
            state = self._states.get(session_id)
            return state.model_copy(deep=True) if state else None

    def commit(self, session_id: str, state: SearchState, *, expected_revision: int) -> None:
        with self._lock:
            current = self._states.get(session_id)
            if current is None:
                raise KeyError(session_id)
            if current.revision != expected_revision:
                raise RevisionConflictError(
                    f"stale search state: expected revision {expected_revision}, "
                    f"current revision is {current.revision}"
                )
            self._states[session_id] = state.model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()


search_session_store = SearchSessionStore()
