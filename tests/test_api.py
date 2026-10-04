"""tests/test_api.py: Contract and integration test suite for Subsystem 4 REST routes."""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import (
    get_circuit_breaker,
    get_qdrant_client,
    get_repository,
)
from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.config import get_settings
from app.core.exceptions import OutOfDistributionError
from app.main import app
from app.schemas.roadmap import Milestone, ProjectRoadmap
from app.services.search.hybrid_search import ScoredChunk
from app.services.storage import SQLiteRoadmapRepository


@pytest.fixture
def mock_settings():
    """Provides validated test settings."""
    settings = get_settings()
    return settings


@pytest.fixture
def test_repo(tmp_path: Path) -> SQLiteRoadmapRepository:
    """Provisions an isolated SQLite database in a temporary directory."""
    db_file = tmp_path / "test_roadmaps.db"
    return SQLiteRoadmapRepository(db_path=db_file)


@pytest.fixture
def clean_circuit_breaker() -> CircuitBreaker:
    """Provides a fresh CircuitBreaker in CLOSED state."""
    return CircuitBreaker(failure_threshold=3, recovery_timeout_sec=45.0)


@pytest.fixture
def sample_roadmap() -> ProjectRoadmap:
    """Generates a strictly valid, 5-stage ProjectRoadmap matching SPEC_V1."""
    return ProjectRoadmap(
        roadmap_id="11111111-1111-1111-1111-111111111111",
        project_title="Distributed Hybrid RAG Pipeline",
        domain="Enterprise Search & Retrieval",
        milestones=[
            Milestone(
                stage=1,
                name="In-Memory Dense Baseline",
                tools_introduced=["FastAPI", "Qdrant", "FastEmbed"],
                why_added="Establishes a baseline semantic search engine.",
                tradeoff="Dense cosine search misses exact part numbers and domain IDs.",
                verification_metric="Mean Reciprocal Rank (MRR) >= 0.65 across 50 test queries.",
            ),
            Milestone(
                stage=2,
                name="Sparse Inverted Index Hybrid Search",
                tools_introduced=["BM25", "Reciprocal Rank Fusion"],
                why_added="Blends lexical keyword precision with semantic embeddings.",
                tradeoff="Increases query retrieval latency by an additional 15ms.",
                verification_metric="Context Recall@10 increases from 0.70 to 0.88.",
            ),
            Milestone(
                stage=3,
                name="Cross-Encoder Reranking Subsystem",
                tools_introduced=["MS-MARCO MiniLM-L-6-v2", "ONNX Runtime"],
                why_added="Recomputes cross-attention to filter irrelevant candidate chunks.",
                tradeoff="CPU compute penalty adds 350ms of cross-encoder latency.",
                verification_metric="Context Precision@4 exceeds 0.85 on golden dataset.",
            ),
            Milestone(
                stage=4,
                name="Instructor Schema Enforcement",
                tools_introduced=["Instructor", "Pydantic V2", "Groq LPU"],
                why_added="Guarantees zero malformed output payloads using native JSON validation.",
                tradeoff="Constrained generation incurs token validation retries on failures.",
                verification_metric="Zero schema validation errors across 1,000 consecutive requests.",
            ),
            Milestone(
                stage=5,
                name="Circuit Breaker & Telemetry Middleware",
                tools_introduced=["FastAPI Middleware", "Static Fallbacks"],
                why_added="Prevents cascading connection failure when upstream APIs degrade.",
                tradeoff="Requires managing in-memory state machines and fallback cache freshness.",
                verification_metric="Fallback payload resolves in under 50ms when circuit trips.",
            ),
        ],
    )


@pytest_asyncio.fixture
async def async_client(
    test_repo: SQLiteRoadmapRepository, clean_circuit_breaker: CircuitBreaker
) -> AsyncGenerator[AsyncClient, None]:
    """Provisions httpx.AsyncClient with deterministic dependency overrides."""
    app.dependency_overrides[get_repository] = lambda: test_repo
    app.dependency_overrides[get_circuit_breaker] = lambda: clean_circuit_breaker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


# ============================================================================
# 1. Health Probe Endpoint Tests (GET /health)
# ============================================================================


@pytest.mark.asyncio
async def test_health_check_healthy(async_client: AsyncClient) -> None:
    """Asserts that /health returns HTTP 200 when Qdrant socket is responsive."""
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    app.dependency_overrides[get_qdrant_client] = lambda: mock_client

    response = await async_client.get("/api/v1/health")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["qdrant"] is True


@pytest.mark.asyncio
async def test_health_check_qdrant_unhealthy(async_client: AsyncClient) -> None:
    """Asserts that /health returns HTTP 503 when Qdrant connection fails."""
    mock_client = MagicMock()
    mock_client.get_collections.side_effect = ConnectionError("Connection refused on port 6334")
    app.dependency_overrides[get_qdrant_client] = lambda: mock_client

    response = await async_client.get("/api/v1/health")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    data = response.json()
    assert data["detail"]["qdrant"] is False


# ============================================================================
# 2. Roadmap Generation Tests (POST /api/v1/roadmaps)
# ============================================================================


@pytest.mark.asyncio
async def test_post_roadmap_ood_rejection_returns_422(async_client: AsyncClient) -> None:
    """Asserts that non-computing/culinary queries trigger HTTP 422 with calibration score."""
    with patch("app.api.v1.endpoints.OODGate.validate_query") as mock_validate:
        mock_validate.side_effect = OutOfDistributionError(
            query="How to make a classic french croissant with butter",
            score=0.5120,
            threshold=0.58,
        )

        payload = {
            "target_role": "Pastry Chef",
            "domain_interest": "French Baking",
            "current_skills": ["Flour", "Yeast"],
        }
        response = await async_client.post("/api/v1/roadmaps", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    body = response.json()
    assert "Query outside supported computing architecture domains." in body["detail"]
    assert body["score"] == 0.5120
    assert body["threshold"] == 0.58


@pytest.mark.asyncio
async def test_post_roadmap_success_flow(
    async_client: AsyncClient,
    sample_roadmap: ProjectRoadmap,
    test_repo: SQLiteRoadmapRepository,
) -> None:
    """Asserts successful 5-stage synthesis returns 200, saves to SQLite, and injects headers."""
    dummy_chunk = ScoredChunk(
        chunk_id="chunk-1",
        content="Execute dense retrieval with FastEmbed.",
        module_name="Dense Retrieval",
        rrf_score=0.016,
        metadata={"header": "Architecture Pattern"},
    )

    with (
        patch("app.api.v1.endpoints.OODGate.validate_query", return_value=0.765),
        patch("app.api.v1.endpoints.HybridSearchEngine.search", return_value=[dummy_chunk]),
        patch("app.api.v1.endpoints.CrossEncoderReranker.rerank", return_value=[dummy_chunk]),
        patch("app.api.v1.endpoints.RoadmapGenerator.generate", return_value=sample_roadmap),
    ):
        payload = {
            "target_role": "Machine Learning Engineer",
            "domain_interest": "Hybrid Search Engines",
            "current_skills": ["Python", "FastAPI", "Vector DBs"],
        }
        response = await async_client.post("/api/v1/roadmaps", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("X-Fallback-Applied") == "false"

    data = response.json()
    assert data["roadmap_id"] == sample_roadmap.roadmap_id
    assert len(data["milestones"]) == 5
    assert data["milestones"][0]["stage"] == 1
    assert data["milestones"][4]["stage"] == 5

    # Verify persistence inside isolated SQLite repository
    persisted = test_repo.get_by_id(sample_roadmap.roadmap_id)
    assert persisted is not None
    assert persisted.project_title == sample_roadmap.project_title


@pytest.mark.asyncio
async def test_post_roadmap_degraded_fallback_header(
    async_client: AsyncClient,
    sample_roadmap: ProjectRoadmap,
) -> None:
    """Asserts that when CircuitBreaker is OPEN, fallback executes and sets degradation headers."""
    dummy_chunk = ScoredChunk(
        chunk_id="chunk-1",
        content="Execute dense retrieval with FastEmbed.",
        module_name="Dense Retrieval",
        rrf_score=0.016,
    )

    # Force circuit breaker into OPEN state
    open_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=45.0)
    open_breaker.state = CircuitState.OPEN
    app.dependency_overrides[get_circuit_breaker] = lambda: open_breaker

    with (
        patch("app.api.v1.endpoints.OODGate.validate_query", return_value=0.78),
        patch("app.api.v1.endpoints.HybridSearchEngine.search", return_value=[dummy_chunk]),
        patch("app.api.v1.endpoints.CrossEncoderReranker.rerank", return_value=[dummy_chunk]),
        patch(
            "app.api.v1.endpoints.FallbackProvider.get_static_roadmap", return_value=sample_roadmap
        ),
    ):
        payload = {
            "target_role": "Data Engineer",
            "domain_interest": "Log Analytics",
            "current_skills": ["SQL", "Python"],
        }
        response = await async_client.post("/api/v1/roadmaps", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("X-Fallback-Applied") == "true"
    assert response.headers.get("X-Fallback-Reason") == "upstream_failure_or_load"


# ============================================================================
# 3. Roadmap Export Tests (GET /api/v1/roadmaps/{id}/export)
# ============================================================================


@pytest.mark.asyncio
async def test_get_export_markdown_success(
    async_client: AsyncClient,
    sample_roadmap: ProjectRoadmap,
    test_repo: SQLiteRoadmapRepository,
) -> None:
    """Asserts that saved roadmap exports into a valid GitHub checklist formatted string."""
    # Seed the temporary database
    test_repo.save(sample_roadmap)

    response = await async_client.get(
        f"/api/v1/roadmaps/{sample_roadmap.roadmap_id}/export?format=markdown"
    )

    assert response.status_code == status.HTTP_200_OK
    assert "text/markdown" in response.headers.get("content-type", "")

    content = response.text
    # Assert structural GitHub checklist tokens
    assert f"# {sample_roadmap.project_title}" in content
    assert f"`{sample_roadmap.roadmap_id}`" in content
    assert "## Stage 1: In-Memory Dense Baseline" in content
    assert "- [ ] **Verification Metric:**" in content
    assert "- **Documented Tradeoff:**" in content


@pytest.mark.asyncio
async def test_get_export_not_found_returns_404(async_client: AsyncClient) -> None:
    """Asserts that querying a non-existent roadmap ID returns HTTP 404."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    response = await async_client.get(f"/api/v1/roadmaps/{non_existent_id}/export?format=markdown")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert f"Roadmap ID '{non_existent_id}' does not exist" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_export_invalid_format_query_returns_422(
    async_client: AsyncClient,
    sample_roadmap: ProjectRoadmap,
    test_repo: SQLiteRoadmapRepository,
) -> None:
    """Asserts that unsupported export formats (e.g. format=pdf) fail schema validation."""
    test_repo.save(sample_roadmap)
    response = await async_client.get(
        f"/api/v1/roadmaps/{sample_roadmap.roadmap_id}/export?format=pdf"
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
