# ADR-006: Human-labelled evaluation

Status: Accepted

Context: Ranking or prompt changes need a repeatable baseline rather than ad hoc manual examples.

Decision: Version query/filter/product-ID labels, pin the catalog checksum, and run deterministic offline metrics before comparing changes.

Alternatives considered: LLM-as-judge as the primary ground truth; unversioned click-through anecdotes.

Consequences: Reproducible local comparisons and visible label errors; the 40-query dataset and offline keyword mode are not a full measure of live provider or semantic quality.
