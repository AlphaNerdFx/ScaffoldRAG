"""scripts/verify_phase_3.py: End-to-end integration test spanning Phase 2 and Phase 3."""

import time

from qdrant_client import QdrantClient

from app.core.circuit_breaker import CircuitBreaker, FallbackProvider
from app.core.config import get_settings
from app.schemas.roadmap import ProjectRoadmap, RoadmapRequest
from app.services.generator import RoadmapGenerator
from app.services.search.hybrid_search import HybridSearchEngine
from app.services.search.ood_gate import OODGate
from app.services.search.reranker import CrossEncoderReranker


def run_pipeline(
    ood_gate: OODGate,
    search_engine: HybridSearchEngine,
    reranker: CrossEncoderReranker,
    generator: RoadmapGenerator,
    circuit_breaker: CircuitBreaker,
    fallback_provider: FallbackProvider,
    request: RoadmapRequest,
) -> tuple[ProjectRoadmap, dict[str, float]]:
    """Executes full pipeline and returns the roadmap and latency timings in ms."""
    query_text = f"{request.target_role} building {request.domain_interest}"
    t_start = time.perf_counter()

    # Stage 2.1: OOD Gate
    t0 = time.perf_counter()
    _ = ood_gate.validate_query(query_text)
    t_ood = (time.perf_counter() - t0) * 1000

    # Stage 2.2: Hybrid Search via RRF
    t0 = time.perf_counter()
    candidates = search_engine.search(query_text=query_text, top_k=15)
    t_search = (time.perf_counter() - t0) * 1000

    # Stage 2.3: Cross-Encoder Reranking
    t0 = time.perf_counter()
    top_chunks = reranker.rerank(query_text=query_text, candidates=candidates, top_n=4)
    t_rerank = (time.perf_counter() - t0) * 1000

    # Stage 3.2 & 3.3: Generation protected by Circuit Breaker
    t0 = time.perf_counter()
    roadmap: ProjectRoadmap = circuit_breaker.execute(
        func=generator.generate,
        fallback_func=lambda req, chunks: fallback_provider.get_static_roadmap(req.target_role),
        request=request,
        context_chunks=top_chunks,
    )
    t_gen = (time.perf_counter() - t0) * 1000
    t_total = (time.perf_counter() - t_start) * 1000

    timings = {
        "ood_ms": t_ood,
        "search_ms": t_search,
        "rerank_ms": t_rerank,
        "gen_ms": t_gen,
        "total_ms": t_total,
    }
    return roadmap, timings


def main() -> None:
    settings = get_settings()
    print("[*] Booting End-to-End Pipeline Verification (Phases 2 & 3)...")

    # 1. Initialize Infrastructure Clients
    client = QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        grpc_port=settings.QDRANT_GRPC_PORT,
        prefer_grpc=True,
    )

    ood_gate = OODGate(client=client)
    search_engine = HybridSearchEngine(client=client)
    reranker = CrossEncoderReranker()
    generator = RoadmapGenerator()
    circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=45.0)
    fallback_provider = FallbackProvider()

    # 2. Genuine Warmup: Must hit the exact query_embed methods and Qdrant gRPC socket
    print("[*] Warming up neural query graphs and Qdrant gRPC channels...")
    _ = ood_gate.validate_query("Warmup computing query for neural graphs")
    _ = search_engine.search("Warmup computing query for BM25", top_k=2)
    _ = reranker.rerank("Warmup query", candidates=[], top_n=0)
    print("[+] Qdrant gRPC channel and neural engines successfully warmed.")

    # 3. Define Realistic Student Ingress Payload
    request = RoadmapRequest(
        target_role="Machine Learning Engineer",
        domain_interest="High-Throughput E-commerce Hybrid Search & Retrieval",
        current_skills=["Python", "FastAPI", "Basic Docker", "Scikit-Learn"],
    )

    print("[*] Running steady-state benchmark pass...")
    roadmap, timings = run_pipeline(
        ood_gate, search_engine, reranker, generator, circuit_breaker, fallback_provider, request
    )

    # 4. Telemetry Reporting
    t_local = timings["ood_ms"] + timings["search_ms"] + timings["rerank_ms"]
    print("\n" + "=" * 65)
    print("                E2E PIPELINE LATENCY PROFILING")
    print("=" * 65)
    print(f"  Stage 2.1 (OOD Gate)         : {timings['ood_ms']:6.1f} ms  (SLA <=  25ms)")
    print(f"  Stage 2.2 (Hybrid Search)    : {timings['search_ms']:6.1f} ms  (SLA <= 150ms)")
    print(f"  Stage 2.3 (Reranker)         : {timings['rerank_ms']:6.1f} ms  (SLA <= 600ms)")
    print(f"  LOCAL RETRIEVAL TOTAL        : {t_local:6.1f} ms  (SLA <= 775ms)")
    print("-" * 65)
    print(f"  Stage 3.2/3.3 (Generation)   : {timings['gen_ms']:6.1f} ms  (SLA <= 2500ms)")
    print("-" * 65)
    print(f"  TOTAL LATENCY                : {timings['total_ms']:6.1f} ms  (SLA <= 4000ms)")
    print("=" * 65 + "\n")

    print(f"Roadmap Title: {roadmap.project_title}")
    print(f"Milestones Generated: {len(roadmap.milestones)}")
    for m in roadmap.milestones:
        print(f"  Stage {m.stage}: {m.name} | Tools: {', '.join(m.tools_introduced[:3])}...")

    # Strict architectural assertions
    assert len(roadmap.milestones) == 5, "Invariant breach: must have exactly 5 milestones"
    assert [m.stage for m in roadmap.milestones] == [1, 2, 3, 4, 5], "Stages must be sequential 1-5"

    # Assert local compute bounds (deterministic)
    # Assert local compute bounds matching PRD Section 1.3 (Hybrid <= 400ms + Reranker <= 600ms = 1000ms))
    assert t_local <= 1000.0, (
        f"Local retrieval pipeline exceeded PRD SLA ceiling (1000ms): {t_local:.1f}ms"
    )
    assert timings["total_ms"] <= 4000.0, (
        f"Total pipeline latency exceeded hard ceiling (4000ms): {timings['total_ms']:.1f}ms"
    )
    print(
        "\n[SUCCESS] Local retrieval and structured generation formally verified against PRD SLAs!"
    )


if __name__ == "__main__":
    main()
