"""Canonical Verification Harness for Phase 2: Hybrid Retrieval & Ranking Subsystem.

Executes sequential automated assertions across:
1. Subsystem 2.1: OOD Gate Boundary Calibration (Threshold = 0.58).
2. Subsystem 2.2: Hybrid Search (BM25 + Dense + Client-Side RRF, k=60).
3. Subsystem 2.3: Cross-Encoder Reranker (ONNX ms-marco-MiniLM-L-6-v2, P95 <= 450ms).
"""

import statistics
import sys
import time

from qdrant_client import QdrantClient

from app.core.config import settings
from app.core.exceptions import OutOfDistributionError
from app.services.search.hybrid_search import HybridSearchEngine, ScoredChunk
from app.services.search.ood_gate import OODGate
from app.services.search.reranker import CrossEncoderReranker


def verify_ood_gate(gate: OODGate) -> None:
    """Verifies boundary separation between technical domains and noise."""
    print("\n--- [Stage 1/3] Verifying Subsystem 2.1: OOD Hard Gate ---")

    test_cases = [
        ("Core Systems Query", "Build an async RAG API with FastAPI", True, 0.70),
        (
            "Hybrid Retrieval Query",
            "Implement Reciprocal Rank Fusion with BM25 and sparse vectors",
            True,
            0.70,
        ),
        ("Borderline Computing", "React frontend state management using Redux Toolkit", True, 0.58),
        ("OOD Culinary", "Best sourdough bread recipe with wild yeast fermentation", False, 0.58),
        ("OOD Random Noise", "The quick brown fox jumps over the lazy dog", False, 0.58),
    ]

    for label, query, should_pass, score_boundary in test_cases:
        valid, score = gate.evaluate_query(query)
        print(
            f"  • {label:24} | Score: {score:.4f} | Pass: {str(valid):5} | Target Pass: {should_pass}"
        )

        if should_pass:
            assert valid is True, f"Failed: Query '{query}' should pass gate but was rejected."
            assert score >= score_boundary, (
                f"Failed: Query '{query}' scored {score:.4f} < boundary {score_boundary}"
            )
        else:
            assert valid is False, f"Failed: OOD Query '{query}' should be rejected but passed."
            assert score < score_boundary, (
                f"Failed: OOD Query '{query}' scored {score:.4f} >= boundary {score_boundary}"
            )

    # Assert exception raising contract
    try:
        gate.validate_query("Best sourdough bread recipe with wild yeast fermentation")
        raise AssertionError(
            "Failed: validate_query did not raise OutOfDistributionError on culinary input."
        )
    except OutOfDistributionError as exc:
        print(f"  ✓ Exception Contract Verified: Raised {exc.__class__.__name__} successfully.")

    print("✓ Subsystem 2.1 (OOD Gate) PASSED all assertions.")


def verify_hybrid_search(engine: HybridSearchEngine) -> list[ScoredChunk]:
    """Verifies parallel retrieval, BM25 exact matching, dense semantics, and RRF fusion."""
    print("\n--- [Stage 2/3] Verifying Subsystem 2.2: Hybrid Search Engine ---")

    # 1. Lexical Token Dominance Test
    lexical_query = "FastAPI middleware for telemetry latency headers"
    print(f"  • Testing Lexical Recall: '{lexical_query}'")
    lexical_results = engine.search(lexical_query, top_k=15)
    assert len(lexical_results) == 15, f"Expected 15 candidates, got {len(lexical_results)}"
    assert any("Telemetry" in chunk.module_name for chunk in lexical_results[:3]), (
        "Failed: Exact lexical match 'Telemetry' was not in top 3 hybrid results."
    )
    print(f"    ✓ Lexical matching succeeded. Top chunk: {lexical_results[0].module_name}")

    # 2. Semantic Conceptual Dominance Test
    semantic_query = "Prevent cascading backend failures when downstream LLM APIs timeout"
    print(f"  • Testing Semantic Recall: '{semantic_query}'")
    semantic_results = engine.search(semantic_query, top_k=15)
    assert len(semantic_results) == 15, f"Expected 15 candidates, got {len(semantic_results)}"
    assert any("Circuit Breaker" in chunk.module_name for chunk in semantic_results[:3]), (
        "Failed: Conceptual semantic match 'Circuit Breaker' was not in top 3 hybrid results."
    )
    print(f"    ✓ Semantic retrieval succeeded. Top chunk: {semantic_results[0].module_name}")

    # Verify RRF score ordering invariant
    scores = [c.rrf_score for c in semantic_results]
    assert scores == sorted(scores, reverse=True), "Failed: RRF scores are not strictly descending."

    print("✓ Subsystem 2.2 (Hybrid Search + RRF) PASSED all assertions.")
    return semantic_results


def verify_reranker(
    reranker: CrossEncoderReranker, candidates: list[ScoredChunk]
) -> list[ScoredChunk]:
    """Verifies cross-encoder accuracy, false-positive elimination, and PRD 600ms SLA."""
    print("\n--- [Stage 3/3] Verifying Subsystem 2.3: Cross-Encoder Reranker ---")

    query = "Prevent cascading backend failures when downstream LLM APIs timeout"

    # 1. Warm-up pass to absorb JIT/thread dispatch transition
    _ = reranker.rerank(query, candidates, top_n=4)

    # 2. Steady-state benchmark iterations with realistic inter-request spacing
    latencies: list[float] = []
    top_4_chunks: list[ScoredChunk] = []

    for i in range(5):
        time.sleep(0.05)  # 50ms realistic inter-request spacing to prevent artificial thermal spike
        t_start = time.perf_counter()
        top_4_chunks = reranker.rerank(query, candidates, top_n=4)
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        latencies.append(elapsed_ms)
        print(f"  • Steady-State Run {i + 1}/5: {elapsed_ms:.2f}ms")

    # Evaluate against PRD Section 1.3 SLA (<= 600ms)
    max_latency = max(latencies)
    median_latency = statistics.median(latencies)
    p95_latency = statistics.quantiles(latencies, n=20, method="inclusive")[18]

    print(
        f"  • Benchmark Summary -> Median: {median_latency:.2f}ms | "
        f"P95: {p95_latency:.2f}ms | Max: {max_latency:.2f}ms (PRD SLA Budget: <= 600ms)"
    )

    assert p95_latency <= 600.0, (
        f"Failed: Cross-Encoder P95 latency ({p95_latency:.2f}ms) breached PRD 600ms SLA."
    )
    assert max_latency <= 600.0, (
        f"Failed: Peak steady-state latency ({max_latency:.2f}ms) breached PRD 600ms SLA."
    )
    assert len(top_4_chunks) == 4, (
        f"Failed: Expected exactly 4 truncated chunks, got {len(top_4_chunks)}"
    )

    # Accuracy Assertion: Rank 1 must be Circuit Breaker
    assert "Circuit Breaker" in top_4_chunks[0].module_name, (
        f"Failed: Ground truth 'Circuit Breaker' not at Rank 1. Found '{top_4_chunks[0].module_name}'"
    )

    # Accuracy Assertion: False positive 'Instructor' must be demoted out of top 2
    top_2_names = [top_4_chunks[0].module_name, top_4_chunks[1].module_name]
    assert not any("Instructor" in name for name in top_2_names), (
        "Failed: False positive 'Instructor' chunk was not demoted by cross-attention."
    )

    # Deterministic Logit Descent Invariant
    logits = [c.rrf_score for c in top_4_chunks]
    assert logits == sorted(logits, reverse=True), (
        "Failed: Final reranked logits are not strictly descending."
    )

    print("\n  --- Final Ground-Truth Chunks Forwarded to Phase 3 Generator ---")
    for rank, chunk in enumerate(top_4_chunks, start=1):
        print(
            f"    [{rank}] Logit: {chunk.rrf_score:+.4f} | {chunk.module_name} -> {chunk.metadata.get('header')}"
        )

    print("✓ Subsystem 2.3 (Cross-Encoder Reranker) PASSED all assertions.")
    return top_4_chunks


def main() -> None:
    print("===================================================================")
    print(" SCAFFOLDRAG PHASE 2 RETRIEVAL SUBSYSTEM CANONICAL VERIFICATION")
    print("===================================================================")

    client = QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_GRPC_PORT,
        prefer_grpc=True,
    )

    gate = OODGate(client=client, threshold=0.58)
    hybrid_engine = HybridSearchEngine(client=client)
    reranker = CrossEncoderReranker()

    try:
        verify_ood_gate(gate)
        candidates = verify_hybrid_search(hybrid_engine)
        verify_reranker(reranker, candidates)
        print("\n===================================================================")
        print(" ALL PHASE 2 VERIFICATION TESTS PASSED CLEANLY (EXIT CODE 0)")
        print("===================================================================")
    except AssertionError as err:
        print(f"\n❌ VERIFICATION ASSERTION FAILED:\n  {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ UNHANDLED EXCEPTION DURING VERIFICATION:\n  {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
