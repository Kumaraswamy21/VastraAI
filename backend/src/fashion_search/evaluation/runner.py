"""Repeatable evaluator. Default mode is offline and never calls an AI provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fashion_search.catalog.generator import DEFAULT_PRODUCT_COUNT, DEFAULT_SEED
from fashion_search.catalog.models import Product
from fashion_search.config.settings import get_settings
from fashion_search.core.db import get_engine
from fashion_search.evaluation.metrics.constraints import (
    aggregate_empty_metrics,
    constraint_violations,
    empty_classification,
)
from fashion_search.evaluation.metrics.filters import (
    aggregate_filter_metrics,
    compare_filters,
)
from fashion_search.evaluation.metrics.latency import summarize
from fashion_search.evaluation.metrics.retrieval import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from fashion_search.evaluation.schemas import EvaluationDataset
from fashion_search.search.constraints import fallback_parse
from fashion_search.search.conversation import (
    SearchStateReducer,
    deterministic_refinement,
)
from fashion_search.search.explanations import (
    MatchExplanationBuilder,
    QualityThresholds,
    all_hard_constraints_match,
    classify_match_quality,
)
from fashion_search.search.keyword import search_by_keyword
from fashion_search.search.preprocess import build_retrieval_query
from fashion_search.search.ranking import RankedCandidate
from fashion_search.search.schemas import SearchState

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = ROOT / "evaluation" / "datasets" / "fashion_search_v1.json"


def catalog_checksum(products: list[Product]) -> str:
    """Hash the immutable, user-facing seeded catalog fields in stable ID order."""
    rows = [
        {
            "id": p.id,
            "slug": p.slug,
            "category": p.category,
            "color": p.color,
            "material": p.material,
            "style": p.style,
            "gender": p.gender,
            "occasion": p.occasion,
            "sizes": p.sizes,
            "price_inr": p.price_inr,
            "title": p.title,
            "description": p.description,
        }
        for p in sorted(products, key=lambda row: row.id)
    ]
    serialized = json.dumps(rows, sort_keys=True, default=list, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def git_worktree_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def _ndcg_eligible(case) -> bool:
    return case.judgments_complete and bool(case.relevance)


def evaluate(
    dataset_path: Path,
    *,
    limit: int | None = None,
    query_id: str | None = None,
    provider_mode: str = "offline_keyword",
) -> dict:
    if provider_mode != "offline_keyword":
        raise ValueError(
            "Only offline_keyword is implemented; it intentionally calls no model providers"
        )
    dataset = EvaluationDataset.model_validate_json(dataset_path.read_text())
    cfg = get_settings()
    with Session(get_engine(), expire_on_commit=False) as session:
        products = list(session.scalars(select(Product).order_by(Product.id)))
    actual_snapshot = catalog_checksum(products)
    if actual_snapshot != dataset.catalog_snapshot_sha256:
        raise ValueError(
            f"Catalog snapshot mismatch: dataset={dataset.catalog_snapshot_sha256}, actual={actual_snapshot}. "
            "Refresh the dataset snapshot deliberately before evaluating."
        )
    by_id = {product.id: product for product in products}
    missing = sorted(
        {pid for case in dataset.queries for pid in case.relevance if pid not in by_id}
    )
    if missing:
        raise ValueError(f"Dataset references missing product IDs: {missing[:10]}")
    for case in dataset.queries:
        for product_id, grade in case.relevance.items():
            if grade > 0 and not all_hard_constraints_match(
                by_id[product_id], case.expected_filters
            ):
                raise ValueError(
                    f"Invalid relevance label: {case.id} marks hard-filter violator {product_id} as relevant"
                )
        if case.expected_empty is not None:
            has_match = any(
                all_hard_constraints_match(product, case.expected_filters)
                for product in products
            )
            if case.expected_empty == has_match:
                raise ValueError(
                    f"Catalog label mismatch for {case.id}: expected_empty={case.expected_empty}, exact matches exist={has_match}"
                )

    cases = dataset.queries
    if query_id:
        cases = [case for case in cases if case.id == query_id]
        if not cases:
            raise ValueError(f"Unknown query id: {query_id}")
    if limit:
        cases = cases[:limit]

    details = []
    for case in cases:
        started = time.perf_counter()
        parse_start = time.perf_counter()
        actual = fallback_parse(case.query, currency=cfg.market_currency)
        retrieval_query = build_retrieval_query(case.query, actual)
        parse_ms = (time.perf_counter() - parse_start) * 1000
        search_start = time.perf_counter()
        hits = search_by_keyword(retrieval_query, constraints=actual, limit=50)
        keyword_ms = (time.perf_counter() - search_start) * 1000
        ranked_ids = [hit.product.id for hit in hits]
        products_found = [hit.product for hit in hits]
        filter_result = compare_filters(case.expected_filters, actual)
        # Compare returned products against the human-intended hard constraints,
        # not merely the parser output; otherwise a missed parser filter hides leaks.
        violations = constraint_violations(products_found, case.expected_filters)
        relevance = case.relevance
        retrieval = {
            "precision_at_5": precision_at_k(ranked_ids, relevance, 5)
            if case.judgments_complete and relevance
            else None,
            "recall_at_10": recall_at_k(ranked_ids, relevance, 10)
            if relevance and case.judgments_complete
            else None,
            "mrr": reciprocal_rank(ranked_ids, relevance)
            if case.judgments_complete and relevance
            else None,
            "ndcg_at_5": ndcg_at_k(ranked_ids, relevance, 5)
            if _ndcg_eligible(case)
            else None,
            "ndcg_at_10": ndcg_at_k(ranked_ids, relevance, 10)
            if _ndcg_eligible(case)
            else None,
        }
        explanation_builder = MatchExplanationBuilder()
        explanation_present = 0
        unsupported_claims: list[dict] = []
        quality_counts = {"strong": 0, "good": 0, "weak": 0}
        explanation_started = time.perf_counter()
        for rank, hit in enumerate(hits, start=1):
            ranked = RankedCandidate(
                product_id=hit.product.id,
                semantic_similarity=None,
                keyword_rank_score=hit.rank_score,
                semantic_rank=None,
                keyword_rank=rank,
                hybrid_score=hit.rank_score,
            )
            quality = classify_match_quality(
                hit.product, actual, ranked, QualityThresholds()
            )
            quality_counts[quality] += 1
            explanation = explanation_builder.build(
                hit.product, actual, ranked, quality
            )
            explanation_present += bool(explanation.strip())
            if not all_hard_constraints_match(hit.product, actual):
                unsupported_claims.append(
                    {"product_id": hit.product.id, "claim": "hard-filter match"}
                )
        explanation_ms = (time.perf_counter() - explanation_started) * 1000
        elapsed = (time.perf_counter() - started) * 1000
        details.append(
            {
                "query_id": case.id,
                "query": case.query,
                "query_type": case.query_type,
                "expected_filters": case.expected_filters.model_dump(mode="json"),
                "actual_filters": actual.model_dump(mode="json"),
                "filter_evaluation": filter_result,
                "relevance_judgments": {str(k): v for k, v in relevance.items()},
                "judgments_complete": case.judgments_complete,
                "returned_product_ids": ranked_ids,
                "ranking": [
                    {"product_id": pid, "rank": pos, "relevance": relevance.get(pid, 0)}
                    for pos, pid in enumerate(ranked_ids, start=1)
                ],
                "retrieval_metrics": retrieval,
                "constraint_violation_ids": violations,
                "constraint_violation_count": len(violations),
                "expected_empty": case.expected_empty,
                "actual_result_count": len(hits),
                "empty_classification": empty_classification(
                    case.expected_empty, not hits
                ),
                "weak_case": case.weak_case,
                "weak_result_behavior": {
                    "has_results": bool(hits),
                    "match_quality_counts": quality_counts,
                    "quality": "no_results"
                    if not hits
                    else "classified_by_existing_rules",
                },
                "explanation_present_count": explanation_present,
                "explanation_present_rate": explanation_present / len(hits)
                if hits
                else None,
                "unsupported_explanation_claims": unsupported_claims,
                "latency": {
                    "total_latency_ms": elapsed,
                    "constraint_parsing_ms": parse_ms,
                    "query_embedding_ms": None,
                    "semantic_search_ms": None,
                    "keyword_search_ms": keyword_ms,
                    "fusion_ms": 0.0,
                    "explanation_ms": explanation_ms,
                },
                "search_mode": "KEYWORD_ONLY",
                "provider_mode": "offline_keyword",
                "provider_model": None,
            }
        )

    filter_metrics = aggregate_filter_metrics(details)
    judged = [
        row for row in details if row["retrieval_metrics"]["precision_at_5"] is not None
    ]
    complete_judged = [
        row for row in details if row["retrieval_metrics"]["recall_at_10"] is not None
    ]

    def aggregate(key: str, rows: list[dict]) -> float | None:
        return (
            sum(row["retrieval_metrics"][key] for row in rows) / len(rows)
            if rows
            else None
        )

    violations = sum(row["constraint_violation_count"] for row in details)
    returned_count = sum(row["actual_result_count"] for row in details)
    latency_rows = [row["latency"] for row in details]
    stage_names = sorted(
        {
            name
            for row in latency_rows
            for name, value in row.items()
            if name != "total_latency_ms" and isinstance(value, (int, float))
        }
    )
    conversation = evaluate_conversations(dataset)
    try:
        completed_embeddings = sum(p.embedding_status == "COMPLETED" for p in products)
    except Exception:
        completed_embeddings = None
    metadata = {
        "dataset_version": dataset.dataset_version,
        "catalog_snapshot_id": dataset.catalog_snapshot_id,
        "catalog_snapshot_sha256": actual_snapshot,
        "catalog_product_count": len(products),
        "catalog_seed": DEFAULT_SEED,
        "catalog_generated_count": DEFAULT_PRODUCT_COUNT,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "git_worktree_dirty": git_worktree_dirty(),
        "provider_mode": "offline_keyword",
        "generation_provider_configured": cfg.generation_provider,
        "generation_model_configured": cfg.generation_model or cfg.search_parser_model,
        "embedding_provider_configured": cfg.embedding_provider,
        "embedding_model_configured": cfg.embedding_model,
        "embedding_dimensions": cfg.embedding_dimensions,
        "rrf_k": cfg.hybrid_rrf_k,
        "semantic_weight": cfg.hybrid_semantic_weight,
        "keyword_weight": cfg.hybrid_keyword_weight,
        "completed_embeddings": completed_embeddings,
        "note": "Offline FTS baseline; no generation or embedding provider was called.",
    }
    return {
        "run_metadata": metadata,
        "filter_metrics": filter_metrics,
        "retrieval_metrics": {
            "judged_query_count": len(judged),
            "complete_judgment_query_count": len(complete_judged),
            "precision_at_5": aggregate("precision_at_5", judged),
            "recall_at_10": aggregate("recall_at_10", complete_judged),
            "mrr": aggregate("mrr", judged),
            "ndcg_at_5": aggregate("ndcg_at_5", complete_judged),
            "ndcg_at_10": aggregate("ndcg_at_10", complete_judged),
        },
        "constraint_metrics": {
            "constraint_violation_count": violations,
            "constraint_violation_rate": violations / returned_count
            if returned_count
            else 0.0,
            "returned_product_count": returned_count,
        },
        "empty_result_metrics": aggregate_empty_metrics(details),
        "conversation_metrics": conversation,
        "explanation_metrics": {
            "explanation_present_rate": _mean(
                [
                    row["explanation_present_rate"]
                    for row in details
                    if row["explanation_present_rate"] is not None
                ]
            ),
            "unsupported_claim_count": sum(
                len(row["unsupported_explanation_claims"]) for row in details
            ),
        },
        "latency": {
            "total": summarize([row["latency"]["total_latency_ms"] for row in details]),
            "stages": {
                stage: summarize([row["latency"].get(stage, 0.0) for row in details])
                for stage in stage_names
            },
        },
        "query_count": len(details),
        "details": details,
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def evaluate_conversations(dataset: EvaluationDataset) -> dict:
    total = correct = 0
    details = []
    for conversation in dataset.conversations:
        first = conversation.turns[0]
        state = SearchState(
            original_query=first.message,
            current_query=first.message,
            constraints=fallback_parse(first.message),
            semantic_query=first.message,
            revision=0,
        )
        for index, turn in enumerate(conversation.turns):
            if index:
                refinement = deterministic_refinement(turn.message, state)
                if refinement is None:
                    # Provider-free evaluation fails closed: an unhandled turn is scored as incorrect.
                    total += 1
                    details.append(
                        {
                            "conversation_id": conversation.id,
                            "turn": index + 1,
                            "exact": False,
                            "reason": "no deterministic refinement",
                        }
                    )
                    continue
                state = SearchStateReducer().apply(
                    state,
                    refinement,
                    message=turn.message,
                    expected_revision=state.revision,
                )
            comparison = compare_filters(turn.expected_state, state.constraints)
            total += 1
            correct += comparison["exact_match"]
            details.append(
                {
                    "conversation_id": conversation.id,
                    "turn": index + 1,
                    "exact": comparison["exact_match"],
                    "mismatches": comparison["mismatches"],
                }
            )
    return {
        "turn_count": total,
        "exact_turn_count": correct,
        "state_transition_accuracy": correct / total if total else None,
        "details": details,
    }


def render_report(result: dict) -> str:
    f, r, c, e = (
        result[key]
        for key in (
            "filter_metrics",
            "retrieval_metrics",
            "constraint_metrics",
            "empty_result_metrics",
        )
    )

    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.1%}"

    return (
        "\n".join(
            [
                "# Fashion Search Evaluation",
                "",
                f"Dataset: {result['run_metadata']['dataset_version']}",
                f"Catalog: {result['run_metadata']['catalog_snapshot_id']} ({result['run_metadata']['catalog_product_count']} products)",
                f"Mode: {result['run_metadata']['provider_mode']} (no live providers)",
                f"Queries: {result['query_count']}",
                "",
                "## Filter extraction",
                f"Exact match: {pct(f['exact_match_rate'])}",
                *[
                    f"{field}: {pct(value)}"
                    for field, value in f["field_accuracy"].items()
                ],
                "",
                "## Retrieval (human-labeled cases only)",
                f"Precision@5: {pct(r['precision_at_5'])}",
                f"Recall@10: {pct(r['recall_at_10'])}",
                f"MRR: {pct(r['mrr'])}",
                f"NDCG@10: {pct(r['ndcg_at_10'])}",
                "",
                "## Hard constraints",
                f"Violations: {c['constraint_violation_count']} / {c['returned_product_count']} returned products",
                f"Violation rate: {pct(c['constraint_violation_rate'])}",
                "",
                "## Empty results",
                f"Accuracy: {pct(e['empty_result_accuracy'])}",
                "",
                "## Conversation",
                f"State transition accuracy: {pct(result['conversation_metrics']['state_transition_accuracy'])}",
                "",
                "## Latency (offline keyword mode)",
                f"Mean: {result['latency']['total']['mean_ms']:.2f} ms"
                if result["latency"]["total"]["mean_ms"] is not None
                else "Mean: n/a",
                f"P50: {result['latency']['total']['p50_ms']:.2f} ms"
                if result["latency"]["total"]["p50_ms"] is not None
                else "P50: n/a",
                f"P95: {result['latency']['total']['p95_ms']:.2f} ms"
                if result["latency"]["total"]["p95_ms"] is not None
                else "P95: n/a",
            ]
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--query-id")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--provider-mode", choices=["offline_keyword"], default="offline_keyword"
    )
    args = parser.parse_args()
    result = evaluate(
        args.dataset,
        limit=args.limit,
        query_id=args.query_id,
        provider_mode=args.provider_mode,
    )
    output = args.output or ROOT / "evaluation" / "results" / "current.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    output.with_suffix(".md").write_text(render_report(result))
    print(render_report(result))
    print(f"Machine-readable report: {output}")


if __name__ == "__main__":
    main()
