"""Constraint extraction accuracy and hallucinated-filter metrics."""

from fashion_search.search.schemas import FashionSearchConstraints

FILTER_FIELDS = (
    "category",
    "color",
    "occasion",
    "size",
    "gender",
    "price_min",
    "price_max",
    "currency",
    "price_min_inclusive",
    "price_max_inclusive",
)
PREFERENCE_FIELDS = (
    "category",
    "color",
    "occasion",
    "size",
    "gender",
    "price_min",
    "price_max",
)


def value_for(value, field: str):
    return (
        getattr(value, field)
        if isinstance(value, FashionSearchConstraints)
        else value.get(field)
    )


def compare_filters(
    expected: FashionSearchConstraints, actual: FashionSearchConstraints
) -> dict:
    mismatches = {}
    correct = {
        field: value_for(expected, field) == value_for(actual, field)
        for field in FILTER_FIELDS
    }
    for field, matched in correct.items():
        if not matched:
            mismatches[field] = {
                "expected": value_for(expected, field),
                "actual": value_for(actual, field),
            }
    expected_active = {
        f for f in PREFERENCE_FIELDS if value_for(expected, f) is not None
    }
    actual_active = {f for f in PREFERENCE_FIELDS if value_for(actual, f) is not None}
    true_positive = sum(
        value_for(expected, field) is not None
        and value_for(expected, field) == value_for(actual, field)
        for field in PREFERENCE_FIELDS
    )
    false_positive = len(actual_active - expected_active)
    false_negative = len(expected_active - actual_active)
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "correct_fields": correct,
        "mismatches": mismatches,
        "exact_match": not mismatches,
        "unexpected_constraint_count": false_positive,
        "constraint_precision": precision,
        "constraint_recall": recall,
        "constraint_f1": f1,
    }


def aggregate_filter_metrics(rows: list[dict]) -> dict:
    metrics = {
        field: sum(row["filter_evaluation"]["correct_fields"][field] for row in rows)
        / len(rows)
        if rows
        else None
        for field in FILTER_FIELDS
    }
    return {
        "exact_match_rate": sum(row["filter_evaluation"]["exact_match"] for row in rows)
        / len(rows)
        if rows
        else None,
        "field_accuracy": metrics,
        "unexpected_constraint_count": sum(
            row["filter_evaluation"]["unexpected_constraint_count"] for row in rows
        ),
        "constraint_precision": _mean(
            [row["filter_evaluation"]["constraint_precision"] for row in rows]
        ),
        "constraint_recall": _mean(
            [row["filter_evaluation"]["constraint_recall"] for row in rows]
        ),
        "constraint_f1": _mean(
            [row["filter_evaluation"]["constraint_f1"] for row in rows]
        ),
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
