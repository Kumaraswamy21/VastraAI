# ADR-005: Grounded explanations

Status: Accepted

Context: Search cards must not claim unsupported attributes.

Decision: Build match reasons from retrieved product metadata and observed ranking/filter evidence, without a second LLM call.

Alternatives considered: Free-form generated explanations.

Consequences: Factual, testable copy with lower latency; style nuance is limited by catalog metadata quality.
