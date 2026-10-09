"""Conversational search state, refinement, session, and API tests."""

from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fashion_search.api.search import router
from fashion_search.search.conversation import (
    FollowUpInterpreter,
    RevisionConflictError,
    SearchStateReducer,
    StateTransitionError,
    active_filters,
    deterministic_refinement,
)
from fashion_search.search.schemas import (
    ConstraintUpdate,
    FashionSearchConstraints,
    HybridSearchResponse,
    SearchRefinement,
    SearchState,
)
from fashion_search.search.sessions import search_session_store


def state(**overrides: object) -> SearchState:
    values: dict[str, object] = {
        "original_query": "black dress under ₹4000 for wedding",
        "current_query": "black dress under ₹4000 for wedding",
        "semantic_query": "black dress under ₹4000 for wedding",
        "constraints": FashionSearchConstraints(
            category="dress",
            color="black",
            occasion="wedding",
            price_max=Decimal("4000"),
            price_max_inclusive=False,
        ),
        "revision": 2,
    }
    values.update(overrides)
    return SearchState(**values)


def apply(message: str, current: SearchState | None = None) -> SearchState:
    current = current or state()
    refinement = deterministic_refinement(message, current)
    assert refinement is not None
    return SearchStateReducer().apply(
        current, refinement, message=message, expected_revision=current.revision
    )


class RefinementTests(unittest.TestCase):
    def test_color_changes_without_losing_other_constraints(self) -> None:
        updated = apply("make it blue")
        self.assertEqual(updated.constraints.color, "blue")
        self.assertEqual(updated.constraints.category, "dress")
        self.assertEqual(updated.constraints.occasion, "wedding")
        self.assertEqual(updated.constraints.price_max, Decimal("4000"))
        self.assertEqual(updated.semantic_query, state().semantic_query)

    def test_size_gender_and_numeric_price(self) -> None:
        sized = apply("size XL")
        self.assertEqual(sized.constraints.size, "XL")
        gendered = apply("women's only", sized)
        self.assertEqual(gendered.constraints.gender, "women")
        priced = apply("under ₹3000", gendered)
        self.assertEqual(priced.constraints.price_max, Decimal("3000"))
        self.assertFalse(priced.constraints.price_max_inclusive)
        self.assertEqual(priced.constraints.size, "XL")

    def test_explicit_removals(self) -> None:
        no_price = apply("remove the price limit")
        self.assertIsNone(no_price.constraints.price_min)
        self.assertIsNone(no_price.constraints.price_max)
        no_color = apply("any color")
        self.assertIsNone(no_color.constraints.color)
        no_size = apply("no size preference", apply("size XL"))
        self.assertIsNone(no_size.constraints.size)
        no_wedding = apply("remove the wedding filter")
        self.assertIsNone(no_wedding.constraints.occasion)

    def test_cheaper_is_sorting_not_an_invented_threshold(self) -> None:
        updated = apply("show cheaper options")
        self.assertEqual(updated.sort_preference, "PRICE_ASC")
        self.assertEqual(updated.constraints.price_max, Decimal("4000"))
        self.assertEqual(updated.constraints.color, "black")

    def test_semantic_modifier_preserves_query_and_filters(self) -> None:
        updated = apply("more casual")
        self.assertEqual(updated.semantic_modifiers, ["more casual"])
        self.assertEqual(updated.semantic_query, state().semantic_query)
        self.assertEqual(updated.constraints.occasion, "wedding")

    def test_new_category_resets_incompatible_context(self) -> None:
        updated = apply("show men's running shoes")
        self.assertEqual(updated.constraints.category, "footwear")
        self.assertEqual(updated.constraints.gender, "men")
        self.assertIsNone(updated.constraints.color)
        self.assertIsNone(updated.constraints.price_max)
        self.assertEqual(updated.original_query, "show men's running shoes")

    def test_actually_can_replace_conflicting_price_context(self) -> None:
        current = state(
            constraints=FashionSearchConstraints(
                category="dress", price_min=Decimal("3000")
            )
        )
        updated = apply("actually under ₹2000", current)
        self.assertIsNone(updated.constraints.price_min)
        self.assertEqual(updated.constraints.price_max, Decimal("2000"))


class ReducerTests(unittest.TestCase):
    def test_revision_increments_and_stale_revision_is_rejected(self) -> None:
        updated = apply("make it blue")
        self.assertEqual(updated.revision, 3)
        refinement = SearchRefinement(
            updates=[ConstraintUpdate(field="size", operation="SET", value="M")]
        )
        with self.assertRaises(RevisionConflictError):
            SearchStateReducer().apply(
                updated, refinement, message="size M", expected_revision=2
            )

    def test_invalid_price_range_and_unsupported_taxonomy_are_rejected(self) -> None:
        with self.assertRaises(StateTransitionError):
            SearchStateReducer().apply(
                state(),
                SearchRefinement(
                    updates=[
                        ConstraintUpdate(
                            field="price_min", operation="SET", value=Decimal("5000")
                        )
                    ]
                ),
                message="over 5000",
                expected_revision=2,
            )
        with self.assertRaises(StateTransitionError):
            SearchStateReducer().apply(
                state(),
                SearchRefinement(
                    updates=[
                        ConstraintUpdate(field="size", operation="SET", value="GIANT")
                    ]
                ),
                message="size giant",
                expected_revision=2,
            )

    def test_update_schema_forbids_fields_and_bad_operations(self) -> None:
        with self.assertRaises(ValidationError):
            ConstraintUpdate(field="material", operation="SET", value="linen")
        with self.assertRaises(ValidationError):
            ConstraintUpdate(field="color", operation="REMOVE", value="black")

    def test_provider_failure_never_erases_state(self) -> None:
        provider = MagicMock()
        provider.generate_structured.side_effect = RuntimeError("offline")
        refinement = FollowUpInterpreter(provider).interpret(
            "something elegant", state()
        )
        updated = SearchStateReducer().apply(
            state(), refinement, message="something elegant", expected_revision=2
        )
        self.assertEqual(updated.constraints, state().constraints)
        self.assertEqual(updated.semantic_modifiers, ["something elegant"])


class ActiveFilterTests(unittest.TestCase):
    def test_labels_are_deterministic(self) -> None:
        filters = active_filters(state())
        values = {(item.key, item.label, item.value) for item in filters}
        self.assertIn(("color", "Color", "Black"), values)
        self.assertIn(("price_max", "Price", "Under ₹4,000"), values)
        self.assertTrue(all(item.removable for item in filters))


class SearchApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def setUp(self) -> None:
        search_session_store.clear()

    @staticmethod
    def empty_result(query: str = "dress") -> HybridSearchResponse:
        return HybridSearchResponse(
            query=query,
            retrieval_query=query,
            filters={},
            total=0,
            results=[],
            search_status="no_exact_matches",
            message="No products matched all of your current filters.",
        )

    def test_initial_then_refinement_and_structured_chip_removal(self) -> None:
        initial = state(revision=0)
        with (
            patch(
                "fashion_search.api.search.initial_search_state", return_value=initial
            ),
            patch(
                "fashion_search.api.search.hybrid_search",
                return_value=self.empty_result(),
            ),
        ):
            first = self.client.post("/search", json={"query": initial.original_query})
            self.assertEqual(first.status_code, 200)
            first_body = first.json()
            self.assertEqual(first_body["revision"], 0)
            self.assertEqual(first_body["search_status"], "no_exact_matches")

            second = self.client.post(
                "/search",
                json={
                    "session_id": first_body["session_id"],
                    "expected_revision": 0,
                    "message": "make it blue",
                },
            )
            self.assertEqual(second.status_code, 200)
            second_body = second.json()
            constraints = second_body["state"]["constraints"]
            self.assertEqual(constraints["color"], "blue")
            self.assertEqual(constraints["category"], "dress")
            self.assertEqual(constraints["occasion"], "wedding")
            self.assertEqual(constraints["price_max"], "4000")

            removed = self.client.post(
                "/search",
                json={
                    "session_id": first_body["session_id"],
                    "expected_revision": 1,
                    "updates": [{"field": "occasion", "operation": "REMOVE"}],
                },
            )
            self.assertEqual(removed.status_code, 200)
            self.assertIsNone(removed.json()["state"]["constraints"]["occasion"])

    def test_stale_request_gets_conflict(self) -> None:
        session_id, _ = search_session_store.create(state(revision=4))
        with patch(
            "fashion_search.api.search.hybrid_search", return_value=self.empty_result()
        ):
            response = self.client.post(
                "/search",
                json={
                    "session_id": session_id,
                    "expected_revision": 3,
                    "message": "make it blue",
                },
            )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
