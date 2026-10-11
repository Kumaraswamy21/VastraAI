# VastraAI architecture

The Next.js App Router frontend calls the FastAPI API. SQLAlchemy accesses one PostgreSQL database containing products, pgvector embeddings, a weighted full-text `tsvector`, and observability events. Alembic owns schema changes. The seeded catalog has 750 deterministic synthetic products; it has no product photography, only color swatches in the current UI.

```text
User query or conversation turn
  -> current SearchState and authoritative exact constraints
  -> compatible query embedding -> pgvector candidates (when available)
  -> normalized query -> PostgreSQL full-text candidates
  -> existing reciprocal-rank fusion and exact metadata filtering
  -> product cards and grounded match explanations
  -> for contextual product questions only: bounded product context
  -> existing GenerationProvider -> structured claim/reference validation
  -> concise catalog-grounded answer alongside the products
```

The hybrid search orchestrator records stage durations, candidate counts, search mode, and fallback state. If the compatible embedding index or query embedding is unavailable, the keyword channel can still serve results. It never silently loosens exact category, color-family, occasion, size, gender, or price filters. Broad color requests such as blue match the catalog's blue shades; named shades such as navy blue remain exact. Zero exact matches retain the requested filters and return diagnostic suggestions.

## Grounded product answers

RAG consumes only the final products returned by the current search. Context is an allowlist of useful catalog fields with configurable top-K and description limits; it excludes vectors, ranking internals, and database metadata. The existing generation provider returns structured product references and attribute claims. Pydantic validation rejects references outside the supplied context and claims whose values do not match catalog data. The server renders the short answer from validated claims; raw model prose is not displayed. Missing catalog fields stay unknown. Empty results, filter changes, and deterministic confirmations do not invoke RAG. Provider failures preserve the product response and use a safe fallback.

## Conversation and sessions

`SearchState` owns the current constraints, original/current query, semantic query/modifiers, sort order, and revision. A follow-up interpreter returns only `SET`, `REMOVE`, or comparative changes; the deterministic reducer validates the full next state and preserves unmentioned fields. Structured chip removal uses the same reducer. Clients supply `expected_revision`; stale updates receive HTTP 409. “Cheaper” sorts ascending without inventing a price cap. A clearly different category can reset incompatible context.

The API's session store is **process-local memory**. The browser also keeps the latest response in `sessionStorage`, so same-tab refresh and product-page navigation restore its view while that backend process remains alive. A backend restart or routing to another worker invalidates that session (HTTP 404); browser storage is not durable server state. Do not deploy multiple backend workers expecting shared conversations.

## Provider boundary and vector compatibility

Search code uses `GenerationProvider` and `EmbeddingProvider`; Gemini and Ollama SDK details stay behind those interfaces. Provider wrappers record individual attempts, including fallback. Generation and embedding providers may differ. Query and product embeddings must use the **same provider, model, and dimensions**: Gemini+Gemini and Ollama+Ollama are valid; Gemini product vectors with an Ollama query vector are invalid. Re-embed the catalog after changing its embedding model/space. The query path checks stored vector compatibility and degrades to keyword search when necessary.

## Shopify Global Catalog provider

When enabled, `POST /search/shopify` calls Shopify Global Catalog MCP as a separate live provider. It uses a dedicated response model and frontend panel; Shopify IDs, currencies, seller URLs, and image URLs do not enter the local product schema, search fusion, RAG context, or PostgreSQL. The backend requires a configured UCP agent profile URL. Results are not cached, and product images are rendered from their returned live URLs next to the associated merchant listing. See the [deployment guide](deployment.md) for settings.

## Observability and evaluation

Provider and search events share a request correlation ID. They record operational metadata, retrieval and RAG timings, context count/size, generation provider/model, grounding failures, results, and token usage when available, without storing prompts by default. Telemetry writes fail open. Developer API routes under `/dev/observability` are disabled when `APP_ENVIRONMENT=production`; the frontend dashboard at `/dev/observability` is for local development only, **not authenticated admin access**.

The versioned, human-labelled evaluation under `backend/evaluation/` supports deterministic offline FTS and semantic/hybrid modes against the same checksum-pinned catalog. The `hybrid_rag` mode adds deterministic adversarial grounding checks but does not call a live text generator. Thus it does not measure generated-answer quality, live RAG latency, or provider cost. See [the evaluation guide](../backend/evaluation/README.md) and [v2.0.0 release notes](releases/v2.0.0.md).
