"""Grounded generation over retrieved, exact-filtered hybrid search results."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from fashion_search.config.settings import Settings, get_settings
from fashion_search.generation.base import GenerationProvider
from fashion_search.generation.router import GenerationRouter
from fashion_search.prompts import load_prompt
from fashion_search.rag.context import build_retrieval_context, context_size_chars
from fashion_search.rag.grounding import (
    GroundedGeneration,
    GroundingValidationError,
    render_grounded_answer,
    validate_grounded_generation,
)
from fashion_search.search.schemas import FashionSearchConstraints, HybridSearchResult

_CONTEXT_QUESTION = re.compile(
    r"\b(which|compare|comparison|better|best|why|what makes|how does|summer|winter|"
    r"rain|warm|lightweight|material|fabric|difference|explain)\b",
    re.IGNORECASE,
)


def needs_grounded_answer(message: str) -> bool:
    """Only product-context questions benefit from a generation call."""
    return bool(_CONTEXT_QUESTION.search(message or ""))


@dataclass(frozen=True)
class RagAnswerResult:
    answer: str
    referenced_product_ids: list[int]
    generation_latency_ms: float
    total_latency_ms: float
    context_count: int
    context_size_chars: int
    generation_provider: str | None
    generation_model: str | None
    grounding_failure: bool = False
    invalid_product_reference: bool = False


def generate_grounded_answer(
    message: str,
    constraints: FashionSearchConstraints,
    products: list[HybridSearchResult],
    *,
    settings: Settings | None = None,
    provider: GenerationProvider | None = None,
) -> RagAnswerResult:
    """Generate claim selections from compact retrieved context and validate them."""
    cfg = settings or get_settings()
    if not products:
        return RagAnswerResult(
            answer="",
            referenced_product_ids=[],
            generation_latency_ms=0.0,
            total_latency_ms=0.0,
            context_count=0,
            context_size_chars=0,
            generation_provider=None,
            generation_model=None,
        )
    total_started = time.perf_counter()
    context = build_retrieval_context(
        products,
        top_k=cfg.rag_context_top_k,
        description_max_chars=cfg.rag_description_max_chars,
    )
    size = context_size_chars(context)
    context_ids = [int(row["product_id"]) for row in context]
    worker = provider or GenerationRouter(settings=cfg)
    started = time.perf_counter()
    failure = False
    invalid_reference = False
    refs = context_ids
    answer = f"I found {len(context_ids)} option{'s' if len(context_ids) != 1 else ''} matching your preferences."
    try:
        prompt = json.dumps(
            {
                "user_question": message,
                "confirmed_hard_filters": constraints.model_dump(
                    mode="json", exclude_none=True
                ),
                "retrieved_products": context,
                "instructions": "Select only supplied product IDs. Return claims only when the exact field value appears in that product. Do not infer missing attributes. The server composes final prose from validated claims.",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        generated = worker.generate_structured(
            prompt,
            GroundedGeneration,
            system_prompt=load_prompt("system_rag_grounded"),
        )
        generated = validate_grounded_generation(generated, context)
        refs = generated.referenced_product_ids
        answer = render_grounded_answer(generated, context)
    except GroundingValidationError as exc:
        failure = True
        invalid_reference = exc.invalid_reference
    except Exception:
        # Retrieval remains useful if the generation provider or structured output fails.
        failure = True
    latency = (time.perf_counter() - started) * 1000
    return RagAnswerResult(
        answer=answer,
        referenced_product_ids=refs,
        generation_latency_ms=latency,
        total_latency_ms=(time.perf_counter() - total_started) * 1000,
        context_count=len(context),
        context_size_chars=size,
        generation_provider=getattr(worker, "name", None),
        generation_model=getattr(worker, "model_name", None),
        grounding_failure=failure,
        invalid_product_reference=invalid_reference,
    )
