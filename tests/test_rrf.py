"""tests/test_rrf.py
Unit tests isolating Reciprocal Rank Fusion algorithmic invariants.
"""

from unittest.mock import MagicMock

import pytest

from app.services.search.hybrid_search import HybridSearchEngine


@pytest.fixture
def mock_qdrant_client():
    return MagicMock()


@pytest.fixture
def hybrid_search_engine(mock_qdrant_client):
    return HybridSearchEngine(
        client=mock_qdrant_client,
        collection_name="engineering_blueprints",
        rrf_k=60,
    )


def test_rrf_scoring_formula_calculation(hybrid_search_engine, mock_qdrant_client):
    """Asserts that points appearing in both dense and sparse have RRF scores exactly equal to 1/(60+r1) + 1/(60+r2)."""
    point_id = "point-123"
    payload = {"module_name": "Module A", "content": "Content A" * 10}

    mock_hit_dense = MagicMock()
    mock_hit_dense.id = point_id
    mock_hit_dense.payload = payload

    mock_hit_sparse = MagicMock()
    mock_hit_sparse.id = point_id
    mock_hit_sparse.payload = payload

    # Both return point-123 at rank 1
    mock_qdrant_client.search.side_effect = [[mock_hit_dense], [mock_hit_sparse]]

    results = hybrid_search_engine.search("sample query", top_k=1)
    assert len(results) == 1
    expected_score = (1.0 / (60 + 1)) + (1.0 / (60 + 1))
    assert pytest.approx(results[0].rrf_score, rel=1e-5) == expected_score


def test_rrf_disjoint_candidate_lists(hybrid_search_engine, mock_qdrant_client):
    """Asserts that disjoint dense and sparse sets are correctly merged and ranked."""
    hit_dense = MagicMock(id="p1", payload={"module_name": "Dense Top", "content": "D" * 50})
    hit_sparse = MagicMock(id="p2", payload={"module_name": "Sparse Top", "content": "S" * 50})

    mock_qdrant_client.search.side_effect = [[hit_dense], [hit_sparse]]

    results = hybrid_search_engine.search("sample query", top_k=5)
    assert len(results) == 2
    # Both ranked #1 in their respective lists -> identical RRF score 1/(60+1)
    assert pytest.approx(results[0].rrf_score, rel=1e-5) == 1.0 / 61
    assert pytest.approx(results[1].rrf_score, rel=1e-5) == 1.0 / 61


def test_rrf_empty_query_returns_empty_list(hybrid_search_engine, mock_qdrant_client):
    """Asserts that empty or whitespace query skips retrieval entirely."""
    assert hybrid_search_engine.search("") == []
    assert hybrid_search_engine.search("   ") == []
    mock_qdrant_client.search.assert_not_called()


def test_rrf_respects_top_k_truncation(hybrid_search_engine, mock_qdrant_client):
    """Asserts that candidate pool is strictly truncated to top_k."""
    dense_hits = [
        MagicMock(id=f"p_{i}", payload={"module_name": f"Mod {i}", "content": "C" * 50})
        for i in range(20)
    ]
    sparse_hits = [
        MagicMock(id=f"p_{i}", payload={"module_name": f"Mod {i}", "content": "C" * 50})
        for i in range(20, 40)
    ]
    mock_qdrant_client.search.side_effect = [dense_hits, sparse_hits]

    results = hybrid_search_engine.search("sample query", top_k=15)
    assert len(results) == 15
