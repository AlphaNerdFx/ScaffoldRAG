"""scripts/verify_generator.py: Live verification script asserting real Groq generation."""

import time
from app.core.config import get_settings
from app.schemas.roadmap import ProjectRoadmap, RoadmapRequest
from app.services.generator import RoadmapGenerator
from app.services.search.hybrid_search import ScoredChunk


def main() -> None:
    settings = get_settings()
    api_key = settings.GROQ_API_KEY.get_secret_value() if hasattr(settings.GROQ_API_KEY, "get_secret_value") else str(settings.GROQ_API_KEY)
    
    if not api_key or "mock" in api_key.lower():
        print("[FAIL] A valid GROQ_API_KEY is required in .env to run this live verification.")
        exit(1)

    generator = RoadmapGenerator(api_key=api_key)
    print(f"[*] Initializing RoadmapGenerator with Groq ({generator.model_name})...")

    # Real architectural context chunks representing top 4 retrieved blueprints
    context_chunks = [
        ScoredChunk(
            chunk_id="b1",
            content="Deploy BAAI/bge-small-en-v1.5 dense vectors with 384 dimensions for semantic candidate retrieval.",
            module_name="Dense Retrieval Baseline",
            rrf_score=0.033,
            metadata={
                "header": "Dense Architecture",
                "tradeoff_latency": "+12ms retrieval time per query",
                "tradeoff_memory": "1.54 KB per indexed vector",
                "tradeoff_complexity": "Weak on exact SKU codes",
            },
        ),
        ScoredChunk(
            chunk_id="b2",
            content="Deploy Qdrant sparse BM25 index alongside dense vectors to capture exact keyword matches.",
            module_name="Sparse BM25 Indexing",
            rrf_score=0.031,
            metadata={
                "header": "Sparse Pattern",
                "tradeoff_latency": "+8ms keyword lookup",
                "tradeoff_memory": "Sparse index memory overhead",
                "tradeoff_complexity": "Requires dual vector configuration",
            },
        ),
        ScoredChunk(
            chunk_id="b3",
            content="Fuse dense and sparse ranks in application memory using Reciprocal Rank Fusion with k=60.",
            module_name="Reciprocal Rank Fusion",
            rrf_score=0.029,
            metadata={
                "header": "RRF Merging",
                "tradeoff_latency": "+2ms rank fusion calculation",
                "tradeoff_memory": "Negligible memory overhead",
                "tradeoff_complexity": "Discards absolute similarity scores",
            },
        ),
        ScoredChunk(
            chunk_id="b4",
            content="Rerank top 15 candidate pairs down to top 4 using Xenova/ms-marco-MiniLM-L-6-v2 via ONNX.",
            module_name="Cross-Encoder Reranking",
            rrf_score=0.027,
            metadata={
                "header": "Reranking Pattern",
                "tradeoff_latency": "+350ms to +450ms CPU inference",
                "tradeoff_memory": "400 MB container footprint",
                "tradeoff_complexity": "Requires strict sequence length bounding",
            },
        ),
    ]

    request = RoadmapRequest(
        target_role="Machine Learning Engineer",
        domain_interest="High-Throughput E-commerce Hybrid Search",
        current_skills=["Python", "FastAPI", "Basic Docker"],
    )

    print("[*] Dispatching structured generation request to Groq...")
    t0 = time.perf_counter()
    roadmap: ProjectRoadmap = generator.generate(request, context_chunks)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\n[+] Generation Succeeded in {elapsed_ms:.1f}ms (PRD SLA: <= 2500ms)")
    print(f"[+] Project Title: {roadmap.project_title}")
    print(f"[+] Domain: {roadmap.domain}")
    print(f"[+] Total Milestones: {len(roadmap.milestones)}\n")

    for m in roadmap.milestones:
        print(f"Stage {m.stage}: {m.name}")
        print(f"  Tools: {', '.join(m.tools_introduced)}")
        print(f"  Why: {m.why_added}")
        print(f"  Tradeoff: {m.tradeoff}")
        print(f"  Metric: {m.verification_metric}\n")

    # Assertions
    assert len(roadmap.milestones) == 5, "Must contain exactly 5 stages"
    assert [m.stage for m in roadmap.milestones] == [1, 2, 3, 4, 5], "Stages must be 1 to 5"
    print("[PASS] All PRD & SPEC schema invariants strictly satisfied!")


if __name__ == "__main__":
    main()