# v2.0.0 release preparation checklist

Updated 2026-10-11. This checklist describes the current candidate; it is not a declaration that v2.0.0 has shipped.

| Gate | Status | Evidence / next action |
| --- | --- | --- |
| Backend, API, and frontend version metadata | Prepared | Python package, FastAPI, frontend package, and npm lockfile set to `2.0.0`. |
| Release notes and architecture documentation | Prepared | [v2.0.0 candidate notes](releases/v2.0.0.md), README, and architecture docs updated. |
| RAG context, structured validation, and telemetry | Implemented; rerun suite | Existing provider abstraction, allowlisted context, product-reference validation, and request-correlated observability extended. The 160-test/1-skip run predates final query-normalization fixes. |
| Exact filters and conversational category switching | Manual backend check passed | Catalog checks returned five black dresses, five footwear items after switching to `shoe under 3000`, and five blue-family dresses. Full browser flow remains pending. |
| Retrieval and grounding evaluation on final source | **Pending** | Previous 40-query run predates final query/color fixes. Re-run all modes and update candidate metrics before publication. |
| Compatible semantic index | **Unavailable in evaluation catalog** | Semantic-only measured zero results; hybrid correctly used FTS. Re-index a matching embedding space before claiming semantic retrieval quality. |
| Live RAG quality, latency, and API cost | **Not measured** | Current grounding harness makes no live text-generation calls. |
| Final automated backend/frontend suites | **Pending** | Run the documented commands after final search fixes. Do not rely on the earlier 160 backend tests and frontend checks as final v2 verification. |
| Production container build | Pass | Latest frontend and backend Docker images built; local health endpoints returned HTTP 200. |
| Desktop/mobile browser acceptance and screenshots | **Pending** | Verify chat input clears, same-session category switch, chip updates, product/back, refresh, and mobile drawer. Replace stale screenshots. |
| Remote CI | **Unverified** | Requires a GitHub Actions run after the user commits/pushes. |
| Dependency audit | **Needs review** | Prior audit reported five high-severity findings in development-only ESLint dependencies; recheck and document disposition. |
| Session scaling | **Known limitation** | Backend sessions are process-local. Keep one backend worker or implement shared session storage before horizontal scaling. |
| Commit, tag, or publication | **Not done by request** | User will commit manually. No release tag or remote publication has been created. |

Before publishing, complete the pending verification and update [v2.0.0 candidate notes](releases/v2.0.0.md). The [v0.1.0 candidate notes](releases/v0.1.0.md) are retained as historical release preparation.
