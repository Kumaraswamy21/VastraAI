"""Provider-free tests for RAG context bounds, validation, and answer safety."""

from __future__ import annotations

import unittest

from fashion_search.rag.context import build_retrieval_context, context_size_chars
from fashion_search.rag.evaluation import (
    evaluate_grounding,
    run_adversarial_grounding_suite,
)
from fashion_search.rag.grounding import (
    GroundedGeneration,
    GroundingValidationError,
    render_grounded_answer,
    validate_grounded_generation,
)
from fashion_search.rag.service import generate_grounded_answer, needs_grounded_answer
from fashion_search.search.schemas import (
    FashionSearchConstraints,
    HybridSearchResult,
    HybridSearchScores,
    RankingEvidence,
)


def product(product_id: int = 11, **overrides) -> HybridSearchResult:
    fields = {
        "product_id": product_id,
        "title": "Blue Linen Wedding Dress",
        "category": "dress",
        "color": "blue",
        "material": "linen blend",
        "style": "flowy",
        "gender": "women",
        "occasion": "wedding",
        "description": "A breathable linen-blend dress for celebrations. " * 30,
        "sizes": ["S", "M"],
        "price_inr": 3500,
        "currency": "INR",
        "image_reference": "catalog/blue-dress.webp",
        "product_url": "/products/blue-linen-wedding-dress",
        "scores": HybridSearchScores(hybrid_score=0.03),
        "match_quality": "good",
        "match_reason": "Matches blue wedding dress filters.",
        "ranking": RankingEvidence(
            hybrid_score=0.03,
            final_rank=1,
            ranking_sources=["keyword"],
            matched_constraints=["color", "occasion", "category"],
        ),
    }
    fields.update(overrides)
    return HybridSearchResult(**fields)


class FakeProvider:
    name = "fake"
    model_name = "fake-grounded"

    def __init__(self, generated=None, error: Exception | None = None):
        self.generated = generated
        self.error = error
        self.calls = 0

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        raise AssertionError("RAG must request structured output")

    def generate_structured(self, prompt, schema, *, system_prompt=None):
        self.calls += 1
        self.prompt = prompt
        if self.error:
            raise self.error
        return self.generated

    def health(self):
        return {"status": "ok"}


class RagTests(unittest.TestCase):
    def test_context_is_allowlisted_top_k_bounded_and_description_truncated(self):
        rows = build_retrieval_context(
            [product(11), product(12)], top_k=1, description_max_chars=80
        )
        self.assertEqual(len(rows), 1)
        self.assertLessEqual(len(rows[0]["description"]), 80)
        self.assertNotIn("scores", rows[0])
        self.assertNotIn("product_url", rows[0])
        self.assertNotIn("image_reference", rows[0])
        self.assertEqual(rows[0]["reference"], "product_11")
        self.assertGreater(context_size_chars(rows), 0)

    def test_context_omits_missing_optional_catalog_fields(self):
        context = build_retrieval_context([product()], top_k=1)[0]
        self.assertNotIn("brand", context)
        self.assertNotIn("fit", context)

    def test_exact_claim_and_product_reference_are_accepted(self):
        context = build_retrieval_context([product()])
        generated = GroundedGeneration(
            answer_kind="comparison",
            referenced_product_ids=[11],
            claims=[
                {"product_id": 11, "attribute": "material", "value": "linen blend"}
            ],
        )
        validated = validate_grounded_generation(generated, context)
        self.assertIn("linen blend", render_grounded_answer(validated, context))

    def test_hallucinated_product_reference_is_rejected(self):
        context = build_retrieval_context([product()])
        generated = GroundedGeneration(
            answer_kind="summary", referenced_product_ids=[999]
        )
        with self.assertRaises(GroundingValidationError) as raised:
            validate_grounded_generation(generated, context)
        self.assertTrue(raised.exception.invalid_reference)

    def test_missing_material_or_size_is_never_filled_from_a_guess(self):
        context = [
            {
                "product_id": 11,
                "title": "Blue Dress",
                "color": "blue",
                "sizes": ["S", "L"],
            }
        ]
        for attribute, value in (("material", "cotton"), ("sizes", "M")):
            generated = GroundedGeneration(
                answer_kind="explanation",
                referenced_product_ids=[11],
                claims=[{"product_id": 11, "attribute": attribute, "value": value}],
            )
            with self.assertRaises(GroundingValidationError):
                validate_grounded_generation(generated, context)

    def test_price_and_occasion_claims_must_match_catalog(self):
        context = [
            {
                "product_id": 11,
                "title": "Party Dress",
                "occasion": "party",
                "price_inr": 3500,
            }
        ]
        generated = GroundedGeneration(
            answer_kind="summary",
            referenced_product_ids=[11],
            claims=[{"product_id": 11, "attribute": "price_inr", "value": "2000"}],
        )
        with self.assertRaises(GroundingValidationError):
            validate_grounded_generation(generated, context)

    def test_provider_error_returns_safe_context_only_answer(self):
        worker = FakeProvider(error=RuntimeError("unavailable"))
        result = generate_grounded_answer(
            "Which would work for summer?",
            FashionSearchConstraints(),
            [product()],
            provider=worker,
        )
        self.assertTrue(result.grounding_failure)
        self.assertEqual(result.referenced_product_ids, [11])
        self.assertEqual(result.answer, "I found 1 option matching your preferences.")

    def test_zero_results_do_not_call_generation(self):
        worker = FakeProvider()
        result = generate_grounded_answer(
            "Which would work for summer?",
            FashionSearchConstraints(),
            [],
            provider=worker,
        )
        self.assertEqual(worker.calls, 0)
        self.assertEqual(result.answer, "")

    def test_contextual_questions_trigger_rag_but_filter_changes_do_not(self):
        self.assertTrue(
            needs_grounded_answer("Which ones would work better for summer?")
        )
        for message in (
            "make it blue",
            "size M",
            "show cheaper options",
            "remove wedding",
        ):
            self.assertFalse(needs_grounded_answer(message))

    def test_grounding_evaluation_detects_bad_claims_and_references(self):
        result = run_adversarial_grounding_suite()
        self.assertEqual(result["invalid_product_reference_emission_count"], 0)
        self.assertEqual(result["unsupported_claim_emission_count"], 0)
        self.assertGreater(result["invalid_product_reference_count"], 0)
        self.assertGreater(result["unsupported_claim_count"], 0)
        bad = GroundedGeneration(answer_kind="summary", referenced_product_ids=[404])
        score = evaluate_grounding(
            "blue dress", [{"product_id": 1, "color": "blue"}], bad
        )
        self.assertEqual(score["invalid_reference_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
