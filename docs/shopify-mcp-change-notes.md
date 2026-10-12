# Shopify MCP change notes

## What changed

VastraAI can search Shopify Global Catalog as a separate provider. The existing VastraAI search remains the default. Shopify results are fetched live, mapped into product cards, and are not saved in the app database.

The backend uses Shopify's MCP endpoint and `search_catalog` tool. It handles timeouts and MCP errors, applies the configured country, and maps product title, price, currency, image, merchant, availability, product URL, and variants when present.

The search page now opens with **Shopify** selected, so new VastraAI searches use live catalog results by default. The **VastraAI** provider remains available in the selector for local catalog search.

The Shopify landing screen now has a custom fashion editorial graphic and quick search ideas. After a search, a shopping chat sits beside the live product grid on wide screens and below it on small screens. Chat product links point to current merchant listings.

Shopify searches now support follow-up requests in the same temporary search session. Users can change filters in natural language, edit minimum and maximum prices, remove filter chips, and sort by price. Each update makes a fresh MCP request. Price controls filter listed offers; they do not change seller prices.

Questions such as “Which one is best for summer?” can receive a grounded VastraAI answer. The answer uses only the current live result page, validates product references and claims, and includes links to referenced products. Shopify products and RAG context are not saved in PostgreSQL. Shopify retrieval is handled by Shopify's catalog search; local vector search does not run over Shopify items.

## Configuration

Shopify search is off by default. The backend configuration supports:

- `SHOPIFY_CATALOG_ENABLED`
- `SHOPIFY_MCP_URL`
- `SHOPIFY_TOKEN_URL`
- `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`
- `SHOPIFY_AGENT_PROFILE_URL`
- `SHOPIFY_CATALOG_COUNTRY`
- `SHOPIFY_MCP_TIMEOUT_SECONDS`
- `SHOPIFY_RAG_MODEL` (defaults to `gemini-3.5-flash-lite`)

Keep credentials in the local environment file or deployment secret store. Do not put credentials in Git.

## Manual check in Docker

Open [http://localhost:3000](http://localhost:3000), select **Shopify**, and search for a product. A live check of `blue cotton kurta under INR 1500` returned three INR products with images, merchant names, availability, and merchant product links. The API route is `POST /search?provider=shopify`.

For this manual run, Shopify was enabled with a temporary Docker Compose override and Shopify's public example agent profile. The override is under `/tmp`, not in the repository. Recreating the backend with the normal Compose configuration may turn Shopify off again; set the Shopify values in your local environment configuration to keep it enabled across restarts.

The app's health endpoint returned `status: ok`, with both backend and database reporting `ok`. The frontend returned HTTP 200.

## Files changed for Shopify

- Backend: `backend/src/fashion_search/api/search.py`, `backend/src/fashion_search/api/shopify.py`, `backend/src/fashion_search/main.py`
- Live Shopify RAG: `backend/src/fashion_search/rag/shopify.py`
- Backend client and mapping: `backend/src/fashion_search/shopify/`
- Settings and example configuration: `backend/src/fashion_search/config/settings.py`, `.env.example`
- Frontend: `frontend/app/search-view.tsx`, `frontend/app/shopify-search-panel.tsx`, `frontend/app/shopify-chat-panel.tsx`, `frontend/lib/api.ts`
- Focused tests: `backend/tests/test_search_provider_api.py`, `backend/tests/test_shopify_rag.py`, `backend/tests/test_shopify_mapping.py`, `backend/tests/test_shopify_mcp.py`
- Project docs: `README.md`, `docs/architecture.md`, `docs/deployment.md`

## Verification notes

Focused Shopify API, MCP, mapping, RAG, local conversation, and local RAG tests pass. Frontend linting, type checking, and production build pass. Live Shopify search, price filtering, and a grounded RAG answer pass. Shopify uses its own Gemini model setting because the previous configured model returned 404; the local search model setting is unchanged.

This note is not committed. No database schema changes were made.
