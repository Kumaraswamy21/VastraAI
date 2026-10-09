# v0.1.0 release gate status

Checked 2026-10-09. This is a **release candidate**, not an approved release.

| Gate | Status | Evidence / remaining action |
| --- | --- | --- |
| Baseline evaluation before fixes and rerun after | Pass | 40-query `fashion-search-v1` runs; see [comparison](evaluation-release-comparison.md). |
| Classified meaningful evaluation failures | Pass | Genuine parser/alias defects and catalog/keyword limitations separated in comparison. No label correction confirmed. |
| Backend formatting, lint, tests | Pass | Ruff 93 files; 148 unittest cases, one opt-in live Gemini test skipped. |
| Frontend lint, types, tests, production build | Pass | ESLint, TypeScript, two session tests, Next webpack build. |
| Clean PostgreSQL/pgvector migrations and seed | Pass | Untouched local database migrated through `0007`, seeded 750 products, checksum-pinned evaluation passed. |
| Container image builds | Pass | Backend and frontend Docker builds completed locally. |
| CI workflow | Added, **not verified remotely** | Push/PR checks require a GitHub Actions run; do not call CI green yet. |
| Environment and onboarding | Documented, partially verified | `.env.example`, `npm ci`, backend editable install, Compose config, migrations, seed, tests, evaluation and build verified. Full clone on a separate machine not performed. |
| Actual product screenshots | Partial | Four captures in [`images/`](images/); product detail, observability, and mobile still required. |
| Critical exact smoke journey | **Blocked** | The pinned seed has no wedding dress, so “black wedding dress under ₹4000” cannot show products. Zero-result filters and “make it blue” state were observed; a catalog-supported black dress query returned product cards and a card click changed to the product route, but full product-detail/back/refresh verification remains outstanding. |
| Secret scan | Pass for common patterns | `.env` is ignored; tracked file names and workspace source/docs were checked for common API-key/private-key patterns without displaying secret values. This is not a substitute for a dedicated secret scanner in CI. |
| npm production dependency audit | Pass | `npm audit --omit=dev`: zero findings. Full audit has five high-severity findings in the ESLint development dependency chain (`braces` → `micromatch` → `fast-glob` → Next ESLint plugin/config); upstream-compatible remediation still needed. |
| Release commit, tag, remote release | **Not done** | Required gates above are incomplete. Do not create `v0.1.0` yet. |

Before release: resolve the catalog-vs-smoke requirement without silently changing evaluation semantics; capture/verify the three missing screens and complete navigation/refresh smoke; inspect the npm dev advisory; run the new workflow on GitHub; review/stage only intended files (the worktree had pre-existing edits); then create the release commit and `v0.1.0` tag if all checks pass.
