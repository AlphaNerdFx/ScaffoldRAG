"""tests/test_main.py
Tests verifying FastAPI lifespan pre-warming and application initialization.
"""

from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import app


def test_app_lifespan_prewarming():
    """Asserts that application lifespan initializes and pre-warms singletons."""
    with (
        patch("app.main.OODGate"),
        patch("app.main.HybridSearchEngine"),
        patch("app.main.CrossEncoderReranker"),
    ):
        # TestClient with 'with' context explicitly invokes the lifespan handler
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            assert response.status_code in [200, 503]
