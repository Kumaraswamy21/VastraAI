"""Ranked retrieval metrics for graded product judgments."""

from __future__ import annotations

import math


def precision_at_k(
    ranked_ids: list[int], relevance: dict[int, int], k: int = 5
) -> float:
    """Precision divides by K even when fewer than K products are returned."""
    if k < 1:
        raise ValueError("k must be positive")
    return sum(relevance.get(product_id, 0) > 0 for product_id in ranked_ids[:k]) / k


def recall_at_k(
    ranked_ids: list[int], relevance: dict[int, int], k: int = 10
) -> float | None:
    """Recall against known relevant IDs; caller must require complete labels."""
    relevant = {product_id for product_id, grade in relevance.items() if grade > 0}
    if k < 1:
        raise ValueError("k must be positive")
    if not relevant:
        return None
    return len(relevant.intersection(ranked_ids[:k])) / len(relevant)


def reciprocal_rank(ranked_ids: list[int], relevance: dict[int, int]) -> float:
    for rank, product_id in enumerate(ranked_ids, start=1):
        if relevance.get(product_id, 0) > 0:
            return 1.0 / rank
    return 0.0


def dcg_at_k(ranked_ids: list[int], relevance: dict[int, int], k: int = 10) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    return sum(
        (2 ** relevance.get(product_id, 0) - 1) / math.log2(rank + 1)
        for rank, product_id in enumerate(ranked_ids[:k], start=1)
    )


def ndcg_at_k(ranked_ids: list[int], relevance: dict[int, int], k: int = 10) -> float:
    ideal = sorted(relevance.values(), reverse=True)[:k]
    ideal_ids = list(range(len(ideal)))
    ideal_relevance = {
        product_id: grade for product_id, grade in zip(ideal_ids, ideal, strict=True)
    }
    denominator = dcg_at_k(ideal_ids, ideal_relevance, k)
    if denominator == 0:
        return 0.0
    return dcg_at_k(ranked_ids, relevance, k) / denominator
