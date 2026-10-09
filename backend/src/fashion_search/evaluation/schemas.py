"""Versioned human-authored evaluation dataset schemas."""

from pydantic import BaseModel, ConfigDict, Field

from fashion_search.search.schemas import FashionSearchConstraints


class EvaluationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    query: str = Field(min_length=1)
    query_type: list[str] = Field(min_length=1)
    expected_filters: FashionSearchConstraints = Field(
        default_factory=FashionSearchConstraints
    )
    relevance: dict[int, int] = Field(default_factory=dict)
    judgments_complete: bool = False
    expected_empty: bool | None = None
    weak_case: bool = False

    @classmethod
    def from_dataset(cls, row: dict) -> "EvaluationQuery":
        return cls.model_validate(row)


class ConversationTurn(BaseModel):
    message: str
    expected_state: FashionSearchConstraints


class EvaluationConversation(BaseModel):
    id: str
    turns: list[ConversationTurn] = Field(min_length=2)


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version: str
    catalog_snapshot_id: str
    catalog_snapshot_sha256: str
    labeling_guide: str
    queries: list[EvaluationQuery] = Field(min_length=30)
    conversations: list[EvaluationConversation] = Field(default_factory=list)
