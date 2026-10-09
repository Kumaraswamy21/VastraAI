"""Conversational search interpretation and deterministic state transitions."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from fashion_search.config.settings import Settings, get_settings
from fashion_search.generation.base import GenerationProvider
from fashion_search.prompts import load_prompt
from fashion_search.search.constraints import (
    fallback_parse, normalize_constraints, parse_constraints, parse_price_facts,
)
from fashion_search.search.schemas import (
    ActiveFilter, ConstraintUpdate, FashionSearchConstraints,
    SearchRefinement, SearchState,
)


class StateTransitionError(ValueError):
    """A refinement cannot produce a valid search state."""


class RevisionConflictError(StateTransitionError):
    """The client attempted to refine an obsolete state revision."""


def initial_search_state(
    query: str, *, settings: Settings | None = None, provider: GenerationProvider | None = None
) -> SearchState:
    cfg = settings or get_settings()
    parsed = parse_constraints(query, settings=cfg, provider=provider)
    return SearchState(
        original_query=query.strip(), current_query=query.strip(),
        constraints=parsed.constraints, semantic_query=query.strip(), revision=0,
    )


def _set_updates(constraints: FashionSearchConstraints) -> list[ConstraintUpdate]:
    return [
        ConstraintUpdate(
            field=key, operation="SET", value=value,
            inclusive=(
                constraints.price_min_inclusive if key == "price_min"
                else constraints.price_max_inclusive if key == "price_max" else None
            ),
        )
        for key, value in constraints.model_dump(exclude_none=True).items()
        if key in {"category", "color", "occasion", "size", "gender", "price_min", "price_max", "currency"}
        and not (key == "currency" and value == "INR")
    ]


def deterministic_refinement(message: str, state: SearchState) -> SearchRefinement | None:
    """Interpret explicit, high-confidence deltas without a generation provider."""
    text = re.sub(r"\s+", " ", message.strip().lower())

    # A different explicitly named category starts a fresh product context.
    parsed = fallback_parse(message, currency=state.constraints.currency)
    if parsed.category and parsed.category != state.constraints.category:
        return SearchRefinement(
            updates=_set_updates(parsed), semantic_refinement=message.strip(), reset_search=True
        )

    updates: list[ConstraintUpdate] = []
    if re.search(r"\b(?:remove|clear|no|without)\s+(?:the\s+)?price\s+(?:limit|filter|preference)\b", text):
        updates.extend([
            ConstraintUpdate(field="price_min", operation="REMOVE"),
            ConstraintUpdate(field="price_max", operation="REMOVE"),
        ])
    if re.search(r"\b(?:any|no)\s+colou?r(?:\s+preference)?\b", text):
        updates.append(ConstraintUpdate(field="color", operation="REMOVE"))
    if re.search(r"\b(?:no|any)\s+size(?:\s+preference)?\b", text):
        updates.append(ConstraintUpdate(field="size", operation="REMOVE"))
    for field in ("category", "occasion", "gender"):
        if re.search(rf"\b(?:remove|clear|without)\s+(?:the\s+)?{field}(?:\s+filter)?\b", text):
            updates.append(ConstraintUpdate(field=field, operation="REMOVE"))
    explicit_value_removal = bool(re.search(r"\b(?:remove|clear|without)\b", text))
    if explicit_value_removal:
        for field in ("category", "color", "occasion", "size", "gender"):
            value = getattr(parsed, field)
            if value is not None and value == getattr(state.constraints, field):
                updates.append(ConstraintUpdate(field=field, operation="REMOVE"))

    cheaper = bool(re.search(r"\b(?:cheaper|more affordable|lower[- ]priced?)\b", text))
    expensive = bool(re.search(r"\b(?:more expensive|higher[- ]priced?|premium options?)\b", text))
    sort = "PRICE_ASC" if cheaper else "PRICE_DESC" if expensive else None

    price = parse_price_facts(message)
    if price.detected and not price.invalid:
        if price.minimum is not None:
            if "actually" in text and state.constraints.price_max is not None and price.minimum > state.constraints.price_max:
                updates.append(ConstraintUpdate(field="price_max", operation="REMOVE"))
            updates.append(ConstraintUpdate(
                field="price_min", operation="SET", value=price.minimum,
                inclusive=price.minimum_inclusive,
            ))
        if price.maximum is not None:
            if "actually" in text and state.constraints.price_min is not None and price.maximum < state.constraints.price_min:
                updates.append(ConstraintUpdate(field="price_min", operation="REMOVE"))
            updates.append(ConstraintUpdate(
                field="price_max", operation="SET", value=price.maximum,
                inclusive=price.maximum_inclusive,
            ))

    removal_fields = {item.field for item in updates if item.operation == "REMOVE"}
    for field in ("color", "size", "gender"):
        value = getattr(parsed, field)
        if value is not None and field not in removal_fields:
            updates.append(ConstraintUpdate(field=field, operation="SET", value=value))
    # Occasion words in comparative style phrases are semantic, not exact filters.
    if (
        parsed.occasion and "occasion" not in removal_fields
        and not re.search(r"\b(?:more|less)\s+" + re.escape(parsed.occasion) + r"\b", text)
    ):
        updates.append(ConstraintUpdate(field="occasion", operation="SET", value=parsed.occasion))
    if parsed.category and parsed.category == state.constraints.category:
        updates.append(ConstraintUpdate(field="category", operation="KEEP"))

    semantic = None
    semantic_match = re.search(r"\b(?:more|less)\s+(casual|minimalist|flashy|sporty)\b", text)
    if semantic_match:
        semantic = semantic_match.group(0)
    if updates or sort or semantic:
        return SearchRefinement(
            updates=updates, sort_preference=sort, semantic_refinement=semantic
        )
    return None


class FollowUpInterpreter:
    """Deterministic-first, provider-neutral refinement interpreter."""

    def __init__(self, provider: GenerationProvider) -> None:
        self._provider = provider

    def interpret(self, message: str, state: SearchState) -> SearchRefinement:
        deterministic = deterministic_refinement(message, state)
        if deterministic is not None:
            return deterministic
        prompt = json.dumps(
            {"current_state": state.model_dump(mode="json"), "follow_up": message,
             "supported_fields": ["category", "color", "occasion", "size", "gender", "price_min", "price_max", "currency"],
             "allowed_operations": ["SET", "REMOVE", "KEEP", "RELAX"]},
            ensure_ascii=False,
        )
        try:
            return self._provider.generate_structured(
                prompt, SearchRefinement, system_prompt=load_prompt("system_search_refinement")
            )
        except Exception:
            # Existing state remains authoritative when all interpretation fails.
            return SearchRefinement(semantic_refinement=message.strip())


class SearchStateReducer:
    """Pure reducer shared by natural-language and structured UI refinements."""

    def apply(
        self, state: SearchState, refinement: SearchRefinement, *, message: str,
        expected_revision: int,
    ) -> SearchState:
        if expected_revision != state.revision:
            raise RevisionConflictError(
                f"stale search state: expected revision {expected_revision}, current revision is {state.revision}"
            )
        base = FashionSearchConstraints(currency=state.constraints.currency) if refinement.reset_search else state.constraints
        payload: dict[str, Any] = base.model_dump()
        for update in refinement.updates:
            if update.operation == "KEEP":
                continue
            if update.operation in {"REMOVE", "RELAX"}:
                payload[update.field] = None
                continue
            payload[update.field] = update.value
            if update.field in {"price_min", "price_max"}:
                payload[f"{update.field}_inclusive"] = update.inclusive
        try:
            candidate = FashionSearchConstraints.model_validate(payload)
            normalized = normalize_constraints(candidate, currency=candidate.currency)
        except (ValidationError, ValueError) as exc:
            raise StateTransitionError(str(exc)) from exc
        for update in refinement.updates:
            if update.operation == "SET" and update.field in {
                "category", "color", "occasion", "size", "gender"
            } and getattr(normalized, update.field) is None:
                raise StateTransitionError(f"unsupported {update.field}: {update.value}")

        modifiers = [] if refinement.reset_search else list(state.semantic_modifiers)
        semantic_query = message.strip() if refinement.reset_search else state.semantic_query
        if refinement.semantic_refinement:
            term = refinement.semantic_refinement.strip()
            if term and term.casefold() not in {item.casefold() for item in modifiers}:
                modifiers.append(term)
        return SearchState(
            original_query=message.strip() if refinement.reset_search else state.original_query,
            current_query=message.strip(), constraints=normalized,
            semantic_query=semantic_query, semantic_modifiers=modifiers,
            sort_preference=refinement.sort_preference or (
                "RELEVANCE" if refinement.reset_search else state.sort_preference
            ),
            revision=state.revision + 1,
        )


def active_filters(state: SearchState) -> list[ActiveFilter]:
    """Build stable human-readable filter chips without generation."""
    c = state.constraints
    rows: list[ActiveFilter] = []
    labels = {"category": "Category", "color": "Color", "occasion": "Occasion", "size": "Size", "gender": "Gender"}
    for key, label in labels.items():
        value = getattr(c, key)
        if value:
            rows.append(ActiveFilter(key=key, label=label, value=value.title()))
    symbol = "₹" if c.currency == "INR" else f"{c.currency} "
    money = lambda value: f"{symbol}{value:,.0f}"
    if c.price_min is not None:
        rows.append(ActiveFilter(key="price_min", label="Price", value=f"Over {money(c.price_min)}"))
    if c.price_max is not None:
        rows.append(ActiveFilter(key="price_max", label="Price", value=f"Under {money(c.price_max)}"))
    return rows
