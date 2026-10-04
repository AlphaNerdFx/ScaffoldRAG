"""Benchmark test suite evaluating Context Precision@4 across tests/golden_dataset.json.

Strictly adheres to PRD Appendix A.1 and SPEC Appendix B.2 offline evaluation contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.services.search.hybrid_search import HybridSearchEngine, ScoredChunk
from app.services.search.reranker import CrossEncoderReranker


def calculate_context_precision_at_k(
    retrieved_chunks: list[ScoredChunk],
    expected_chunk_ids: list[str],
    expected_module_name: str,
    k: int = 4,
) -> float:
    """Computes Context Precision@K as formulated in PRD Appendix A.1.

    Precision@k = (relevant chunks in top k) / k
    Context Precision@K = sum(Precision@k * v_k) / (total relevant chunks in top K)
    """
    top_k_chunks = retrieved_chunks[:k]
    if not top_k_chunks:
        return 0.0

    relevance_flags: list[int] = []
    for chunk in top_k_chunks:
        is_relevant = (
            chunk.chunk_id in expected_chunk_ids
            or chunk.module_name.strip().lower() == expected_module_name.strip().lower()
        )
        relevance_flags.append(1 if is_relevant else 0)

    total_relevant = sum(relevance_flags)
    if total_relevant == 0:
        return 0.0

    cumulative_precision_sum = 0.0
    running_relevant_count = 0

    for rank, is_rel in enumerate(relevance_flags, start=1):
        if is_rel == 1:
            running_relevant_count += 1
            precision_at_rank = running_relevant_count / rank
            cumulative_precision_sum += precision_at_rank

    return cumulative_precision_sum / total_relevant


@pytest.fixture(scope="module")
def golden_dataset() -> list[dict[str, Any]]:
    path = Path("tests/golden_dataset.json")
    if not path.is_file():
        pytest.fail(f"Required golden dataset not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) >= 30, f"Golden dataset must contain at least 30 queries. Found: {len(data)}"
    return data


@pytest.fixture(scope="module")
def retrieval_pipeline():
    settings = get_settings()
    client = QdrantClient(
        host=settings.QDRANT_HOST, port=settings.QDRANT_GRPC_PORT, prefer_grpc=True
    )
    # FIX: Use QDRANT_COLLECTION_NAME instead of QDRANT_COLLECTION
    hybrid_search = HybridSearchEngine(
        client=client, collection_name=settings.QDRANT_COLLECTION_NAME
    )
    reranker = CrossEncoderReranker(threads=4)
    return hybrid_search, reranker


def test_retrieval_context_precision_benchmark(golden_dataset, retrieval_pipeline):
    """Asserts that mean Context Precision@4 across the golden dataset is >= 0.85."""
    hybrid_search, reranker = retrieval_pipeline
    precisions: list[float] = []

    for entry in golden_dataset:
        query = entry["query"]
        expected_ids = entry.get("expected_chunk_ids", [])
        expected_module = entry.get("expected_module_name", "")

        # 1. Retrieve top 15 via Hybrid Search (RRF k=60)
        candidates = hybrid_search.search(query_text=query, top_k=15)
        assert len(candidates) > 0, f"Retrieval returned 0 candidates for query: '{query}'"

        # 2. Rerank down to top 4 via Cross-Encoder ONNX
        top_4 = reranker.rerank(query_text=query, candidates=candidates, top_n=4)
        assert len(top_4) <= 4

        # 3. Calculate Context Precision@4
        score = calculate_context_precision_at_k(
            retrieved_chunks=top_4,
            expected_chunk_ids=expected_ids,
            expected_module_name=expected_module,
            k=4,
        )
        precisions.append(score)

    mean_context_precision = sum(precisions) / len(precisions)
    print(
        f"\n[BENCHMARK] Mean Context Precision@4 across {len(precisions)} queries: {mean_context_precision:.4f}"
    )

    # PRD Section 1.3 DoD: Mean Context Precision >= 0.85
    assert mean_context_precision >= 0.85, (
        f"Retrieval Precision benchmark failed: Mean Context Precision is {mean_context_precision:.4f} < 0.85"
    )
