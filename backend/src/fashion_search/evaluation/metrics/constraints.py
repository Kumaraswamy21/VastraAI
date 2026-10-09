"""Application hard-filter conformance metrics."""

from fashion_search.search.explanations import all_hard_constraints_match
from fashion_search.search.schemas import FashionSearchConstraints


def constraint_violations(products, constraints: FashionSearchConstraints) -> list[int]:
    return [
        product.id
        for product in products
        if not all_hard_constraints_match(product, constraints)
    ]


def empty_classification(expected: bool | None, actual_empty: bool) -> str:
    if expected is None:
        return "unlabeled"
    if expected and actual_empty:
        return "true_empty"
    if not expected and actual_empty:
        return "false_empty"
    if expected and not actual_empty:
        return "unexpected_results"
    return "expected_nonempty"


def aggregate_empty_metrics(rows: list[dict]) -> dict:
    labeled = [row for row in rows if row["expected_empty"] is not None]
    correct = sum(
        (row["expected_empty"] == (row["actual_result_count"] == 0)) for row in labeled
    )
    return {
        "labeled_query_count": len(labeled),
        "true_empty_count": sum(
            row["empty_classification"] == "true_empty" for row in rows
        ),
        "false_empty_count": sum(
            row["empty_classification"] == "false_empty" for row in rows
        ),
        "unexpected_result_count": sum(
            row["empty_classification"] == "unexpected_results" for row in rows
        ),
        "empty_result_accuracy": correct / len(labeled) if labeled else None,
    }
