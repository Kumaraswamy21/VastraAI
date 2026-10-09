# VastraAI architecture

The Next.js App Router frontend calls the FastAPI API. SQLAlchemy accesses one PostgreSQL database containing products, pgvector embeddings, a weighted full-text `tsvector`, and observability events. Alembic owns schema changes. The seeded catalog has 750 deterministic synthetic products; it has no product photography, only color swatches in the current UI.

```text
Natural-language request
  -> constraint extraction (generation provider, then deterministic fallback)
  -> structured SearchState (initial or delta-based refinement)
  -> semantic query plus compatible query embedding -> pgvector candidates
  -> normalized keyword query -> PostgreSQL full-text candidates
  -> reciprocal-rank fusion -> exact metadata filters -> deduplication
  -> grounded match explanations -> API results and active-filter chips
```

The hybrid search orchestrator records stage durations, candidate counts, search mode, and fallback state. If the compatible embedding index or query embedding is unavailable, the keyword channel can still serve results. It never silently loosens exact filters. Zero exact matches retain the requested filters and return diagnostic suggestions.

## Conversation and sessions

`SearchState` owns the current constraints, original/current query, semantic query/modifiers, sort order, and revision. A follow-up interpreter returns only `SET`, `REMOVE`, or comparative changes; the deterministic reducer validates the full next state and preserves unmentioned fields. Structured chip removal uses the same reducer. Clients supply `expected_revision`; stale updates receive HTTP 409. “Cheaper” sorts ascending without inventing a price cap. A clearly different category can reset incompatible context.

The API's session store is **process-local memory**. The browser also keeps the latest response in `sessionStorage`, so same-tab refresh and product-page navigation restore its view while that backend process remains alive. A backend restart or routing to another worker invalidates that session (HTTP 404); browser storage is not durable server state. Do not deploy multiple backend workers expecting shared conversations.

## Provider boundary and vector compatibility

Search code uses `GenerationProvider` and `EmbeddingProvider`; Gemini and Ollama SDK details stay behind those interfaces. Provider wrappers record individual attempts, including fallback. Generation and embedding providers may differ. Query and product embeddings must use the **same provider, model, and dimensions**: Gemini+Gemini and Ollama+Ollama are valid; Gemini product vectors with an Ollama query vector are invalid. Re-embed the catalog after changing its embedding model/space. The query path checks stored vector compatibility and degrades to keyword search when necessary.

## Observability and evaluation

Provider and search events share a request correlation ID. They record operational metadata, timings, results, and token usage when available, without storing prompts by default. Telemetry writes fail open. Developer API routes under `/dev/observability` are disabled when `APP_ENVIRONMENT=production`; the frontend dashboard at `/dev/observability` is for local development only, **not authenticated admin access**.

The versioned, human-labelled evaluation under `backend/evaluation/` runs in deterministic `offline_keyword` mode against a checksum-pinned catalog. It assesses extraction, ranked retrieval, hard constraints, empty results, conversation transitions, explanations, and latency. It does **not** measure live hybrid quality or provider cost. See [the evaluation guide](../backend/evaluation/README.md).
