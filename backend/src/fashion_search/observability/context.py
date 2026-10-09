"""Context-local request correlation without plumbing IDs through business APIs."""

from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
search_request_id_var: ContextVar[str | None] = ContextVar("search_request_id", default=None)
fallback_used_var: ContextVar[bool] = ContextVar("fallback_used", default=False)


def request_id() -> str:
    return request_id_var.get() or str(uuid4())


@contextmanager
def search_context(value: str | None = None):
    identifier = value or request_id()
    token = search_request_id_var.set(identifier)
    try:
        yield identifier
    finally:
        search_request_id_var.reset(token)


@contextmanager
def fallback_context():
    token = fallback_used_var.set(True)
    try:
        yield
    finally:
        fallback_used_var.reset(token)
