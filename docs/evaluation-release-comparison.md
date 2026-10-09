# Release-readiness evaluation (2026-10-09)

Both runs used `fashion-search-v1`, checksum `eb804e475515946fa7919f8fe3a509cfab49759f16725c03b1058c07054ab8af`, 750 products, deterministic `offline_keyword` mode, and commit base `1dc13da9ea76f30a7f66964ab3dd15bf70fa86dc` with an uncommitted worktree. Configured providers were Gemini `gemini-2.5-flash-lite` for generation and `gemini-embedding-001` (768 dimensions) for embeddings; **neither provider was called**. RRF k=60, weights semantic 0.6 / keyword 0.4 were recorded but not exercised in this mode. The reported provider-connected database contained 750 completed embeddings; the clean local database had none, which does not affect offline keyword scores.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Filter exact match | 97.50% | 100.00% | +2.50 pp |
| Category / color / occasion / gender / price field accuracy | 100% each | 100% each | 0 |
| Size field accuracy | 97.50% | 100.00% | +2.50 pp |
| Unexpected constraints | 0 | 0 | 0 |
| Precision@5 | 80.00% | 84.44% | +4.44 pp |
| Recall@10 | 80.07% | 81.60% | +1.54 pp |
| MRR | 94.44% | 95.83% | +1.39 pp |
| NDCG@10 | 94.09% | 94.76% | +0.67 pp |
| Hard-filter violations | 0/221 | 0/258 | 0 |
| Empty-result accuracy | 70% | 75% | +5 pp |
| Conversation transition accuracy | 100% (8/8) | 100% (8/8) | 0 |
| Explanation present / unsupported claims | 100% / 0 | 100% / 0 | 0 |
| P50 latency, hosted DB | 1218.06 ms | 1174.47 ms | -43.59 ms |
| P95 latency, hosted DB | 1371.29 ms | 1279.47 ms | -91.82 ms |

Latency values are single 40-query runs against a hosted database, not a statistically reliable performance claim. A separate pristine local PostgreSQL run after the fixes had P50 **2.12 ms** and P95 **3.24 ms**; do not compare those local values with hosted-DB latency.

## Failure classification

| Cases / symptom | Classification | Evidence and disposition |
| --- | --- | --- |
| q035, `men wedding footwear size 9` extracted no size and returned empty | GENUINE_DEFECT | Size regex omitted catalog-supported footwear size 9. It now uses the existing size taxonomy. |
| q016 `black tee`, q017 `running trainers` retained alias words in FTS text | GENUINE_DEFECT | Category aliases were extracted but retrieval text was not normalized. Recognized aliases now become canonical category terms; q016 recovered, while q017's “running” still lacks an exact keyword match. |
| q010–q012, q014, q017, q019, q021, q024–q026 false-empty after fixes | KNOWN_LIMITATION / AMBIGUOUS_QUERY | These are largely descriptive or weak natural-language requests evaluated in keyword-only mode; no hard-filter breach was observed. The weak cases' nonempty expectation is an evaluation-design question, not proof of a production ranking defect. Preserve labels pending a separate semantic/hybrid evaluation. |
| q009 `black dress for wedding under ₹4000` is empty | CATALOG_DATA_LIMITATION / EXPECTED_BEHAVIOR | The pinned seed has no wedding dress. Do not relax exact filters or fabricate results. |
| No confirmed incorrect product relevance labels | LABEL_ERROR: none confirmed | Dataset version remains `fashion-search-v1`; do not alter labels to inflate scores. |
| Gemini/Ollama run-to-run differences | PROVIDER_VARIANCE: not assessed | Offline mode deliberately makes no live calls. |

The clean-install check found a separate **GENUINE_DEFECT** not visible in the evaluation run: the migration's FTS row trigger used unqualified columns, so fresh catalog inserts failed. Migration `20261009_0007` repairs already-migrated databases; migration `0004` now builds the correct trigger on new installs. A second pristine local database migrated, seeded, and passed evaluation.

Release risk: the exact requested smoke journey requiring products for a black wedding dress cannot pass with this catalog. Use a catalog-supported query to test UI navigation, but do not claim that substitutes for the requested exact journey.
