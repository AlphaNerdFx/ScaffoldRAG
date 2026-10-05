"""app/api/v1/endpoints.py: Primary REST route definitions with persistent singleton injection."""

import logging
import time
from typing import Annotated,  Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from qdrant_client import QdrantClient

from app.core.circuit_breaker import CircuitBreaker, FallbackProvider
from app.core.config import get_settings
from app.schemas.roadmap import ProjectRoadmap, RoadmapRequest
from app.services.exporter import roadmap_to_markdown
from app.services.generator import RoadmapGenerator
from app.services.search.hybrid_search import HybridSearchEngine
from app.services.search.ood_gate import OODGate
from app.services.search.reranker import CrossEncoderReranker
from app.services.storage import RoadmapRepository, SQLiteRoadmapRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Persistent Singletons (Initialized once during module load / lifespan)
# ============================================================================
_settings = get_settings()
_storage_repo = SQLiteRoadmapRepository()
_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=45.0)
_fallback_provider = FallbackProvider()

# Shared Qdrant gRPC Client
_qdrant_client = QdrantClient(
    host=_settings.QDRANT_HOST,
    port=_settings.QDRANT_GRPC_PORT,
    prefer_grpc=True,
)

# Shared AI / ML Engines (Instantiated once to avoid per-request ONNX loading)
_ood_gate = OODGate(client=_qdrant_client, collection_name=_settings.QDRANT_COLLECTION_NAME)
_hybrid_searcher = HybridSearchEngine(
    client=_qdrant_client, collection_name=_settings.QDRANT_COLLECTION_NAME
)
_reranker = CrossEncoderReranker()
_generator = RoadmapGenerator()


# Dependency Providers
def get_repository() -> RoadmapRepository:
    return _storage_repo


def get_circuit_breaker() -> CircuitBreaker:
    return _circuit_breaker


def get_qdrant_client() -> QdrantClient:
    return _qdrant_client


def get_fallback_provider() -> FallbackProvider:
    return _fallback_provider


def get_ood_gate() -> OODGate:
    return _ood_gate


def get_hybrid_searcher() -> HybridSearchEngine:
    return _hybrid_searcher


def get_reranker() -> CrossEncoderReranker:
    return _reranker


def get_generator() -> RoadmapGenerator:
    return _generator


# ============================================================================
# Routes
# ============================================================================
@router.post(
    "/roadmaps",
    response_model=ProjectRoadmap,
    status_code=status.HTTP_200_OK,
    summary="Generate Scaffolded Architecture Roadmap",
)
def generate_roadmap(
    request_data: RoadmapRequest,
    http_request: Request,
    response: Response,
    repo: Annotated[RoadmapRepository, Depends(get_repository)],
    circuit_breaker: Annotated[CircuitBreaker, Depends(get_circuit_breaker)],
    fallback_provider: Annotated[FallbackProvider, Depends(get_fallback_provider)],
    ood_gate: Annotated[OODGate, Depends(get_ood_gate)],
    hybrid_searcher: Annotated[HybridSearchEngine, Depends(get_hybrid_searcher)],
    reranker: Annotated[CrossEncoderReranker, Depends(get_reranker)],
    generator: Annotated[RoadmapGenerator, Depends(get_generator)],
) -> ProjectRoadmap:
    """Executes OOD Gate -> Hybrid Search -> Reranker -> Generator with sub-millisecond telemetry."""
    http_request.state.timings = {
        "t_ood_ms": 0.0,
        "t_retrieval_ms": 0.0,
        "t_rerank_ms": 0.0,
        "t_generation_ms": 0.0,
    }

    query_text = (
        f"{request_data.target_role} in {request_data.domain_interest}. "
        f"Skills: {', '.join(request_data.current_skills)}"
    )

    # 1. Subsystem 2.1: OOD Gate Timing
    t_ood_start = time.perf_counter()
    ood_gate.validate_query(query_text)
    http_request.state.timings["t_ood_ms"] = round((time.perf_counter() - t_ood_start) * 1000, 2)

    # 2. Subsystem 2.2: Hybrid Retrieval Timing
    t_retrieval_start = time.perf_counter()
    candidates = hybrid_searcher.search(query_text=query_text, top_k=15)
    http_request.state.timings["t_retrieval_ms"] = round(
        (time.perf_counter() - t_retrieval_start) * 1000, 2
    )

    # 3. Subsystem 2.3: Cross-Encoder Reranker Timing
    t_rerank_start = time.perf_counter()
    reranked_chunks = reranker.rerank(query_text=query_text, candidates=candidates, top_n=4)
    http_request.state.timings["t_rerank_ms"] = round(
        (time.perf_counter() - t_rerank_start) * 1000, 2
    )

    # 4. Subsystems 3 & 5: Generation Timing (Protected by Circuit Breaker)
    was_fallback: bool = False

    def primary_call() -> ProjectRoadmap:
        return generator.generate(request=request_data, context_chunks=reranked_chunks)

    def fallback_call() -> ProjectRoadmap:
        nonlocal was_fallback
        was_fallback = True
        logger.warning(f"Circuit breaker fallback triggered for role: {request_data.target_role}")
        return fallback_provider.get_static_roadmap(role=request_data.target_role)

    if circuit_breaker.state.value == "OPEN":
        was_fallback = True

    t_gen_start = time.perf_counter()
    try:
        roadmap = circuit_breaker.execute(primary_call, fallback_call)
    except Exception as exc:
        logger.error(f"Downstream generation failed completely: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream generative model failed to return compliant schema.",
        ) from exc
    finally:
        http_request.state.timings["t_generation_ms"] = round(
            (time.perf_counter() - t_gen_start) * 1000, 2
        )

    if was_fallback:
        response.headers["X-Fallback-Applied"] = "true"
        response.headers["X-Fallback-Reason"] = "upstream_failure_or_load"
    else:
        response.headers["X-Fallback-Applied"] = "false"

    repo.save(roadmap)
    return roadmap


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="System Health & Readiness Probe",
)
def health_check(
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
) -> dict[str, str | bool]:
    """Verifies Qdrant gRPC socket and inference configuration readiness."""
    qdrant_healthy = False
    try:
        client.get_collections()
        qdrant_healthy = True
    except Exception as exc:
        logger.error(f"Health check failed to communicate with Qdrant: {exc}")

    if not qdrant_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "qdrant": False},
        )

    return {"status": "healthy", "qdrant": True}


@router.get("/roadmaps/{id}/export")
async def export_roadmap(
    id: str,
    format: Literal["markdown"] = Query(default="markdown"),
    repo: RoadmapRepository = Depends(get_repository),
) -> Response:
    """Fetches roadmap by ID and converts it to raw Markdown checklist."""
    if format != "markdown":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported format '{format}'. Only 'markdown' is currently supported.",
        )

    roadmap = repo.get_by_id(id)
    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Roadmap ID '{id}' does not exist.",
        )

    markdown_content = roadmap_to_markdown(roadmap)
    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="roadmap_{id}.md"'},
    )
