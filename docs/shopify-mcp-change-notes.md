# Shopify MCP change notes

## What changed

VastraAI can search Shopify Global Catalog as a separate provider. The existing VastraAI search remains the default. Shopify results are fetched live, mapped into product cards, and are not saved in the app database.

The backend uses Shopify's MCP endpoint and `search_catalog` tool. It handles timeouts and MCP errors, applies the configured country, and maps product title, price, currency, image, merchant, availability, product URL, and variants when present.

The search page now has a **Shopify** provider option. Choose it, enter a query, and submit to see the returned product cards and merchant links.

## Configuration

Shopify search is off by default. The backend configuration supports:

- `SHOPIFY_CATALOG_ENABLED`
- `SHOPIFY_MCP_URL`
- `SHOPIFY_TOKEN_URL`
- `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`
- `SHOPIFY_AGENT_PROFILE_URL`
- `SHOPIFY_CATALOG_COUNTRY`
- `SHOPIFY_MCP_TIMEOUT_SECONDS`

Keep credentials in the local environment file or deployment secret store. Do not put credentials in Git.

## Manual check in Docker

Open [http://localhost:3000](http://localhost:3000), select **Shopify**, and search for a product. A live check of `blue cotton kurta under INR 1500` returned three INR products with images, merchant names, availability, and merchant product links. The API route is `POST /search?provider=shopify`.

For this manual run, Shopify was enabled with a temporary Docker Compose override and Shopify's public example agent profile. The override is under `/tmp`, not in the repository. Recreating the backend with the normal Compose configuration may turn Shopify off again; set the Shopify values in your local environment configuration to keep it enabled across restarts.

The app's health endpoint returned `status: ok`, with both backend and database reporting `ok`. The frontend returned HTTP 200.

## Files changed for Shopify

- Backend: `backend/src/fashion_search/api/search.py`, `backend/src/fashion_search/api/shopify.py`, `backend/src/fashion_search/main.py`
- Backend client and mapping: `backend/src/fashion_search/shopify/`
- Settings and example configuration: `backend/src/fashion_search/config/settings.py`, `.env.example`
- Frontend: `frontend/app/search-view.tsx`, `frontend/app/shopify-search-panel.tsx`, `frontend/lib/api.ts`
- Focused tests: `backend/tests/test_search_provider_api.py`, `backend/tests/test_shopify_mapping.py`, `backend/tests/test_shopify_mcp.py`
- Project docs: `README.md`, `docs/architecture.md`, `docs/deployment.md`

## Verification notes

Focused Shopify tests and the live catalog request have been run. Frontend linting, type checking, and production build passed. The full backend suite had existing failures related to database DNS access and unrelated assertions; those are recorded in the validation report from the integration work.

This note is not committed. No database schema changes or frontend redesign were made for Shopify search.
