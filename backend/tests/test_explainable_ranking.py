"""Grounding, quality, and orchestration tests for explainable hybrid ranking."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fashion_search.search.explanations import (
    MatchExplanationBuilder,
    QualityThresholds,
    classify_match_quality,
    matched_constraints,
)
from fashion_search.search.hybrid import hybrid_search
from fashion_search.search.keyword import KeywordHit
from fashion_search.search.ranking import RankedCandidate
from fashion_search.search.schemas import (
    FashionSearchConstraints,
    HybridSearchRequest,
    SearchDiagnostics,
)
from fashion_search.search.vector import VectorHit


def product(**overrides):
    values = dict(
        id=1,
        title="Black Embellished Maxi Dress",
        category="dress",
        color="black",
        material="silk",
        style="maxi",
        gender="women",
        occasion="wedding",
        sizes=["M", "L"],
        price_inr=3499,
        image_reference="catalog/black-dress.webp",
        slug="black-embellished-maxi-dress",
        description="Structured fields, not this text, determine matches.",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def ranked(**overrides):
    values = dict(
        product_id=1,
        hybrid_score=0.0319,
        semantic_rank=2,
        keyword_rank=1,
        semantic_similarity=0.89,
        keyword_rank_score=0.31,
    )
    values.update(overrides)
    return RankedCandidate(**values)


FULL = FashionSearchConstraints(
    category="dress",
    color="black",
    occasion="wedding",
    size="M",
    gender="women",
    price_max=4000,
    price_max_inclusive=False,
)


class ExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = MatchExplanationBuilder()
        self.thresholds = QualityThresholds(0.75, 0.35, 0.01)

    def test_full_exact_match_and_price_are_grounded(self) -> None:
        item = product()
        matches = matched_constraints(item, FULL)
        self.assertEqual(
            matches, ["category", "color", "occasion", "size", "gender", "price"]
        )
        reason = self.builder.build(item, FULL, ranked(), "strong")
        self.assertIn("black dress", reason)
        self.assertIn("wedding-wear", reason)
        self.assertIn("size M", reason)
        self.assertIn("₹3,499", reason)
        self.assertIn("₹4,000", reason)

    def test_missing_occasion_never_invents_wedding_suitability(self) -> None:
        item = product(occasion=None)
        reason = self.builder.build(item, FULL, ranked(), "weak")
        self.assertNotIn("wedding", reason.lower())
        self.assertNotIn("suitable", reason.lower())

    def test_description_cannot_create_color_or_occasion_match(self) -> None:
        item = product(
            color="red",
            occasion=None,
            description="Pairs with black accessories and is a great wedding gift",
        )
        self.assertNotIn("color", matched_constraints(item, FULL))
        self.assertNotIn("occasion", matched_constraints(item, FULL))

    def test_size_gender_and_range_explanations(self) -> None:
        constraints = FashionSearchConstraints(
            size="M",
            gender="women",
            price_min=2000,
            price_max=4000,
        )
        reason = self.builder.build(product(), constraints, ranked(), "strong")
        self.assertIn("size M", reason)
        self.assertIn("women's", reason)
        self.assertIn("₹2,000–₹4,000 range", reason)

    def test_semantic_only_and_keyword_plus_semantic_signals(self) -> None:
        no_constraints = FashionSearchConstraints()
        semantic = ranked(keyword_rank=None, keyword_rank_score=None)
        self.assertIn(
            "semantic relevance",
            self.builder.build(product(), no_constraints, semantic, "good"),
        )
        self.assertIn(
            "keyword and semantic relevance",
            self.builder.build(product(), no_constraints, ranked(), "strong"),
        )

    def test_quality_strong_good_weak_and_hard_violation(self) -> None:
        self.assertEqual(
            classify_match_quality(product(), FULL, ranked(), self.thresholds), "strong"
        )
        good = ranked(
            keyword_rank=None, keyword_rank_score=None, semantic_similarity=0.5
        )
        self.assertEqual(
            classify_match_quality(product(), FULL, good, self.thresholds), "good"
        )
        weak = ranked(
            keyword_rank=None, keyword_rank_score=None, semantic_similarity=0.1
        )
        self.assertEqual(
            classify_match_quality(product(), FULL, weak, self.thresholds), "weak"
        )
        self.assertEqual(
            classify_match_quality(
                product(color="red"), FULL, ranked(), self.thresholds
            ),
            "weak",
        )

    def test_dual_channel_presence_does_not_hide_bad_semantic_signal(self) -> None:
        contradictory = ranked(semantic_similarity=-0.4, keyword_rank_score=0.2)
        self.assertEqual(
            classify_match_quality(product(), FULL, contradictory, self.thresholds),
            "good",
        )

    def test_generation_is_deterministic_without_duplicate_sentences(self) -> None:
        first = self.builder.build(product(), FULL, ranked(), "strong")
        second = self.builder.build(product(), FULL, ranked(), "strong")
        self.assertEqual(first, second)
        self.assertEqual(len(first.split(". ")), len(set(first.split(". "))))


class HybridExplainabilityTests(unittest.TestCase):
    def settings(self):
        return SimpleNamespace(
            market_currency="INR",
            hybrid_candidate_limit=10,
            hybrid_rrf_k=60,
            hybrid_semantic_weight=0.6,
            hybrid_keyword_weight=0.4,
            search_strong_semantic_threshold=0.75,
            search_weak_semantic_threshold=0.35,
            search_min_keyword_signal=0.01,
            search_diagnostics_enabled=True,
        )

    @patch("fashion_search.search.hybrid.diagnose_zero_results")
    @patch("fashion_search.search.hybrid.search_by_keyword")
    @patch("fashion_search.search.hybrid.search_by_vector")
    @patch("fashion_search.search.hybrid.parse_constraints")
    def test_ranking_order_evidence_and_no_extra_calls(
        self,
        parse,
        vector_search,
        keyword_search,
        diagnostics,
    ) -> None:
        constraints = FashionSearchConstraints(category="dress", color="black")
        parse.return_value = SimpleNamespace(constraints=constraints)
        first, second = product(id=1), product(id=2, slug="second")
        vector_search.return_value = [
            VectorHit(first, 0.9),
            VectorHit(second, 0.8),
        ]
        keyword_search.return_value = [KeywordHit(second, 0.4), KeywordHit(first, 0.3)]
        embedder = MagicMock()
        embedder.embed_query.return_value = [1.0]

        response = hybrid_search(
            HybridSearchRequest(query="black dress", limit=2),
            settings=self.settings(),
            embedder=embedder,
        )

        self.assertEqual([row.product_id for row in response.results], [1, 2])
        self.assertEqual([row.ranking.final_rank for row in response.results], [1, 2])
        self.assertEqual(
            response.results[0].ranking.ranking_sources, ["semantic", "keyword"]
        )
        self.assertEqual(
            response.results[0].ranking.matched_constraints, ["category", "color"]
        )
        embedder.embed_query.assert_called_once()
        parse.assert_called_once()
        vector_search.assert_called_once()
        keyword_search.assert_called_once()
        diagnostics.assert_not_called()

    @patch("fashion_search.search.hybrid.diagnose_zero_results")
    @patch("fashion_search.search.hybrid.search_by_keyword", return_value=[])
    @patch("fashion_search.search.hybrid.search_by_vector", return_value=[])
    @patch("fashion_search.search.hybrid.parse_constraints")
    def test_empty_response_uses_diagnostics_without_relaxing(
        self,
        parse,
        vector_search,
        keyword_search,
        diagnostics,
    ) -> None:
        constraints = FashionSearchConstraints(color="black")
        parse.return_value = SimpleNamespace(constraints=constraints)
        diagnostics.return_value = (
            SearchDiagnostics(
                enabled=True,
                initial_catalog=10,
                exact_match_count=0,
                filter_counts={"color": 0},
                eliminated_by="color",
            ),
            [
                "The current catalog has 2 matching products if the color filter is removed."
            ],
        )
        embedder = MagicMock()
        embedder.embed_query.return_value = [1.0]
        response = hybrid_search(
            HybridSearchRequest(query="black", limit=2),
            settings=self.settings(),
            embedder=embedder,
        )
        self.assertEqual(response.search_status, "no_exact_matches")
        self.assertEqual(response.results, [])
        self.assertEqual(response.total, 0)
        self.assertEqual(len(response.suggestions), 1)
        diagnostics.assert_called_once_with(constraints)

    @patch("fashion_search.search.hybrid.diagnose_zero_results")
    @patch("fashion_search.search.hybrid.search_by_keyword", return_value=[])
    @patch("fashion_search.search.hybrid.search_by_vector", return_value=[])
    @patch("fashion_search.search.hybrid.parse_constraints")
    def test_empty_retrieval_does_not_falsely_claim_filters_eliminated_products(
        self,
        parse,
        vector_search,
        keyword_search,
        diagnostics,
    ) -> None:
        constraints = FashionSearchConstraints(category="dress")
        parse.return_value = SimpleNamespace(constraints=constraints)
        diagnostics.return_value = (
            SearchDiagnostics(
                initial_catalog=10,
                exact_match_count=4,
                filter_counts={"category": 4},
                eliminated_by=None,
            ),
            [],
        )
        embedder = MagicMock()
        embedder.embed_query.return_value = [1.0]
        response = hybrid_search(
            HybridSearchRequest(query="avant-garde dress", limit=2),
            settings=self.settings(),
            embedder=embedder,
        )
        self.assertEqual(response.search_status, "no_relevant_matches")
        self.assertNotIn("matched all", response.message)
        self.assertEqual(response.suggestions, [])


if __name__ == "__main__":
    unittest.main()
