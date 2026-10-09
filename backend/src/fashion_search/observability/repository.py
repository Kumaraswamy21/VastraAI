"""Fail-open telemetry persistence and bounded PostgreSQL analytics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine
from fashion_search.core.logging import get_logger
from fashion_search.observability.models import AIProviderEvent, SearchEvent
from fashion_search.observability.schemas import AIProviderEventData, SearchEventData

logger = get_logger(__name__)


class TelemetryRepository:
    def __init__(self, settings: Settings | None = None, engine=None) -> None:
        self.settings = settings or get_settings()
        self.engine = engine

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.settings, "observability_enabled", True))

    def _engine(self):
        return self.engine or get_engine()

    def record_provider(self, event: AIProviderEventData) -> None:
        if not self.enabled:
            return
        try:
            payload = event.model_dump(exclude={"metadata"})
            with Session(self._engine()) as session:
                session.add(AIProviderEvent(**payload, event_metadata=event.metadata))
                session.commit()
        except Exception as exc:
            logger.warning("telemetry_provider_write_failed error_type=%s", type(exc).__name__)

    def record_search(self, event: SearchEventData) -> None:
        if not self.enabled:
            return
        try:
            with Session(self._engine()) as session:
                session.add(SearchEvent(**event.model_dump()))
                session.commit()
        except Exception as exc:
            logger.warning("telemetry_search_write_failed error_type=%s", type(exc).__name__)

    def cleanup(self, retention_days: int | None = None) -> dict[str, int]:
        days = retention_days or self.settings.observability_retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with Session(self._engine()) as session:
            ai = session.execute(delete(AIProviderEvent).where(AIProviderEvent.timestamp < cutoff)).rowcount
            searches = session.execute(delete(SearchEvent).where(SearchEvent.timestamp < cutoff)).rowcount
            session.commit()
        return {"ai_provider_events": ai or 0, "search_events": searches or 0}

    def query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with self._engine().connect() as connection:
            return [dict(row) for row in connection.execute(text(sql), params).mappings()]

    def summary(self, since: datetime) -> dict[str, Any]:
        sql = """
        SELECT
          (SELECT count(*) FROM ai_provider_events WHERE timestamp >= :since) ai_requests,
          (SELECT count(*) FROM ai_provider_events WHERE timestamp >= :since AND outcome='SUCCESS') ai_successes,
          (SELECT avg(latency_ms) FROM ai_provider_events WHERE timestamp >= :since) ai_avg_latency_ms,
          (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) FROM ai_provider_events WHERE timestamp >= :since) ai_p50_latency_ms,
          (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) FROM ai_provider_events WHERE timestamp >= :since) ai_p95_latency_ms,
          (SELECT sum(total_tokens) FROM ai_provider_events WHERE timestamp >= :since) total_tokens,
          (SELECT sum(estimated_cost) FROM ai_provider_events WHERE timestamp >= :since) estimated_api_cost,
          (SELECT count(*) FROM ai_provider_events WHERE timestamp >= :since AND fallback_used) fallback_count,
          (SELECT count(*) FROM search_events WHERE timestamp >= :since) search_requests,
          (SELECT count(*) FROM search_events WHERE timestamp >= :since AND outcome='SUCCESS') search_successes,
          (SELECT count(*) FROM search_events WHERE timestamp >= :since AND final_result_count=0) zero_result_searches,
          (SELECT avg(total_latency_ms) FROM search_events WHERE timestamp >= :since) search_avg_latency_ms,
          (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_latency_ms) FROM search_events WHERE timestamp >= :since) search_p50_latency_ms,
          (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms) FROM search_events WHERE timestamp >= :since) search_p95_latency_ms,
          (SELECT avg(final_result_count) FROM search_events WHERE timestamp >= :since) avg_result_count
          ,(SELECT count(*) FROM search_events WHERE timestamp >= :since AND search_mode='HYBRID') hybrid_searches
          ,(SELECT count(*) FROM search_events WHERE timestamp >= :since AND search_mode='KEYWORD_FALLBACK') keyword_fallback_searches
        """
        rows = self.query(sql, {"since": since})
        return rows[0] if rows else {}

    def providers(self, since: datetime, filters: dict[str, Any]) -> list[dict[str, Any]]:
        clauses = ["timestamp >= :since"]
        params = {"since": since}
        for key in ("provider", "model", "operation", "outcome"):
            if filters.get(key):
                clauses.append(f"{key} = :{key}")
                params[key] = filters[key]
        return self.query(f"""
          SELECT provider, model, operation, count(*) requests,
            count(*) FILTER (WHERE outcome='SUCCESS') successes,
            avg(latency_ms) avg_latency_ms,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) p50_latency_ms,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) p95_latency_ms,
            sum(total_tokens) total_tokens, sum(estimated_cost) estimated_api_cost,
            count(*) FILTER (WHERE fallback_used) fallback_count
          FROM ai_provider_events WHERE {" AND ".join(clauses)}
          GROUP BY provider, model, operation ORDER BY requests DESC LIMIT 100
        """, params)

    def recent_providers(self, since: datetime, filters: dict[str, Any]) -> list[dict[str, Any]]:
        clauses = ["timestamp >= :since"]
        params = {"since": since}
        for key in ("provider", "model", "operation", "outcome"):
            if filters.get(key):
                clauses.append(f"{key} = :{key}")
                params[key] = filters[key]
        return self.query(f"""
          SELECT timestamp, request_id, search_request_id, provider, model, operation,
            outcome, latency_ms, total_tokens, estimated_cost, cost_currency,
            error_type, fallback_used
          FROM ai_provider_events WHERE {" AND ".join(clauses)}
          ORDER BY timestamp DESC LIMIT 100
        """, params)

    def searches(self, since: datetime, mode: str | None = None) -> dict[str, Any]:
        clause = "timestamp >= :since" + (" AND search_mode=:mode" if mode else "")
        params = {"since": since, "mode": mode}
        stages = ["constraint_parsing_ms", "query_embedding_ms", "semantic_search_ms", "keyword_search_ms", "fusion_ms", "explanation_ms"]
        expressions = []
        for stage in stages:
            expressions.extend([
                f"avg({stage}) AS {stage}_avg",
                f"percentile_cont(0.5) WITHIN GROUP (ORDER BY {stage}) AS {stage}_p50",
                f"percentile_cont(0.95) WITHIN GROUP (ORDER BY {stage}) AS {stage}_p95",
            ])
        stage_rows = self.query(f"SELECT {', '.join(expressions)} FROM search_events WHERE {clause}", params)
        modes = self.query(f"SELECT search_mode, count(*) count FROM search_events WHERE {clause} GROUP BY search_mode ORDER BY count DESC", params)
        recent = self.query(f"SELECT timestamp, request_id, search_mode, outcome, total_latency_ms, final_result_count, fallback_used FROM search_events WHERE {clause} ORDER BY timestamp DESC LIMIT 100", params)
        return {"stages": stage_rows[0] if stage_rows else {}, "modes": modes, "recent": recent}

    def request_detail(self, request_id: str) -> dict[str, Any] | None:
        searches = self.query("SELECT * FROM search_events WHERE request_id=:id LIMIT 1", {"id": request_id})
        providers = self.query("SELECT timestamp, provider, model, operation, outcome, latency_ms, input_tokens, output_tokens, total_tokens, estimated_cost, cost_currency, error_type, fallback_used FROM ai_provider_events WHERE search_request_id=:id ORDER BY timestamp, id LIMIT 100", {"id": request_id})
        if not searches and not providers:
            return None
        return {"search": searches[0] if searches else None, "provider_events": providers}


repository = TelemetryRepository()
