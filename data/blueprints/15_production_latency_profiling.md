# Module: Production Latency Profiling and Flamegraph Analysis

## Metadata
- Module ID: blueprint_15_production_latency_profiling
- Difficulty Level: 3
- Prerequisites: blueprint_08_fastapi_telemetry, blueprint_14_prometheus_metrics, Py-Spy

## Architecture Pattern
Incorporate non-intrusive statistical profiling capabilities using Py-Spy to inspect runtime execution profiles under load without modifying application source code. Configure Py-Spy to sample call stacks at a 100 Hz frequency during performance test runs. Aggregate stack traces to output speedscope profiles and SVG flamegraphs. Correlate profiled CPU bottlenecks with Prometheus P95/P99 latency spikes, isolating CPU-bound bottlenecks (ONNX runtime vector math, tokenization, serialization) from asynchronous I/O wait states (database reads, network calls).

## Explicit Tradeoffs
- Latency Impact: Introduces a 1% to 3% CPU overhead penalty when the profiler is actively attached and sampling; 0% overhead when inactive.
- Memory Footprint: Allocates negligible memory (<15 MB) to record sample buffers and write output trace artifacts to disk.
- Operational Complexity: Requires elevated Linux kernel permissions (SYS_PTRACE capability) inside Docker containers to attach to running process IDs; requires expertise to interpret asynchronous call graphs.

## Verification Metric
Flamegraphs pinpoint the top 3 CPU hotspots under a 50 RPS load test; active profiling reduces total system throughput by less than 3%.
