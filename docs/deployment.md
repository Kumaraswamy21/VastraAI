# Deployment

The repository contains a Next.js frontend and a FastAPI backend. A straightforward hosted setup is Vercel for the frontend, Render for the backend, and your existing Neon Postgres database with the `vector` extension. Vercel and Render can deploy from the GitHub repository when their configured branch changes. GitHub Actions remains the CI workflow; production secrets do not need to be copied into Actions.

## 1. Connect the backend to Neon

1. In Neon, copy the connection string for the database branch this app should use. Prefer a dedicated Neon database or branch so this app's tables and synthetic catalog stay isolated from other applications.
2. Create a Web Service from this repository in Render. Select the Docker runtime, leave **Root Directory** blank (repository root), set **Dockerfile Path** to `backend/Dockerfile`, and set **Docker Context** to `backend`. These paths are relative to the service root; do not set Root Directory to `backend` at the same time. Alternatively, if Root Directory is `backend`, use Dockerfile Path `Dockerfile` and Docker Context `.`.
3. Add the environment variables below in the service's Environment settings. Set secret values there; do not commit them to `.env.example` or GitHub Actions.
4. Configure the service's pre-deploy command as `alembic upgrade head` so migrations run before each deploy. Render's pre-deploy command availability depends on the service plan. If it is unavailable, run migrations from the service shell for the initial deploy and after later schema changes.
5. Deploy the service and copy its public URL (for example, `https://vastraai-api.onrender.com`).

Use the `DATABASE_URL` from Neon's Connect dialog. A direct connection is suitable for this persistent FastAPI service; use Neon's pooled connection string if you need to limit database connections. The app adds `sslmode=require` if the URL does not include an SSL mode. The first Alembic migration enables pgvector with `CREATE EXTENSION IF NOT EXISTS vector`.

Keep one backend instance for now: conversational search sessions are held in process memory and are not shared across instances.

| Render variable | Value |
| --- | --- |
| `DATABASE_URL` | Neon connection string for the intended database/branch |
| `CORS_ORIGINS` | The exact Vercel production origin, such as `https://vastraai.vercel.app` |
| `APP_ENVIRONMENT` | `production` |
| `OBSERVABILITY_DASHBOARD_ENABLED` | `false` |
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

Only set the provider-specific values you use. If Neon has IP restrictions enabled, allow connections from the Render service's outbound IP addresses.

After the first deploy and successful migration, open the service shell and run `seed-catalog` once. This loads the repo's 750 synthetic products into Neon. The seed is idempotent for an already seeded catalog.

## 2. Create the frontend on Vercel

1. Import the same GitHub repository as a Vercel project.
2. Set the project Root Directory to `frontend` and leave Next.js as the detected framework.
3. Add `NEXT_PUBLIC_API_URL` with the Render backend URL, such as `https://vastraai-api.onrender.com`, for the Production environment. This value is compiled into the frontend, so changing it requires a new frontend deployment.
4. Deploy, then verify the catalog and API health status from the production site.

If preview deployments need to call the API, add each preview origin to `CORS_ORIGINS` or use a stable preview domain. The backend currently accepts an explicit comma-separated origin list.

## Troubleshooting the frontend health status

If the page shows `Backend: error. Database: unknown. Failed to fetch`, the browser did not receive a readable response from the API. Check both settings:

- In **Render**, set `CORS_ORIGINS` to the exact site origin, for example `https://vastraai.vercel.app` (scheme and hostname, with no path or trailing slash). This variable belongs on the backend service, not in Vercel.
- In **Vercel**, set `NEXT_PUBLIC_API_URL` to the Render API base URL, for example `https://vastraai-api.onrender.com` (no trailing slash). Since this is compiled into the frontend, redeploy Vercel after changing it. A trailing slash makes the current frontend request `//health`.

Open `https://<your-render-service>.onrender.com/health` directly. It should return JSON with `backend` and `database` fields. If it returns `database: "error"`, check Render's `DATABASE_URL`, Neon connectivity, and whether migrations ran. If the direct health URL works but the frontend still says `Failed to fetch`, check the browser console for a CORS error and verify the Vercel origin matches `CORS_ORIGINS` exactly; then redeploy/restart Render after changing that setting.

## Changing models

The backend reads its settings when the process starts. To change the generation model, update `GENERATION_MODEL` (Gemini) or `OLLAMA_GENERATION_MODEL` (Ollama) in Render and restart or redeploy the service. `GENERATION_PROVIDER` selects the provider. For Gemini, `GENERATION_MODEL` is used by both generation and structured constraint parsing; when unset, the app uses `SEARCH_PARSER_MODEL`.

Embedding settings are also selected through Render variables. A newly seeded catalog has no vectors and uses keyword retrieval. To enable semantic retrieval, run `embed-catalog` once from the backend service shell after setting the intended embedding provider, model, and dimensions. Changing those settings later requires re-embedding the catalog so query and catalog vectors remain compatible.

## GitHub Actions and local CI values

The current `.github/workflows/ci.yml` tests the backend against its temporary CI database and builds the frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000`. Those values are for CI only. With platform GitHub integration handling deploys, do not add production API keys or database credentials to the Actions workflow. Set them in Render and Vercel as described above.
