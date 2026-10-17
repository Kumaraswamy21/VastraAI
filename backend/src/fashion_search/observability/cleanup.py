"""Delete telemetry older than the configured retention period."""

from fashion_search.observability.repository import repository
from fashion_search.search.sessions import search_session_store


def main() -> None:
    result = repository.cleanup()
    auth_result = search_session_store.cleanup()
    print(
        f"Deleted {result['ai_provider_events']} provider events and "
        f"{result['search_events']} search events; "
        f"{auth_result['search_sessions']} search sessions, "
        f"{auth_result['auth_tokens']} auth tokens, and "
        f"{auth_result['auth_rate_limits']} rate-limit counters."
    )
