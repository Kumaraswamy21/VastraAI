# ADR-004: Structured SearchState

Status: Accepted

Context: Re-parsing chat history can drop earlier constraints and obscure intent.

Decision: Keep explicit state and apply validated delta updates through a deterministic reducer. Use revisions to reject stale follow-ups.

Alternatives considered: Replacing state with every LLM response; raw transcript as authority.

Consequences: Predictable filter preservation and chip removal. Current process-local storage limits restart safety and multi-worker deployment.
