"""app/main.py: FastAPI entry point with Lifespan Model Warmup and Telemetry Middleware."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from qdrant_client import QdrantClient

from app.api.v1.endpoints import router as v1_router
from app.api.v1.exceptions import register_exception_handlers
from app.core.config import get_settings
from app.middleware.timing import LatencyProfilingMiddleware
from app.services.search.hybrid_search import HybridSearchEngine
from app.services.search.ood_gate import OODGate
from app.services.search.reranker import CrossEncoderReranker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Pre-warms ONNX runtimes and validates Qdrant gRPC channel on boot."""
    settings = get_settings()
    logger.info("Starting ScaffoldRAG API. Executing Subsystem warmup...")

    try:
        client = QdrantClient(
            host=settings.QDRANT_HOST, port=settings.QDRANT_GRPC_PORT, prefer_grpc=True
        )

        # 1. Warm up BGE-small Dense Model
        ood_gate = OODGate(client=client, collection_name=settings.QDRANT_COLLECTION_NAME)
        list(ood_gate.dense_model.query_embed("warmup query"))

        # 2. Warm up BM25 Sparse Model
        hybrid = HybridSearchEngine(client=client, collection_name=settings.QDRANT_COLLECTION_NAME)
        list(hybrid.sparse_model.embed(["warmup query"]))

        # 3. Warm up Cross-Encoder ONNX graph (Constructor executes batch-15 tensor pre-allocation)
        CrossEncoderReranker()

        logger.info("ONNX runtimes and gRPC channels pre-warmed successfully.")
    except Exception as exc:
        logger.warning(f"Lifespan warmup encountered a non-fatal warning: {exc}")

    yield

    logger.info("Shutting down ScaffoldRAG API.")


app = FastAPI(
    title="ScaffoldRAG Core API",
    version="1.0.0",
    description="Incremental Complexity Portfolio Generator for Computing Students",
    lifespan=lifespan,
)

# 1. Bind Middleware (First in, last out)
app.add_middleware(LatencyProfilingMiddleware)

# 2. Register Global Exception Mappings
register_exception_handlers(app)

# 3. Mount REST Subsystem Routes
app.include_router(v1_router, prefix="/api/v1")
