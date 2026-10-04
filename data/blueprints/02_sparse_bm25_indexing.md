
# Module: Sparse BM25 Inverted Index Retrieval

## Metadata

- Module ID: blueprint_02_sparse_bm25
- Difficulty Level: 2
- Prerequisites: blueprint_01_dense_baseline, FastEmbed SparseTextEmbedding

## Architecture Pattern

Augment the vector storage layer with an inverted index that tracks term frequencies and inverse document frequencies (TF-IDF / BM25). Text documents are tokenized, stemmed, and stripped of common stop words. Document term weights are computed and stored as sparse vectors containing discrete token indices and numerical importance scores. At query time, the user query is tokenized, matched against the sparse index, and scored according to document term saturation and length penalization algorithms without neural network matrix multiplications.

## Explicit Tradeoffs

- Latency Impact: Tokenization and sparse inverted index traversal add +15ms to +25ms per query depending on vocabulary size and dictionary sparsity.
- Memory Footprint: Requires hosting an inverted token index alongside dense vectors. Sparse token postings expand disk and RAM requirements by ~25% to ~40% over dense-only storage.
- Operational Complexity: Completely blind to semantic context and synonyms (e.g., searching for 'low latency' will not match a document containing 'high performance' unless exact tokens overlap). Requires maintaining language-specific tokenizers and stemmers.

## Verification Metric

Improves exact-match token recall by >= 35% on specialized technical keywords and library names compared to dense-only retrieval.
