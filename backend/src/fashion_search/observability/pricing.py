"""Configurable, explicitly estimated API pricing."""

import json
from decimal import Decimal

from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.observability.schemas import AIUsage, ModelPricing

logger = get_logger(__name__)


class PricingCatalog:
    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self._entries: dict[tuple[str, str], ModelPricing] = {}
        try:
            payload = json.loads(getattr(cfg, "observability_pricing_json", "{}"))
            rows = payload.get("models", []) if isinstance(payload, dict) else []
            for raw in rows:
                item = ModelPricing.model_validate(raw)
                self._entries[(item.provider, item.model)] = item
        except Exception as exc:
            logger.warning(
                "observability_pricing_invalid error_type=%s", type(exc).__name__
            )

    def estimate(
        self, provider: str, model: str, operation: str, usage: AIUsage
    ) -> tuple[Decimal | None, str | None, str | None]:
        item = self._entries.get((provider, model))
        if item is None or provider == "ollama":
            return None, None, None
        million = Decimal("1000000")
        cost = Decimal("0")
        calculable = False
        if operation in {"query_embedding", "document_embedding"}:
            if (
                usage.total_tokens is not None
                and item.embedding_cost_per_million_tokens is not None
            ):
                cost += (
                    Decimal(usage.total_tokens)
                    * item.embedding_cost_per_million_tokens
                    / million
                )
                calculable = True
        else:
            if (
                item.input_cost_per_million_tokens is not None
                and usage.input_tokens is None
            ):
                return None, None, None
            if (
                item.output_cost_per_million_tokens is not None
                and usage.output_tokens is None
            ):
                return None, None, None
            if (
                usage.input_tokens is not None
                and item.input_cost_per_million_tokens is not None
            ):
                cost += (
                    Decimal(usage.input_tokens)
                    * item.input_cost_per_million_tokens
                    / million
                )
                calculable = True
            if (
                usage.output_tokens is not None
                and item.output_cost_per_million_tokens is not None
            ):
                cost += (
                    Decimal(usage.output_tokens)
                    * item.output_cost_per_million_tokens
                    / million
                )
                calculable = True
        return (
            (cost, item.currency, item.effective_date)
            if calculable
            else (None, None, None)
        )
