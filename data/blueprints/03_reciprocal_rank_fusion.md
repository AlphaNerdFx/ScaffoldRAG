
# Module: Reciprocal Rank Fusion Hybrid Search

## Metadata

- Module ID: blueprint_03_reciprocal_rank_fusion
- Difficulty Level: 2
- Prerequisites: blueprint_01_dense_baseline, blueprint_02_sparse_bm25

## Architecture Pattern

Execute parallel retrieval over dense vector and sparse keyword indices in Qdrant for every ingress query. The system extracts two disjoint ranked lists of candidate document IDs (top 20 dense candidates and top 20 sparse candidates). Combine the lists using the Reciprocal Rank Fusion (RRF) algorithm: Score(d) = Sum(1 / (k + rank_i(d))) across all systems i, where k is a smoothing constant fixed at 60. RRF eliminates the need to normalize and calibrate incompatible raw scores (BM25 unbound positive scores vs. Cosine -1.0 to +1.0 scores), sorting documents purely by their ordinal ranking consistency.

## Explicit Tradeoffs

- Latency Impact: Requires running two parallel search queries and an in-memory aggregation loop; adds +15ms to +30ms total retrieval latency over single-index search.
- Memory Footprint: Minimal in-memory footprint (<100 KB) for candidate score dictionaries; requires dual index maintenance (dense HNSW and sparse inverted index) in the underlying database.
- Operational Complexity: RRF is a rank-based heuristic that discards the magnitude of relevance (a document barely winning Rank 1 is treated identically to a document dominating Rank 1). Requires tuning the rank depth parameter N.

## Verification Metric

Retrieves relevant documents across both conceptual and exact-token test queries, achieving Mean Average Precision (MAP@10) >= 0.75 across mixed benchmark suites.
