"""Unit and integration tests for Subsystem 2.2: Hybrid Search Engine."""

from app.services.search.hybrid_search import HybridSearchEngine


def test_hybrid_search_lexical_token_dominance(hybrid_search_engine: HybridSearchEngine) -> None:
    """Asserts that BM25 elevates exact library tokens into the top 3 results."""
    query = "FastAPI middleware for telemetry latency headers"
    results = hybrid_search_engine.search(query, top_k=15)

    assert len(results) == 15
    top_3_modules = [chunk.module_name for chunk in results[:3]]
    assert any("Telemetry" in name for name in top_3_modules), (
        "BM25 lexical search failed to elevate exact token 'Telemetry' into top 3."
    )


def test_hybrid_search_semantic_dominance(hybrid_search_engine: HybridSearchEngine) -> None:
    """Asserts that dense cosine search matches abstract conceptual descriptions."""
    query = "Prevent cascading backend failures when downstream LLM APIs timeout"
    results = hybrid_search_engine.search(query, top_k=15)

    assert len(results) == 15
    top_3_modules = [chunk.module_name for chunk in results[:3]]
    assert any("Circuit Breaker" in name for name in top_3_modules), (
        "Dense semantic search failed to elevate concept 'Circuit Breaker' into top 3."
    )


def test_hybrid_search_rrf_scoring_invariants(hybrid_search_engine: HybridSearchEngine) -> None:
    """Asserts that RRF scores are strictly positive fractions and monotonically descending."""
    query = "Redis semantic caching and distributed task queues"
    results = hybrid_search_engine.search(query, top_k=15)

    assert len(results) == 15
    scores = [c.rrf_score for c in results]

    # Scores must be strictly positive fractions: 1/(60+rank)
    assert all(score > 0.0 for score in scores)

    # Scores must descend monotonically
    assert scores == sorted(scores, reverse=True), "RRF scores are not descending."

    # Validate payload fields on all returned chunks
    for chunk in results:
        assert chunk.chunk_id
        assert chunk.module_name
        assert len(chunk.content) > 0
        assert "difficulty_level" in chunk.metadata


def test_hybrid_search_difficulty_filtering(hybrid_search_engine: HybridSearchEngine) -> None:
    """Asserts that difficulty_level filters correctly restrict candidate selection."""
    query = "Basic Python in-memory vector retrieval baseline"
    # Blueprint 01 is the only module with difficulty_level = 1
    results = hybrid_search_engine.search(query, top_k=15, max_difficulty=1)

    assert len(results) > 0
    for chunk in results:
        assert chunk.metadata["difficulty_level"] <= 1