"""Reciprocal Rank Fusion for hybrid semantic + keyword rankings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankedCandidate:
    """One product after RRF with source ranks preserved."""

    product_id: int
    hybrid_score: float
    semantic_rank: int | None
    keyword_rank: int | None
    semantic_similarity: float | None
    keyword_rank_score: float | None


def reciprocal_rank_fusion(
    semantic: list[tuple[int, float]],
    keyword: list[tuple[int, float]],
    *,
    rrf_k: int = 60,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> list[RankedCandidate]:
    """Merge two ranked lists by product ID using weighted RRF.

    Each input list is ``(product_id, score)`` in best-first order.
    Ranks are 1-based positions within each list.
    """
    semantic_ranks = {product_id: (index + 1, score) for index, (product_id, score) in enumerate(semantic)}
    keyword_ranks = {product_id: (index + 1, score) for index, (product_id, score) in enumerate(keyword)}
    product_ids = sorted(set(semantic_ranks) | set(keyword_ranks))

    fused: list[RankedCandidate] = []
    for product_id in product_ids:
        score = 0.0
        sem_rank: int | None = None
        sem_sim: float | None = None
        key_rank: int | None = None
        key_score: float | None = None
        if product_id in semantic_ranks:
            sem_rank, sem_sim = semantic_ranks[product_id]
            score += semantic_weight / (rrf_k + sem_rank)
        if product_id in keyword_ranks:
            key_rank, key_score = keyword_ranks[product_id]
            score += keyword_weight / (rrf_k + key_rank)
        fused.append(
            RankedCandidate(
                product_id=product_id,
                hybrid_score=score,
                semantic_rank=sem_rank,
                keyword_rank=key_rank,
                semantic_similarity=sem_sim,
                keyword_rank_score=key_score,
            )
        )
    fused.sort(key=lambda row: (-row.hybrid_score, row.product_id))
    return fused
