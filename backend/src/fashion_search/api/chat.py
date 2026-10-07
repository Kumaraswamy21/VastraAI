"""Conversational shopping turns. Domain guard and generation start on Day 4."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fashion_search.catalog.schemas import ProductRecord

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatTurnRequest(BaseModel):
    """One customer message in a shopping session."""

    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatTurnResponse(BaseModel):
    """Assistant reply: products, a clarification question, or a domain refusal."""

    session_id: str
    reply: str
    needs_clarification: bool = False
    off_topic: bool = False
    products: list[ProductRecord] = Field(default_factory=list)


@router.post("", response_model=ChatTurnResponse)
def chat_turn(_body: ChatTurnRequest) -> ChatTurnResponse:
    """Handle a conversational shopping turn. Day 4 implements this path."""
    raise HTTPException(
        status_code=501,
        detail="Chat is not implemented on Day 1.",
    )
