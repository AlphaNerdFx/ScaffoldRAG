"""app/middleware/timing.py: Subsystem latency profiling and structured JSON logging."""

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Telemetry logger writing pure JSON
telemetry_logger = logging.getLogger("scaffold_rag.telemetry")
telemetry_logger.setLevel(logging.INFO)


class LatencyProfilingMiddleware(BaseHTTPMiddleware):
    """Measures component latencies and appends timing headers and structured logs."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()

        # Initialize default timings on request state in case endpoint aborts early
        request.state.timings = {}

        try:
            response: Response = await call_next(request)
        except Exception:
            # Calculate total time even on unhandled application failures
            t_total_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self._log_telemetry(request, 500, t_total_ms)
            raise

        t_total_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Inject timing header into response
        response.headers["X-Process-Time-Ms"] = str(t_total_ms)

        # Emit structured log
        self._log_telemetry(request, response.status_code, t_total_ms)
        return response

    def _log_telemetry(self, request: Request, status_code: int, t_total_ms: float) -> None:
        """Formats and outputs a structured JSON log entry."""
        timings: dict[str, float] = getattr(request.state, "timings", {})
        client_ip = request.client.host if request.client else "unknown"

        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "client_ip": client_ip,
            "t_ood_ms": timings.get("t_ood_ms", 0.0),
            "t_retrieval_ms": timings.get("t_retrieval_ms", 0.0),
            "t_rerank_ms": timings.get("t_rerank_ms", 0.0),
            "t_generation_ms": timings.get("t_generation_ms", 0.0),
            "t_total_ms": t_total_ms,
        }

        telemetry_logger.info(json.dumps(log_record))
