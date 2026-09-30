# Module: Asynchronous FastAPI Telemetry and Request Tracing

## Metadata
- Module ID: blueprint_08_fastapi_telemetry
- Difficulty Level: 2
- Prerequisites: Python Asyncio, FastAPI, Starlette, Structlog

## Architecture Pattern
Implement non-blocking ASGI middleware in FastAPI to intercept the entire HTTP request-response lifecycle. At ingress, extract or generate an immutable X-Request-ID header using UUIDv4. Store this correlation ID within a contextvars context to propagate it across asynchronous execution branches. Collect request metadata (method, route path, client IP) and calculate elapsed execution duration upon response emission. Format operational telemetry as single-line, structured JSON payloads emitted to stdout, ensuring thread-safe, non-blocking execution across the event loop.

## Explicit Tradeoffs
- Latency Impact: Introduces <1.5ms overhead per HTTP transaction to handle header manipulation, monotonic clock timing, and JSON serialization.
- Memory Footprint: Constant memory allocation (~2 KB per concurrent request) to maintain contextual request state within the active asyncio task loop.
- Operational Complexity: Improper error handling in ASGI middleware can swallow exceptions or drop outgoing response headers; requires rigorous try-finally execution wrappers.

## Verification Metric
100% of emitted log events contain the matching X-Request-ID; middleware overhead remains strictly below 2.0ms at P99 under a 100 concurrent request load.
