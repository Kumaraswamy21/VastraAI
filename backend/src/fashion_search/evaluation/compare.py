"""Compare two evaluation reports without assuming every positive delta is good."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


METRICS = (
    ("Filter exact match", "filter_metrics.exact_match_rate", "higher"),
    ("Precision@5", "retrieval_metrics.precision_at_5", "higher"),
    ("Recall@10", "retrieval_metrics.recall_at_10", "higher"),
    ("MRR", "retrieval_metrics.mrr", "higher"),
    ("NDCG@10", "retrieval_metrics.ndcg_at_10", "higher"),
    (
        "Constraint violation rate",
        "constraint_metrics.constraint_violation_rate",
        "lower",
    ),
    ("Empty result accuracy", "empty_result_metrics.empty_result_accuracy", "higher"),
    (
        "Conversation accuracy",
        "conversation_metrics.state_transition_accuracy",
        "higher",
    ),
    ("P95 latency ms", "latency.total.p95_ms", "lower"),
    ("Context relevance", "rag_quality_metrics.mean_context_relevance", "higher"),
    (
        "Product attribution accuracy",
        "rag_quality_metrics.mean_product_attribution_accuracy",
        "higher",
    ),
    ("Unsupported claim rate", "rag_quality_metrics.unsupported_claim_rate", "lower"),
    ("Invalid reference rate", "rag_quality_metrics.invalid_reference_rate", "lower"),
    ("Answer groundedness", "rag_quality_metrics.mean_answer_groundedness", "higher"),
)


def _at(value: dict, dotted: str):
    for part in dotted.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def compare(
    baseline: dict,
    current: dict,
    *,
    allow_version_mismatch: bool = False,
    compare_modes: bool = False,
) -> list[dict]:
    keys = [
        "dataset_version",
        "catalog_snapshot_id",
        "catalog_snapshot_sha256",
    ]
    if not compare_modes:
        keys.append("provider_mode")
    for key in keys:
        before = baseline.get("run_metadata", {}).get(key)
        after = current.get("run_metadata", {}).get(key)
        if before != after and not allow_version_mismatch:
            raise ValueError(f"Cannot compare: {key} differs ({before!r} vs {after!r})")
    rows = []
    for label, path, direction in METRICS:
        before, after = _at(baseline, path), _at(current, path)
        rows.append(
            {
                "metric": label,
                "baseline": before,
                "current": after,
                "delta": after - before
                if before is not None and after is not None
                else None,
                "direction": direction,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--allow-version-mismatch", action="store_true")
    parser.add_argument(
        "--compare-modes",
        action="store_true",
        help="Allow different retrieval modes when dataset and catalog match",
    )
    args = parser.parse_args()
    rows = compare(
        json.loads(args.baseline.read_text()),
        json.loads(args.current.read_text()),
        allow_version_mismatch=args.allow_version_mismatch,
        compare_modes=args.compare_modes,
    )
    print(f"{'Metric':28} {'Baseline':>12} {'Current':>12} {'Delta':>12}  Direction")
    for row in rows:

        def fmt(value: float | None) -> str:
            if value is None:
                return "n/a"
            if "latency" in row["metric"].lower():
                return f"{value:.2f} ms"
            return f"{value:.2%}"

        delta = row["delta"]
        delta_text = (
            "n/a"
            if delta is None
            else (
                f"{delta:+.2%}"
                if "latency" not in row["metric"].lower()
                else f"{delta:+.2f} ms"
            )
        )
        print(
            f"{row['metric']:28} {fmt(row['baseline']):>12} {fmt(row['current']):>12} {delta_text:>12}  {row['direction']} is better"
        )


if __name__ == "__main__":
    main()
