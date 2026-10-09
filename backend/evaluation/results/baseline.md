# Fashion Search Evaluation

Dataset: fashion-search-v1
Catalog: synthetic-seed-20261007-count-750-v1 (750 products)
Mode: offline_keyword (no live providers)
Queries: 40

## Filter extraction
Exact match: 97.5%
category: 100.0%
color: 100.0%
occasion: 100.0%
size: 97.5%
gender: 100.0%
price_min: 100.0%
price_max: 100.0%
currency: 100.0%
price_min_inclusive: 100.0%
price_max_inclusive: 100.0%

## Retrieval (human-labeled cases only)
Precision@5: 80.0%
Recall@10: 80.1%
MRR: 94.4%
NDCG@10: 94.1%

## Hard constraints
Violations: 0 / 221 returned products
Violation rate: 0.0%

## Empty results
Accuracy: 70.0%

## Conversation
State transition accuracy: 100.0%

## Latency (offline keyword mode)
Mean: 1193.70 ms
P50: 1181.38 ms
P95: 1319.83 ms
