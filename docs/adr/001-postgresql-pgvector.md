# ADR-001: PostgreSQL and pgvector

Status: Accepted

Context: Products need transactional metadata filtering and vector similarity.

Decision: Keep catalog data and embeddings in PostgreSQL, using pgvector for compatible-space cosine retrieval.

Alternatives considered: A separate vector database; local files.

Consequences: One migration/backup surface and exact-filter joins; embedding model changes require re-indexing, and PostgreSQL/pgvector must be available locally and in CI.
