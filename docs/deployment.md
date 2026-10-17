# Deployment

The repository contains a Next.js frontend and a FastAPI backend. A straightforward hosted setup is Vercel for the frontend, Render for the backend, and your existing Neon Postgres database with the `vector` extension. Vercel and Render can deploy from the GitHub repository when their configured branch changes. GitHub Actions remains the CI workflow; production secrets do not need to be copied into Actions.

## 1. Connect the backend to Neon

1. In Neon, copy the connection string for the database branch this app should use. Prefer a dedicated Neon database or branch so this app's tables and synthetic catalog stay isolated from other applications.
2. Create a Web Service from this repository in Render. Select the Docker runtime, leave **Root Directory** blank (repository root), set **Dockerfile Path** to `backend/Dockerfile`, and set **Docker Context** to `backend`. These paths are relative to the service root; do not set Root Directory to `backend` at the same time. Alternatively, if Root Directory is `backend`, use Dockerfile Path `Dockerfile` and Docker Context `.`.
3. Add the environment variables below in the service's Environment settings. Set secret values there; do not commit them to `.env.example` or GitHub Actions.
4. Deploy the backend Docker service. Its startup command runs `alembic upgrade head` before starting the API, including on plans without a service shell or pre-deploy command. If a migration fails, the API will not start; check the Render deploy log for the Alembic error.
5. After the service starts, copy its public URL (for example, `https://vastraai-api.onrender.com`).

Use the `DATABASE_URL` from Neon's Connect dialog. A direct connection is suitable for this persistent FastAPI service; use Neon's pooled connection string if you need to limit database connections. The app adds `sslmode=require` if the URL does not include an SSL mode. The first Alembic migration enables pgvector with `CREATE EXTENSION IF NOT EXISTS vector`.

Search sessions are stored in PostgreSQL and can be served by multiple backend instances after migrations run.

| Render variable | Value |
| --- | --- |
| `DATABASE_URL` | Neon connection string for the intended database/branch |
| `CORS_ORIGINS` | The exact Vercel production origin, such as `https://vastraai.vercel.app` |
| `APP_ENVIRONMENT` | `production` |
| `OBSERVABILITY_DASHBOARD_ENABLED` | `false` |
| `AUTH_JWT_SECRET` | New random secret of at least 32 characters for production, identical in Render and Vercel; keep it different from `NEXTAUTH_SECRET` |
| `AUTH_FRONTEND_URL` | Exact public Vercel origin, such as `https://vastraai.vercel.app`, used in verification and reset emails |
| `AUTH_EMAIL_FROM` | Sender address accepted by your SMTP provider; required for email/password registration and reset |
| `AUTH_SMTP_HOST`, `AUTH_SMTP_PORT` | SMTP server and port; the app defaults to port `587` |
| `AUTH_SMTP_USERNAME`, `AUTH_SMTP_PASSWORD` | SMTP login values when the server requires authentication |
| `AUTH_SMTP_STARTTLS` | `true` for an SMTP server that supports STARTTLS, or `false` if your server does not |
| `AUTH_ADMIN_EMAILS` | Comma-separated verified account emails allowed to view observability; leave blank to deny all |
| `GEMINI_API_KEY` | Gemini key, if using Gemini |
| `GENERATION_PROVIDER` | `gemini` or `ollama` |
| `GENERATION_MODEL` | Gemini generation model; if blank, `SEARCH_PARSER_MODEL` is used |
| `SEARCH_PARSER_MODEL` | Gemini model used when `GENERATION_MODEL` is blank |
| `GENERATION_FALLBACK_PROVIDER` | Optional `gemini` or `ollama`; blank disables fallback |
| `EMBEDDING_PROVIDER` | `gemini` or `ollama` |
| `EMBEDDING_MODEL` | Gemini embedding model |
| `EMBEDDING_DIMENSIONS` | Output dimension for the selected Gemini embedding model |
| `OLLAMA_BASE_URL` | Reachable Ollama service URL; `localhost` refers to the backend container, not your computer |
| `OLLAMA_GENERATION_MODEL` | Ollama generation model |
| `OLLAMA_EMBEDDING_MODEL` | Ollama embedding model |
| `OLLAMA_EMBEDDING_DIMENSIONS` | Output dimension of the selected Ollama embedding model |
| `SHOPIFY_CATALOG_ENABLED` | Set `true` to enable the separate Shopify search endpoint |
| `SHOPIFY_CLIENT_ID` | Optional Shopify Dev Dashboard Catalogs API client ID; leave blank with the secret for keyless access |
| `SHOPIFY_CLIENT_SECRET` | Optional Shopify Dev Dashboard Catalogs API client secret; leave blank with the ID for keyless access |
| `SHOPIFY_AGENT_PROFILE_URL` | HTTPS URL for a UCP agent profile with catalog search and Shopify Global Catalog capabilities |
| `SHOPIFY_MCP_URL` | Global Catalog MCP endpoint; defaults to Shopify's endpoint |
| `SHOPIFY_TOKEN_URL` | OAuth token endpoint; defaults to Shopify's endpoint |
| `SHOPIFY_CATALOG_COUNTRY` | ISO country code used for shipping availability and localization, such as `IN` |
| `SHOPIFY_MCP_TIMEOUT_SECONDS` | Shopify request timeout; defaults to 10 seconds |
| `SHOPIFY_RAG_MODEL` | Gemini model used for Shopify grounded answers; defaults to `gemini-3.5-flash-lite` |

Only set the provider-specific values you use. If Neon has IP restrictions enabled, allow connections from the Render service's outbound IP addresses.

Shopify search is disabled unless explicitly enabled with an agent profile URL. With both client credentials blank, the app sends anonymous requests without an Authorization header. Shopify applies its lowest rate limits to that tier and advises against anonymous production traffic. When both credentials are configured, the backend caches only the access token in process memory and refreshes it before its documented 60-minute expiry. Product data is returned live and is not persisted by this app. Shopify search results must not be cached; product images are loaded directly from Shopify and shown with their merchant product link.

After the first deploy and successful migration, run `seed-catalog` once if the database has not already been seeded. This loads the repo's 750 synthetic products into Neon. The seed is idempotent for an already seeded catalog. On a plan without a service shell, run the command against the same Neon database from a trusted local checkout or CI job.

## 2. Create the frontend on Vercel

1. Import the same GitHub repository as a Vercel project.
2. Set the project Root Directory to `frontend` and leave Next.js as the detected framework.
3. Set `BACKEND_API_URL` to the Render backend origin, with no trailing slash. Set `NEXTAUTH_URL` to the exact public Vercel origin and `NEXTAUTH_SECRET` to a new random value of at least 32 characters. Set `AUTH_JWT_SECRET` to the same value configured in Render. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` from a Google OAuth **Web application** client. Register `https://<your-vercel-domain>/api/auth/callback/google` as an authorized redirect URI in Google Cloud. Set `AUTH_ADMIN_EMAILS` if the observability dashboard is needed.
4. Apply the new backend migration before directing the new frontend to the backend. Deploy both services from the same commit, then verify `/health`, the public search landing page, Google sign-in and return to the saved query, email registration/verification and password reset if SMTP is enabled, and an authenticated search.

Use two different production secrets; do not reuse local development values. Generate each with `openssl rand -hex 32`. The browser calls same-origin Next.js route handlers. Preview deployments need a stable preview domain, a matching OAuth callback URL and `NEXTAUTH_URL`, and separate environment settings.

| Vercel variable | Value |
| --- | --- |
| `BACKEND_API_URL` | Public Render backend origin, without a trailing slash |
| `NEXTAUTH_URL` | Exact public Vercel origin using HTTPS |
| `NEXTAUTH_SECRET` | New production random value, at least 32 characters |
| `AUTH_JWT_SECRET` | Exact same value as Render's `AUTH_JWT_SECRET` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth Web application credentials for the registered production callback |
| `AUTH_ADMIN_EMAILS` | Optional; set on both services only if the developer dashboard is needed |

## Troubleshooting production requests

If the page shows `Backend: error. Database: unknown. Failed to fetch`, check the Next.js server route and backend URL:

- In **Vercel**, set `BACKEND_API_URL` to the reachable Render API base URL, with no trailing slash.
- In **Render** and **Vercel**, set the same `AUTH_JWT_SECRET`; search requests with mismatched values return HTTP 401.
- If Google sign-in fails, check that `NEXTAUTH_URL` and the Google authorized redirect URI use the same HTTPS origin and end in `/api/auth/callback/google`.
- If Vercel logs show `[next-auth][error][OAUTH_CALLBACK_HANDLER_ERROR] fetch failed`, check that `BACKEND_API_URL` is set in Vercel's **Production** environment to the public Render HTTPS origin. Open `<BACKEND_API_URL>/health` from outside Render and confirm it responds. Google sign-in calls `/auth/google` on that backend before a session is created; the new log message distinguishes an unreachable backend from an HTTP rejection.
- If email registration returns HTTP 503, configure Render's `AUTH_EMAIL_FROM` and `AUTH_SMTP_*` settings.
- If Shopify returns HTTP 403, check Render logs for `shopify_catalog_forbidden`. The entry includes Shopify's request ID and up to 1,000 characters of its response body; it does not log the outgoing Authorization header. A successful anonymous request from another network does not establish that Render's outbound IP has the same access. If Shopify rejects anonymous traffic from Render, configure both Shopify Catalogs API credentials for authenticated access or ask Shopify to investigate using the request ID. The browser only sees the backend's HTTP 503 response.
- If Gemini generation returns HTTP 400, inspect `mode`, `api_code`, `api_status`, and the bounded `api_message` in Render logs. Gemini 3.x requests omit deprecated sampling parameters and structured requests send only supported JSON Schema keywords; a remaining 400 needs its API message to diagnose.

Open `https://<your-render-service>.onrender.com/health` directly. It should return JSON with `backend` and `database` fields. If it returns `database: "error"`, check Render's `DATABASE_URL`, Neon connectivity, and whether migrations ran. If the direct health URL works but the frontend still fails, check Vercel's server logs and `BACKEND_API_URL`.

## Changing models

The backend reads its settings when the process starts. To change the generation model, update `GENERATION_MODEL` (Gemini) or `OLLAMA_GENERATION_MODEL` (Ollama) in Render and restart or redeploy the service. `GENERATION_PROVIDER` selects the provider. For Gemini, `GENERATION_MODEL` is used by both generation and structured constraint parsing; when unset, the app uses `SEARCH_PARSER_MODEL`.

Embedding settings are also selected through Render variables. A newly seeded catalog has no vectors and uses keyword retrieval. To enable semantic retrieval, run `embed-catalog` once from the backend service shell after setting the intended embedding provider, model, and dimensions. Changing those settings later requires re-embedding the catalog so query and catalog vectors remain compatible.

## GitHub Actions and local CI values

The GitHub Actions workflow uses a temporary CI database. Keep production OAuth, email, and signing secrets in Render and Vercel; do not add them to Actions.
