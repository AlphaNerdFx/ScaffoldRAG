# Module: Semantic and Exact-Match Redis Caching

## Metadata
- Module ID: blueprint_09_redis_caching
- Difficulty Level: 3
- Prerequisites: Docker, Redis, blueprint_01_dense_baseline

## Architecture Pattern
Deploy Redis as an in-memory key-value cache layer positioned ahead of the hybrid retrieval and generation pipelines. Ingress student queries and skill profiles are normalized, sorted, and hashed using SHA-256 to create an idempotent cache key. Upon request arrival, execute an O(1) Redis GET lookup. On a cache hit, bypass Qdrant retrieval and Groq LLM generation, returning the cached JSON payload with an active 24-hour TTL. On a cache miss, execute the complete RAG execution graph, write the resulting payload to Redis asynchronously, and return the response.

## Explicit Tradeoffs
- Latency Impact: Lowers cache-hit response latency from ~1,200ms down to <8ms over local network loopback connections.
- Memory Footprint: Requires allocated Redis memory. Storing 10,000 serialized blueprint roadmap responses consumes approximately 35 MB to 50 MB of RAM depending on string compression.
- Operational Complexity: Introduces cache invalidation synchronization challenges when underlying markdown blueprints are modified; requires configuring an eviction policy (volatile-lru) to avoid memory exhaustion.

## Verification Metric
Achieves >= 40% cache hit ratio across repeated evaluation test suites; P99 response time for cached queries remains strictly below 10ms.
