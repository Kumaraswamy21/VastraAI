# Fashion search evaluation

This harness establishes a versioned, human-labeled measurement baseline. It does not tune production search and does not use an LLM as a relevance judge. The checked-in `datasets/fashion_search_v1.json` contains 40 natural-language cases, explicit expected constraints, selected graded relevance judgments, empty-result expectations, and three conversational sequences.

## Repeatability and modes

The default runner is `offline_keyword`: deterministic fallback parsing, existing query preprocessing, and PostgreSQL full-text retrieval. It deliberately makes no Gemini/Ollama generation or embedding calls, so its latency/results must not be compared to live hybrid mode. Dataset and catalog checksums, configured provider/model settings, ranking parameters, timestamp, and git SHA are recorded. The pinned catalog is the 750-row synthetic seed `20261007`; evaluation stops if its canonical catalog checksum or the dataset's referenced product IDs do not match. Refreshing labels/snapshot is an intentional versioned change, not something the runner does automatically.

## Dataset and labeling

Product IDs are catalog primary keys, not titles. Relevance grades: 0 not relevant, 1 partial, 2 relevant, 3 highly relevant. A product violating any expected hard filter must have grade 0. Set `judgments_complete` only when relevant items are exhaustively judged; incomplete/unjudged products are not treated as irrelevant for ranked metric aggregation. `expected_empty` is grounded in exact catalog metadata, not search behavior. Leave a filter null when the wording does not explicitly establish it. Weak/ambiguous cases measure whether the system returns something but do not receive subjective relevance scores. Increment `dataset_version` after a material label/query change.

## Metrics

Filter evaluation reports exact query match, per-field accuracy (including nulls and price inclusivity), false-positive active constraints, and constraint precision/recall/F1. Retrieval uses grades >0 as relevant for Precision@5, Recall@10, and MRR; NDCG uses gain `2^grade - 1` discounted by `log2(rank+1)`. Precision divides by K even when fewer than K products are returned. Retrieval aggregates only use complete relevance judgments; recall also requires at least one positive label. Hard-constraint violation rate counts returned products failing an active category/color/occasion/size/gender/price constraint. Empty outcomes are classified separately. State transition accuracy requires the full expected constraint state to match after each turn. Explanation checks are deterministic and structured-evidence based. Latencies use monotonic elapsed time; P50/P95 use linear interpolation over sorted samples. Stage durations are measured locally and need not sum exactly to total.

## Run and compare

From `backend/` with dependencies installed and the matching PostgreSQL catalog available:

```sh
python -m fashion_search.evaluation.runner
python -m fashion_search.evaluation.runner --query-id q001
python -m fashion_search.evaluation.runner --provider-mode offline_keyword
python -m fashion_search.evaluation.runner --dataset evaluation/datasets/fashion_search_v1.json --limit 5 --output evaluation/results/baseline.json
python -m fashion_search.evaluation.compare evaluation/results/baseline.json evaluation/results/current.json
```

The runner writes JSON details and a sibling Markdown summary. Keep a baseline only when it is an actual run; do not commit example/placeholder scores. Comparison rejects different dataset, catalog snapshot, checksum, or provider mode by default. `--allow-version-mismatch` is an explicit escape hatch; version-mixed deltas should not be interpreted as regressions/improvements. Direction is shown per metric because latency and violation rate are lower-is-better. Threshold configuration is intentionally not a CI failure gate in this initial milestone.

## Adding cases

Add query cases with stable IDs, query classes, manually labeled expected filters, product-ID relevance grades, judgment completeness, and catalog-grounded empty expectation. Add conversational turns with the full expected state after each message. Before changing production search, inspect per-query mismatches and verify the human labels against the pinned catalog. When catalog data changes, create and record a new catalog snapshot/checksum; do not silently update the v1 catalog identifier.

## Limitations

The initial runnable baseline is PostgreSQL FTS only. It does not measure semantic retrieval, RRF ordering, live provider latency, or model usage; those should be separate runs/modes built on the same dataset and never mixed in comparison. Several cases intentionally have incomplete relevance judgments, so only a smaller exhaustive subset contributes to ranked scores. The conversation evaluator is deterministic-only and unsupported provider-dependent turns are marked incorrect rather than called live. Dashboard/observability history is not used as a substitute for controlled evaluation runs.
