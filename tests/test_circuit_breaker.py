"""tests/test_circuit_breaker.py: Verification of Circuit Breaker FSM and Fallback Provider."""

import time

from app.core.circuit_breaker import CircuitBreaker, CircuitState, FallbackProvider
from app.schemas.roadmap import ProjectRoadmap


def test_fallback_provider_loads_valid_roadmaps() -> None:
    """Asserts that all three fallback files parse into valid ProjectRoadmap models."""
    provider = FallbackProvider()

    mle = provider.get_static_roadmap("Machine Learning Engineer")
    de = provider.get_static_roadmap("Data Engineer")
    backend = provider.get_static_roadmap("Backend AI Engineer")

    assert mle.project_title == "Production Machine Learning Search & Retrieval Engine"
    assert de.project_title == "Scalable Vector Ingestion & Batch Search Pipeline"
    assert backend.project_title == "Production Async AI Microservice Architecture"

    for roadmap in [mle, de, backend]:
        assert len(roadmap.milestones) == 5
        assert [m.stage for m in roadmap.milestones] == [1, 2, 3, 4, 5]


def test_circuit_breaker_closed_state_success() -> None:
    """Asserts normal pass-through when circuit is CLOSED."""
    breaker = CircuitBreaker(failure_threshold=3)

    target_func = lambda x: f"success: {x}"
    fallback_func = lambda x: f"fallback: {x}"

    result = breaker.execute(target_func, fallback_func, "query")
    assert result == "success: query"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_trips_to_open_after_three_failures() -> None:
    """Asserts breaker trips to OPEN after 3 consecutive exceptions."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=45.0)

    failing_func = lambda: (_ for _ in ()).throw(RuntimeError("API Outage"))
    fallback_func = lambda: "fallback_served"

    # Calls 1 & 2 fail but stay CLOSED
    res1 = breaker.execute(failing_func, fallback_func)
    assert res1 == "fallback_served"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 1

    res2 = breaker.execute(failing_func, fallback_func)
    assert res2 == "fallback_served"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 2

    # Call 3 trips to OPEN
    res3 = breaker.execute(failing_func, fallback_func)
    assert res3 == "fallback_served"
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


def test_circuit_breaker_fast_fails_when_open_under_50ms() -> None:
    """DoD Assertion: When OPEN, requests resolve in < 50ms without invoking target func."""
    breaker = CircuitBreaker(failure_threshold=1)
    provider = FallbackProvider()

    # Trip breaker
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    mock_target = lambda role: time.sleep(1.0)  # Simulates slow network hang
    fallback = lambda role: provider.get_static_roadmap(role)

    t0 = time.perf_counter()
    result: ProjectRoadmap = breaker.execute(mock_target, fallback, "Machine Learning Engineer")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 50.0  # DoD SLA requirement: < 50ms
    assert result.project_title == "Production Machine Learning Search & Retrieval Engine"


def test_circuit_breaker_half_open_recovery() -> None:
    """Asserts transition from OPEN to HALF-OPEN after timeout and healing on success."""
    # Breaker with 0.1s recovery timeout for testing
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=0.1)
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Sleep past recovery timeout
    time.sleep(0.15)

    success_target = lambda: "recovered"
    fallback = lambda: "fallback"

    result = breaker.execute(success_target, fallback)
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
