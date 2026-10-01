"""Domain-specific exception hierarchy for ScaffoldRAG.

All custom exceptions decouple core business and retrieval logic from
transport protocols (HTTP, gRPC, CLI).
"""

from typing import Any


class ScaffoldRAGError(Exception):
    """Base exception for all domain errors within ScaffoldRAG."""
    pass


class OutOfDistributionError(ScaffoldRAGError):
    """Raised when an incoming user query fails the cosine similarity threshold."""

    def __init__(
        self,
        query: str,
        score: float,
        threshold: float = 0.40,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.query = query
        self.score = score
        self.threshold = threshold
        self.metadata = metadata or {}
        super().__init__(
            f"Query '{query}' failed OOD gate. Cosine similarity {score:.4f} "
            f"is strictly below the hard gate threshold of {threshold:.2f}."
        )


class CollectionNotFoundError(ScaffoldRAGError):
    """Raised when querying a Qdrant collection that has not been initialized."""
    pass


class CorpusEmptyError(ScaffoldRAGError):
    """Raised when the collection contains 0 indexed points."""
    pass