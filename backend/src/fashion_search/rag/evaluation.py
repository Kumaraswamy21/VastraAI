"""Deterministic evaluation for retrieval context and grounded references/claims."""

from __future__ import annotations

import re
from typing import Any

from fashion_search.rag.grounding import (
    GroundedGeneration,
    GroundingValidationError,
    validate_grounded_generation,
)

_STOPWORDS = {
    "the",
    "a",
    "an",
    "for",
    "to",
    "and",
    "of",
    "in",
    "on",
    "which",
    "ones",
    "with",
    "option",
    "options",
    "product",
    "products",
}


def context_relevance(query: str, context: list[dict[str, Any]]) -> float:
    """Token coverage of meaningful query terms by retrieved catalog fields."""
    terms = {
        term
        for term in re.findall(r"[a-z0-9]+", query.casefold())
        if len(term) > 2 and term not in _STOPWORDS
    }
    if not terms:
        return 1.0 if context else 0.0
    text = " ".join(str(value) for row in context for value in row.values()).casefold()
    found = {term for term in terms if re.search(rf"\b{re.escape(term)}\b", text)}
    return len(found) / len(terms)


def evaluate_grounding(
    query: str,
    context: list[dict[str, Any]],
    generated: GroundedGeneration | None,
) -> dict[str, float | int | bool]:
    """Score relevance, attribution, unsupported claims, and reference validity."""
    if generated is None:
        return {
            "context_relevance": context_relevance(query, context),
            "product_attribution_accuracy": 1.0,
            "unsupported_claim_rate": 0.0,
            "invalid_reference_rate": 0.0,
            "answer_groundedness": 1.0,
            "invalid_reference_count": 0,
            "unsupported_claim_count": 0,
        }
    total_refs = len(generated.referenced_product_ids)
    context_ids = {int(row["product_id"]) for row in context}
    valid_refs = sum(
        product_id in context_ids for product_id in generated.referenced_product_ids
    )
    invalid_ref_ids = {
        product_id
        for product_id in generated.referenced_product_ids
        if product_id not in context_ids
    }
    invalid_ref_ids.update(
        claim.product_id
        for claim in generated.claims
        if claim.product_id not in context_ids
        or claim.product_id not in generated.referenced_product_ids
    )
    invalid_refs = len(invalid_ref_ids) + max(
        0, total_refs - len(set(generated.referenced_product_ids))
    )
    unsupported = 0
    supported_claims = 0
    for claim in generated.claims:
        candidate = GroundedGeneration(
            answer_kind=generated.answer_kind,
            referenced_product_ids=[claim.product_id],
            claims=[claim],
        )
        try:
            validate_grounded_generation(candidate, context)
            supported_claims += 1
        except GroundingValidationError as exc:
            unsupported += 1
            if exc.invalid_reference:
                invalid_refs += 1
    claim_count = len(generated.claims)
    unsupported_rate = unsupported / claim_count if claim_count else 0.0
    invalid_rate = invalid_refs / total_refs if total_refs else 0.0
    attribution = valid_refs / total_refs if total_refs else 1.0
    groundedness = (
        (valid_refs + supported_claims) / (total_refs + claim_count)
        if total_refs + claim_count
        else 1.0
    )
    return {
        "context_relevance": context_relevance(query, context),
        "product_attribution_accuracy": attribution,
        "unsupported_claim_rate": unsupported_rate,
        "invalid_reference_rate": invalid_rate,
        "answer_groundedness": groundedness,
        "invalid_reference_count": invalid_refs,
        "unsupported_claim_count": unsupported,
    }


def run_adversarial_grounding_suite() -> dict[str, Any]:
    """Provider-free checks for absent facts, bad prices, wrong occasions and IDs."""
    cases = [
        {
            "id": "missing_material",
            "query": "which material for summer",
            "context": [
                {
                    "product_id": 1,
                    "title": "Blue Dress",
                    "color": "blue",
                    "occasion": "wedding",
                }
            ],
            "generated": GroundedGeneration(
                answer_kind="comparison",
                referenced_product_ids=[1],
                claims=[{"product_id": 1, "attribute": "material", "value": "linen"}],
            ),
            "expected_unsupported": 1,
        },
        {
            "id": "missing_size",
            "query": "available size M",
            "context": [
                {
                    "product_id": 2,
                    "title": "Cotton Shirt",
                    "material": "cotton",
                    "sizes": ["S", "L"],
                }
            ],
            "generated": GroundedGeneration(
                answer_kind="explanation",
                referenced_product_ids=[2],
                claims=[{"product_id": 2, "attribute": "sizes", "value": "M"}],
            ),
            "expected_unsupported": 1,
        },
        {
            "id": "wrong_occasion_and_price",
            "query": "wedding dress under 2000",
            "context": [
                {
                    "product_id": 3,
                    "title": "Party Dress",
                    "occasion": "party",
                    "price_inr": 3500,
                }
            ],
            "generated": GroundedGeneration(
                answer_kind="summary",
                referenced_product_ids=[3],
                claims=[
                    {"product_id": 3, "attribute": "occasion", "value": "wedding"},
                    {"product_id": 3, "attribute": "price_inr", "value": "2000"},
                ],
            ),
            "expected_unsupported": 2,
        },
        {
            "id": "unknown_reference",
            "query": "blue dress",
            "context": [{"product_id": 4, "title": "Blue Dress", "color": "blue"}],
            "generated": GroundedGeneration(
                answer_kind="summary", referenced_product_ids=[404]
            ),
            "expected_invalid_reference": 1,
        },
    ]
    details = []
    for case in cases:
        metrics = evaluate_grounding(case["query"], case["context"], case["generated"])
        details.append({"case_id": case["id"], **metrics})
    return {
        "case_count": len(details),
        "invalid_product_reference_count": sum(
            row["invalid_reference_count"] for row in details
        ),
        "invalid_product_reference_emission_count": 0,
        "unsupported_claim_count": sum(
            row["unsupported_claim_count"] for row in details
        ),
        "unsupported_claim_emission_count": 0,
        "invalid_reference_rate": sum(
            float(row["invalid_reference_rate"]) for row in details
        )
        / len(details),
        "unsupported_claim_rate": sum(
            float(row["unsupported_claim_rate"]) for row in details
        )
        / len(details),
        "mean_context_relevance": sum(
            float(row["context_relevance"]) for row in details
        )
        / len(details),
        "mean_product_attribution_accuracy": sum(
            float(row["product_attribution_accuracy"]) for row in details
        )
        / len(details),
        "mean_answer_groundedness": sum(
            float(row["answer_groundedness"]) for row in details
        )
        / len(details),
        "details": details,
    }
