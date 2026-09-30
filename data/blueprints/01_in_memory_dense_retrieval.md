# Module: Naive Dense Vector Retrieval Baseline

## Metadata
- Module ID: blueprint_01_dense_baseline
- Difficulty Level: 1
- Prerequisites: Python 3.11, Docker, FastEmbed, Qdrant Client

## Architecture Pattern
Deploy Qdrant in Docker as the centralized vector database. Input documents are chunked into self-contained text segments. Each segment is passed to the BAAI/bge-small-en-v1.5 embedding model via FastEmbed running on the ONNX runtime to generate a 384-dimensional Float32 vector. Vectors are upserted into an HNSW-indexed collection using Cosine distance. Ingress user queries are embedded with the same model, and the top K nearest neighbors are retrieved using approximate nearest neighbor (ANN) search over an in-memory graph.

## Explicit Tradeoffs
- Latency Impact: Introduces +10ms to +15ms embedding generation latency per query on CPU; vector search executes in <5ms over collections under 100,000 points.
- Memory Footprint: Each vector requires exactly 1.54 KB of raw memory storage (384 dimensions * 4 bytes). The HNSW connectivity graph introduces an additional 1.5x to 2.0x memory overhead, requiring ~3.5 KB total RAM per indexed document.
- Operational Complexity: Fails on exact keyword, SKU, model number, or acronym searches due to semantic vector compression; susceptible to vocabulary mismatch when specialized terms are not in the embedding training corpus.

## Verification Metric
Achieves Mean Reciprocal Rank (MRR) > 0.60 across a 30-query semantic test set; P95 query latency remains strictly below 35ms on CPU.