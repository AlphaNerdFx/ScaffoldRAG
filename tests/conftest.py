"""PyTest Shared Fixtures for Phase 2: Hybrid Retrieval & Ranking Subsystem.

Provides session-scoped singleton instances of QdrantClient, OODGate,
HybridSearchEngine, and CrossEncoderReranker.
"""

from typing import Generator

import pytest
from qdrant_client import QdrantClient

from app.core.config import settings
from app.services.search.hybrid_search import HybridSearchEngine
from app.services.search.ood_gate import OODGate
from app.services.search.reranker import CrossEncoderReranker


@pytest.fixture(scope="session")
def qdrant_client() -> Generator[QdrantClient, None, None]:
    """Provides a shared gRPC QdrantClient connection for the entire test session."""
    client = QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_GRPC_PORT,
        prefer_grpc=True,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def ood_gate(qdrant_client: QdrantClient) -> OODGate:
    """Provides a singleton instance of the calibrated OOD gate (threshold=0.58)."""
    return OODGate(client=qdrant_client, threshold=0.58)


@pytest.fixture(scope="session")
def hybrid_search_engine(qdrant_client: QdrantClient) -> HybridSearchEngine:
    """Provides a singleton instance of the client-side RRF hybrid search engine."""
    return HybridSearchEngine(client=qdrant_client, rrf_k=60)


@pytest.fixture(scope="session")
def reranker() -> CrossEncoderReranker:
    """Provides a pre-warmed singleton instance of the ONNX Cross-Encoder reranker."""
    return CrossEncoderReranker(max_content_chars=350, threads=4)
