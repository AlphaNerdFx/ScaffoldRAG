"""tests/test_timing_middleware.py: Validates Task 4.2 telemetry middleware."""

import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_timing_header_injected_on_health() -> None:
    """Asserts that X-Process-Time-Ms header is injected on all requests."""
    transport = ASGITransport(app=app)
    with patch("app.api.v1.endpoints.QdrantClient") as mock_qdrant_cls:
        mock_instance = MagicMock()
        mock_instance.get_collections.return_value = MagicMock(collections=[])
        mock_qdrant_cls.return_value = mock_instance

        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert "X-Process-Time-Ms" in response.headers
    process_time = float(response.headers["X-Process-Time-Ms"])
    assert process_time >= 0.0


@pytest.mark.asyncio
async def test_structured_json_log_emitted(caplog: pytest.LogCaptureFixture) -> None:
    """Asserts that telemetry logs emit a parsable JSON string with all timing fields."""
    import logging

    caplog.set_level(logging.INFO, logger="scaffold_rag.telemetry")

    transport = ASGITransport(app=app)
    with patch("app.api.v1.endpoints.QdrantClient") as mock_qdrant_cls:
        mock_instance = MagicMock()
        mock_instance.get_collections.return_value = MagicMock(collections=[])
        mock_qdrant_cls.return_value = mock_instance

        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await client.get("/api/v1/health")

    telemetry_records = [
        record for record in caplog.records if record.name == "scaffold_rag.telemetry"
    ]
    assert len(telemetry_records) >= 1

    last_record = json.loads(telemetry_records[-1].message)
    assert "timestamp" in last_record
    assert "t_total_ms" in last_record
    assert "t_retrieval_ms" in last_record
    assert "t_rerank_ms" in last_record
    assert "t_generation_ms" in last_record
    assert last_record["path"] == "/api/v1/health"
    assert last_record["status_code"] == 200
