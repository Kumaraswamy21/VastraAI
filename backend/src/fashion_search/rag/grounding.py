"""Validated structured RAG selection and catalog-backed answer rendering."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GroundedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_id: int
    attribute: Literal[
        "category",
        "color",
        "material",
        "style",
        "occasion",
        "gender",
        "price_inr",
        "sizes",
    ]
    value: str = Field(min_length=1, max_length=160)


class GroundedGeneration(BaseModel):
    """Model-selected products and exact catalog claims; no free-form answer text."""

    model_config = ConfigDict(extra="forbid")
    answer_kind: Literal["summary", "comparison", "explanation"]
    referenced_product_ids: list[int] = Field(min_length=1, max_length=12)
    claims: list[GroundedClaim] = Field(default_factory=list, max_length=24)


class GroundingValidationError(ValueError):
    def __init__(self, message: str, *, invalid_reference: bool = False) -> None:
        super().__init__(message)
        self.invalid_reference = invalid_reference


def _values(product: dict, attribute: str) -> set[str]:
    value = product.get(attribute)
    if attribute == "price_inr" and value is not None:
        return {str(value), f"₹{value:,}"}
    if isinstance(value, list):
        return {str(item).casefold() for item in value}
    return {str(value).casefold()} if value is not None else set()


def validate_grounded_generation(
    generated: GroundedGeneration, context: list[dict]
) -> GroundedGeneration:
    """Reject unknown references and claims that do not exactly match context."""
    available = {int(row["product_id"]): row for row in context}
    if len(generated.referenced_product_ids) != len(
        set(generated.referenced_product_ids)
    ):
        raise GroundingValidationError(
            "duplicate product reference", invalid_reference=True
        )
    if any(
        product_id not in available for product_id in generated.referenced_product_ids
    ):
        raise GroundingValidationError(
            "product reference outside retrieval context", invalid_reference=True
        )
    refs = set(generated.referenced_product_ids)
    for claim in generated.claims:
        if claim.product_id not in refs:
            raise GroundingValidationError(
                "claim product was not referenced", invalid_reference=True
            )
        supported = _values(available[claim.product_id], claim.attribute)
        if claim.value.casefold() not in supported:
            raise GroundingValidationError(
                "claim value is not present in catalog context"
            )
    return generated


def render_grounded_answer(generated: GroundedGeneration, context: list[dict]) -> str:
    """Compose concise prose exclusively from validated catalog values."""
    rows = {int(row["product_id"]): row for row in context}
    titles = [
        str(rows[pid].get("title", "this option"))
        for pid in generated.referenced_product_ids
    ]
    if not generated.claims:
        return f"I found {len(titles)} option{'s' if len(titles) != 1 else ''} matching your preferences."
    clauses: list[str] = []
    for claim in generated.claims[:4]:
        title = str(rows[claim.product_id].get("title", "This option"))
        label = {
            "category": "category",
            "color": "color",
            "material": "material",
            "style": "style",
            "occasion": "occasion",
            "gender": "audience",
            "price_inr": "listed price",
            "sizes": "size",
        }[claim.attribute]
        value = (
            f"₹{int(claim.value):,}"
            if claim.attribute == "price_inr" and claim.value.isdigit()
            else claim.value
        )
        clauses.append(f"{title} lists {label} as {value}")
    prefix = {
        "summary": "I found options matching your preferences. ",
        "comparison": "Here are the catalog details to compare. ",
        "explanation": "The catalog describes these options as follows. ",
    }[generated.answer_kind]
    return prefix + "; ".join(clauses) + "."
