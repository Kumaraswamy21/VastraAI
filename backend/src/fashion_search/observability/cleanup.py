"""Delete telemetry older than the configured retention period."""

from fashion_search.observability.repository import repository


def main() -> None:
    result = repository.cleanup()
    print(
        f"Deleted {result['ai_provider_events']} provider events and "
        f"{result['search_events']} search events."
    )
