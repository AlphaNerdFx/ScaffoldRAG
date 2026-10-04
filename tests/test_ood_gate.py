"""Unit and integration tests for Subsystem 2.1: Out-of-Distribution Hard Gate."""

import pytest

from app.core.exceptions import OutOfDistributionError
from app.services.search.ood_gate import OODGate


def test_ood_gate_in_domain_queries(ood_gate: OODGate) -> None:
    """Asserts that technical computing queries score >= 0.58 and return valid=True."""
    in_domain_queries = [
        ("Build an async RAG API with FastAPI", 0.70),
        ("Implement Reciprocal Rank Fusion with BM25 and sparse vectors", 0.70),
        ("React frontend state management using Redux Toolkit", 0.58),
        ("Redis distributed locking and semantic caching layer", 0.70),
    ]

    for query, expected_floor in in_domain_queries:
        valid, score = ood_gate.evaluate_query(query)
        assert valid is True, f"In-domain query '{query}' was rejected by the gate."
        assert score >= expected_floor, (
            f"Query '{query}' scored {score:.4f}, expected >= {expected_floor:.2f}"
        )


def test_ood_gate_out_of_distribution_queries(ood_gate: OODGate) -> None:
    """Asserts that culinary, spam, and non-computing queries score < 0.58 and return valid=False."""
    ood_queries = [
        "Best sourdough bread recipe with wild yeast fermentation",
        "The quick brown fox jumps over the lazy dog",
        "How to train a golden retriever puppy to sit",
        "History of ancient Roman architecture and aqueducts",
    ]

    for query in ood_queries:
        valid, score = ood_gate.evaluate_query(query)
        assert valid is False, f"OOD query '{query}' unexpectedly passed the gate."
        assert score < 0.58, f"OOD query '{query}' scored {score:.4f} >= 0.58"


def test_ood_gate_validate_query_raises_exception(ood_gate: OODGate) -> None:
    """Asserts that validate_query raises OutOfDistributionError with accurate metadata."""
    query = "Best sourdough bread recipe with wild yeast fermentation"
    with pytest.raises(OutOfDistributionError) as exc_info:
        ood_gate.validate_query(query)

    assert exc_info.value.query == query
    assert exc_info.value.score < 0.58
    assert exc_info.value.threshold == 0.58


def test_ood_gate_empty_or_whitespace_query(ood_gate: OODGate) -> None:
    """Asserts that blank strings fail gracefully without triggering database exceptions."""
    valid, score = ood_gate.evaluate_query("   ")
    assert valid is False
    assert score == 0.0
