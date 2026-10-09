from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from fashion_search.evaluation.compare import compare
from fashion_search.evaluation.metrics.constraints import (
    constraint_violations,
    empty_classification,
)
from fashion_search.evaluation.metrics.filters import compare_filters
from fashion_search.evaluation.metrics.latency import percentile, summarize
from fashion_search.evaluation.metrics.retrieval import (
    dcg_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from fashion_search.evaluation.runner import evaluate_conversations
from fashion_search.evaluation.schemas import EvaluationDataset
from fashion_search.catalog.generator import generate_catalog
from fashion_search.search.explanations import all_hard_constraints_match
from fashion_search.search.schemas import FashionSearchConstraints


class RetrievalMetricTests(unittest.TestCase):
    def test_precision_fixed_k_denominator_and_recall(self):
        judgments = {1: 3, 2: 0, 3: 2}
        self.assertEqual(precision_at_k([1, 2], judgments, 5), 0.2)
        self.assertEqual(recall_at_k([1], judgments, 10), 0.5)

    def test_rr_mrr_dcg_ndcg(self):
        judgments = {1: 3, 2: 0, 3: 1}
        self.assertEqual(reciprocal_rank([2, 3, 1], judgments), 0.5)
        self.assertEqual(dcg_at_k([1], judgments, 1), 7.0)
        self.assertEqual(ndcg_at_k([1, 3, 2], judgments, 3), 1.0)


class FilterMetricTests(unittest.TestCase):
    def test_field_match_and_unexpected_constraint(self):
        expected = FashionSearchConstraints(category="dress", color="black")
        actual = FashionSearchConstraints(
            category="dress", color="black", gender="women"
        )
        result = compare_filters(expected, actual)
        self.assertFalse(result["exact_match"])
        self.assertEqual(result["unexpected_constraint_count"], 1)
        self.assertEqual(result["constraint_precision"], 2 / 3)
        self.assertEqual(result["unexpected_constraint_count"], 1)

    def test_exact_filter_match(self):
        c = FashionSearchConstraints(category="dress", price_max=4000)
        self.assertTrue(compare_filters(c, c)["exact_match"])


class EmptyAndLatencyTests(unittest.TestCase):
    def test_empty_result_categories(self):
        self.assertEqual(empty_classification(True, True), "true_empty")
        self.assertEqual(empty_classification(False, True), "false_empty")
        self.assertEqual(empty_classification(True, False), "unexpected_results")

    def test_percentiles_and_summary(self):
        self.assertEqual(percentile([0, 10], 50), 5)
        self.assertEqual(summarize([1, 2, 3])["p95_ms"], 2.9)


class CompareTests(unittest.TestCase):
    def test_version_mismatch_rejected(self):
        a = {"run_metadata": {"dataset_version": "v1"}}
        b = {"run_metadata": {"dataset_version": "v2"}}
        with self.assertRaises(ValueError):
            compare(a, b)

    def test_catalog_version_and_checksum_mismatch_rejected(self):
        a = {
            "run_metadata": {
                "dataset_version": "v1",
                "catalog_snapshot_id": "c1",
                "catalog_snapshot_sha256": "h1",
                "provider_mode": "offline",
            }
        }
        b = {
            "run_metadata": {
                "dataset_version": "v1",
                "catalog_snapshot_id": "c2",
                "catalog_snapshot_sha256": "h2",
                "provider_mode": "offline",
            }
        }
        with self.assertRaises(ValueError):
            compare(a, b)

    def test_matching_versions_and_metric_delta(self):
        a = {
            "run_metadata": {
                "dataset_version": "v1",
                "catalog_snapshot_id": "c",
                "catalog_snapshot_sha256": "h",
                "provider_mode": "offline",
            },
            "filter_metrics": {"exact_match_rate": 0.5},
        }
        b = {
            "run_metadata": dict(a["run_metadata"]),
            "filter_metrics": {"exact_match_rate": 0.75},
        }
        rows = compare(a, b)
        self.assertEqual(rows[0]["delta"], 0.25)


class DatasetAndConstraintTests(unittest.TestCase):
    def test_versioned_dataset_and_catalog_labels_are_consistent(self):
        dataset_path = (
            Path(__file__).parents[1]
            / "evaluation"
            / "datasets"
            / "fashion_search_v1.json"
        )
        dataset = EvaluationDataset.model_validate_json(dataset_path.read_text())
        self.assertGreaterEqual(len(dataset.queries), 30)
        catalog = generate_catalog()
        by_id = {index + 1: product for index, product in enumerate(catalog)}
        for query in dataset.queries:
            for product_id, grade in query.relevance.items():
                self.assertIn(product_id, by_id)
                if grade > 0:
                    self.assertTrue(
                        all_hard_constraints_match(
                            by_id[product_id], query.expected_filters
                        )
                    )
            if query.expected_empty is not None:
                has_exact_match = any(
                    all_hard_constraints_match(p, query.expected_filters)
                    for p in catalog
                )
                self.assertEqual(not has_exact_match, query.expected_empty, query.id)

    def test_conversation_state_transitions_match_full_expected_states(self):
        dataset_path = (
            Path(__file__).parents[1]
            / "evaluation"
            / "datasets"
            / "fashion_search_v1.json"
        )
        dataset = EvaluationDataset.model_validate_json(dataset_path.read_text())
        result = evaluate_conversations(dataset)
        self.assertEqual(result["turn_count"], 8)
        self.assertEqual(result["state_transition_accuracy"], 1.0)

    def test_hard_constraint_violation_detection(self):
        constraints = FashionSearchConstraints(category="dress", color="black")
        valid = SimpleNamespace(
            id=1,
            category="dress",
            color="black",
            occasion=None,
            sizes=[],
            gender="women",
            price_inr=2000,
        )
        invalid = SimpleNamespace(
            id=2,
            category="dress",
            color="red",
            occasion=None,
            sizes=[],
            gender="women",
            price_inr=2000,
        )
        self.assertEqual(constraint_violations([valid, invalid], constraints), [2])


if __name__ == "__main__":
    unittest.main()
