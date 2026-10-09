# ADR-003: Provider-neutral AI interfaces

Status: Accepted

Context: Gemini is hosted; Ollama can run locally. Either may fail or be configured independently for generation and embeddings.

Decision: Business logic depends on `GenerationProvider` and `EmbeddingProvider`; provider implementations and instrumented wrappers own SDK calls and telemetry.

Alternatives considered: Direct SDK calls in search services; an agent framework.

Consequences: Mockable CI and per-attempt fallback visibility. Mixed generation/embedding providers are allowed, but query/product vectors still need the same embedding space.
