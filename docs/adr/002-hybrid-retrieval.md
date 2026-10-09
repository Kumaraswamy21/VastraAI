# ADR-002: Hybrid retrieval

Status: Accepted

Context: Literal fashion attributes and descriptive shopping language require different retrieval signals.

Decision: Fuse pgvector and PostgreSQL weighted full-text candidates with reciprocal-rank fusion, then enforce exact metadata constraints and explain results from structured evidence.

Alternatives considered: Semantic-only or keyword-only search.

Consequences: Keyword fallback remains available when embeddings fail; semantic/keyword weights need evidence-based tuning. Offline keyword evaluation alone does not validate hybrid quality.
