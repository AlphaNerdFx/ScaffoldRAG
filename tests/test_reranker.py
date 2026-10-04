"""Unit and integration tests for Subsystem 2.3: Cross-Encoder Reranker."""

import time

from app.services.search.hybrid_search import HybridSearchEngine
from app.services.search.reranker import CrossEncoderReranker


def test_reranker_relevance_ordering(
    hybrid_search_engine: HybridSearchEngine,
    reranker: CrossEncoderReranker,
) -> None:
    """Asserts that cross-attention elevates ground truth and evicts false positives."""
    query = "Prevent cascading backend failures when downstream LLM APIs timeout"
    candidates = hybrid_search_engine.search(query, top_k=15)

    top_4 = reranker.rerank(query, candidates=candidates, top_n=4)

    assert len(top_4) == 4

    # Ground truth must be at Rank 1
    assert "Circuit Breaker" in top_4[0].module_name, (
        f"Ground-truth 'Circuit Breaker' was not at rank 1. Found '{top_4[0].module_name}'"
    )

    # False positive 'Instructor' from RRF must not be in the top 2
    top_2_names = [top_4[0].module_name, top_4[1].module_name]
    assert not any("Instructor" in name for name in top_2_names), (
        "False positive 'Instructor' chunk was not demoted by the Cross-Encoder."
    )

    # Logit scores must be strictly descending
    logits = [chunk.rrf_score for chunk in top_4]
    assert logits == sorted(logits, reverse=True), "Reranked logit scores are not descending."


def test_reranker_latency_sla_under_budget(
    hybrid_search_engine: HybridSearchEngine,
    reranker: CrossEncoderReranker,
) -> None:
    """Asserts that a warm cross-encoder execution takes <= 600ms on CPU (PRD Section 1.3)."""
    query = "Celery asynchronous background job execution and Redis caching"
    candidates = hybrid_search_engine.search(query, top_k=15)

    t_start = time.perf_counter()
    top_4 = reranker.rerank(query, candidates=candidates, top_n=4)
    elapsed_ms = (time.perf_counter() - t_start) * 1000.0

    assert len(top_4) == 4
    assert elapsed_ms <= 600.0, f"Reranker latency SLA breached: took {elapsed_ms:.2f}ms > 600ms"


def test_reranker_empty_candidates_handling(reranker: CrossEncoderReranker) -> None:
    """Asserts that passing an empty candidate list returns an empty list without error."""
    results = reranker.rerank("Arbitrary query", candidates=[], top_n=4)
    assert results == []
