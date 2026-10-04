"""app/api/v1/exceptions.py: Global FastAPI exception handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import OutOfDistributionError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Binds domain exception mappings to the FastAPI transport layer."""

    @app.exception_handler(OutOfDistributionError)
    async def out_of_distribution_handler(
        request: Request, exc: OutOfDistributionError
    ) -> JSONResponse:
        logger.warning(
            f"OOD query rejected: query='{exc.query}' score={exc.score:.4f} threshold={exc.threshold}"
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Query outside supported computing architecture domains.",
                "score": round(exc.score, 4),
                "threshold": exc.threshold,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled error on path '{request.url.path}': {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error encountered while processing request."},
        )
