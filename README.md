# VastraAI

VastraAI is a fashion discovery app with conversational search, exact catalog filters, PostgreSQL full-text retrieval, optional compatible-space semantic retrieval, and concise grounded product answers. The current release candidate is **v2.0.0**; it has not been committed, tagged, or published. It uses a synthetic catalog and is not a storefront: there is no live inventory, checkout, account, or product photography.

## Screenshots

Captured from the running product (color swatches represent the synthetic catalog's image placeholders): [catalog](docs/images/01-catalog.png), [natural-language search](docs/images/02-natural-language-search.png), [conversational refinement](docs/images/03-conversational-refinement.png), and [active filters/results](docs/images/04-search-results-filters.png). These captures predate a health-label wording fix (`Neon` → `Database`). Product-detail, dashboard, and mobile captures remain outstanding; no mockups are presented as screenshots.

## What works

- Browse 750 deterministic synthetic products, inspect product details, and search in natural language.
- Parse category, color, occasion, size, gender, and INR price constraints; exact filters remain authoritative.
- Fuse pgvector and PostgreSQL full-text candidates with reciprocal-rank fusion; fall back to keyword search when semantic search is unavailable.
- Refine a search with messages or remove active-filter chips. State revisions reject stale requests.
- Ask contextual questions about retrieved products; answers use bounded catalog context and validated product references. Deterministic filter changes continue to skip generation.
- Inspect developer-only provider/search telemetry and run a 40-query offline evaluation against a pinned catalog.
- Compare keyword, semantic, hybrid, and hybrid-plus-grounding evaluation modes; RAG evaluation includes deterministic adversarial grounding checks.

See [architecture](docs/architecture.md) and [ADRs](docs/adr/).

For hosted deployment, see the [Vercel + Render + Neon deployment guide](docs/deployment.md).

## Prerequisites

- Docker Engine with Compose (for PostgreSQL 16 + pgvector; optionally the app containers).
- Python 3.12 and Node.js 22 with npm (for host development). The Dockerfiles use these versions.
- Optional: a Gemini API key, or a local Ollama server and the configured generation/embedding models. Standard tests and offline evaluation use neither.

## Quick start (host app, Docker database)

From the repository root:

```sh
cp .env.example .env
docker compose up -d db
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
cd backend
.venv/bin/alembic upgrade head
.venv/bin/seed-catalog
cd ../frontend
npm ci
```

Set `GEMINI_API_KEY` in `.env` if using the default Gemini configuration. Without an available provider, catalog browsing works and search can degrade to keyword retrieval; some generation calls will first fail and fall back to deterministic parsing. To run the backend and frontend in separate terminals from the root:

```sh
cd backend && .venv/bin/python -m uvicorn fashion_search.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

Open <http://localhost:3000>; API health is <http://localhost:8000/health>. For an all-container run, use `docker compose up --build -d`, then run `docker compose exec backend alembic upgrade head` and `docker compose exec backend seed-catalog` before searching. `docker compose` overrides the backend's database host to the internal `db` service. The documented local password is development-only; change it before exposing the database.

The seed is idempotent for an already seeded catalog. **For evaluation**, seed a truly fresh database: product IDs are part of its pinned snapshot. A failed insert can consume a PostgreSQL sequence value even when it rolls back, making an otherwise identical catalog fail the checksum check.

## Configuration and provider modes

Copy [`.env.example`](.env.example); it lists supported settings. The local `DATABASE_URL` explicitly uses `sslmode=disable`; a hosted PostgreSQL/pgvector URL can instead use `sslmode=require`. `CORS_ORIGINS` should include the frontend origin. Do not commit `.env`.

`GENERATION_PROVIDER` and `EMBEDDING_PROVIDER` accept `gemini` or `ollama`. `GENERATION_FALLBACK_PROVIDER` is optional. Gemini uses `GEMINI_API_KEY`; Ollama uses `OLLAMA_BASE_URL`, `OLLAMA_GENERATION_MODEL`, and `OLLAMA_EMBEDDING_MODEL`. Start Ollama and pull those models yourself for local-provider mode. Mixed generation and embedding providers are supported, but **query and catalog vectors must use the same embedding provider, model, and dimensions**. After changing embedding configuration, run `cd backend && .venv/bin/embed-catalog` to re-index; this calls the configured embedding provider and can incur API cost. A new seed has no completed embeddings, so it initially serves keyword fallback. Do not assume Gemini vectors are compatible with Ollama query vectors.

Shopify Global Catalog search is an optional, separate provider. Set `SHOPIFY_CATALOG_ENABLED=true`, the Shopify Dev Dashboard `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`, and `SHOPIFY_AGENT_PROFILE_URL` for a UCP profile that declares catalog search and Shopify's Global Catalog capability. The backend exchanges the credentials for a short-lived access token. `SHOPIFY_CATALOG_COUNTRY` sets the buyer country used for availability and localization. Shopify results are fetched live, are not saved to the local database, and open on the merchant's product page. Shopify's catalog usage guidelines prohibit caching search results and require images to be displayed from their live product URLs. See [Global Catalog MCP](https://shopify.dev/docs/agents/catalog/global-catalog), [authentication](https://shopify.dev/docs/agents/get-started/authentication), and [catalog usage guidelines](https://shopify.dev/docs/agents/catalog).

## Tests and build

With the local database migrated and seeded, run:

```sh
cd backend
.venv/bin/ruff format --check .
.venv/bin/ruff check src tests migrations
.venv/bin/python -m unittest discover -s tests -q
cd ../frontend
npm run lint
npx tsc --noEmit
npm test
npm run build
```

The backend suite includes mocked provider contracts, evaluation metric tests, and database integration tests; the one live Gemini test is opt-in with `RUN_GEMINI_INTEGRATION=1`. Run integration tests against a disposable database: they update a few product embedding fields and restore them, and must not share a production catalog. The frontend build uses Next's supported webpack builder because the default Turbopack build failed to bind a worker port in this development environment. GitHub Actions runs lint, tests, migrations, a seeded offline evaluation, frontend build, and both Docker image builds without provider secrets.

## Search evaluation

The dataset [`fashion_search_v1.json`](backend/evaluation/datasets/fashion_search_v1.json) has 40 cases and three conversational sequences. It pins `synthetic-seed-20261007-count-750-v1` with SHA-256 `eb804e475515946fa7919f8fe3a509cfab49759f16725c03b1058c07054ab8af`. See the [evaluation guide](backend/evaluation/README.md) for the `offline_keyword`, `semantic`, `hybrid`, and `hybrid_rag` modes and metric definitions. From `backend/`:

```sh
.venv/bin/python -m fashion_search.evaluation.runner --output evaluation/results/current.json
.venv/bin/python -m fashion_search.evaluation.compare evaluation/results/baseline.json evaluation/results/current.json
```

`current.json` is ignored; inspect its per-query details and do not compare different dataset/catalog versions as if equivalent. The checked-in [historical baseline](backend/evaluation/results/baseline.json) was a measured offline keyword run. The [v2.0.0 release notes](docs/releases/v2.0.0.md) record current evaluation results and limitations. The deterministic `hybrid_rag` mode does not call a live text generator; it measures retrieval and grounding safeguards, not generated-answer quality, provider latency, or cost. Semantic evaluation requires a ready compatible embedding index.

## Developer observability

In development, open <http://localhost:3000/dev/observability>. The backend exposes `/dev/observability/summary`, `/providers`, `/search`, and `/requests/{request_id}`; search responses also include a correlation ID. Provider/model, outcome, latency, fallback attempts, token usage when available, estimated API cost when configured, stage timings, counts, and search mode can be inspected. Raw prompts are not persisted by default. These routes are disabled for `APP_ENVIRONMENT=production`, but there is **no admin authentication**: do not expose the development dashboard publicly. `OBSERVABILITY_RETENTION_DAYS` configures retention; run `cd backend && .venv/bin/cleanup-observability` manually if no scheduler is installed.

## Known limitations and next steps

- The seed has no wedding dresses; a black wedding dress request correctly yields `no_exact_matches`. Some descriptive queries are false-empty in offline keyword mode. Catalog metadata and sample size constrain quality.
- Search sessions live in one backend process. Same-tab refresh restores the browser view while that process survives, but restart or another worker loses the session. PostgreSQL-backed sessions with expiry and atomic revisions are the next persistence milestone.
- A freshly seeded catalog has no embeddings. Semantic retrieval requires an explicit `embed-catalog` pass with a configured provider/model. The v2 evaluation run found no ready compatible index, so hybrid used its FTS fallback and semantic-only returned no products.
- The 40-query labels and synthetic catalog are limited; no production load test or authenticated developer dashboard exists. Python runtime dependencies use minimum versions rather than a lockfile. The current full npm audit reports five high-severity advisories in development-only ESLint dependencies; production dependencies report zero findings.

Priorities: (1) complete v2 release gates, (2) persist sessions across backend workers/restarts, (3) expand catalog and evaluation labels, and (4) measure live hybrid/RAG quality and cost. See the [v2 release checklist](docs/release-checklist.md), [v2.0.0 candidate notes](docs/releases/v2.0.0.md), and the [historical v0.1.0 candidate](docs/releases/v0.1.0.md). A version bump is not evidence of deployment.
