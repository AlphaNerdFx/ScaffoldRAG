"""app/core/circuit_breaker.py: SRE Circuit Breaker and Fallback Subsystem."""

import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar

from app.schemas.roadmap import ProjectRoadmap

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Discrete states of the circuit breaker finite state machine."""

    CLOSED = "CLOSED"  # Normal operations; calls routed to upstream
    OPEN = "OPEN"  # Outage detected; upstream blocked, serving fallbacks
    HALF_OPEN = "HALF-OPEN"  # Testing canary call to verify upstream recovery


class CircuitBreakerOpenException(Exception):
    """Raised when an external call is rejected because the circuit is OPEN."""


class FallbackProvider:
    """Loads and caches pre-indexed, verified static roadmaps from disk."""

    def __init__(self, fallback_dir: Path | None = None) -> None:
        self.fallback_dir = fallback_dir or Path("data/fallbacks")
        self._cache: dict[str, ProjectRoadmap] = {}
        self._load_and_validate_all()

    def _load_and_validate_all(self) -> None:
        """Parses and validates all fallback files at startup to fail fast."""
        if not self.fallback_dir.exists():
            raise FileNotFoundError(f"Fallback directory missing: {self.fallback_dir}")

        for file_path in self.fallback_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                roadmap = ProjectRoadmap.model_validate(data)
                self._cache[file_path.stem] = roadmap
            except Exception as e:
                raise ValueError(f"Corrupt fallback JSON file '{file_path.name}': {e}") from e

        if not self._cache:
            logger.warning(f"No fallback JSON files found in {self.fallback_dir}")

    def get_static_roadmap(self, role: str) -> ProjectRoadmap:
        """Resolves target role to a matching static fallback blueprint."""
        normalized = role.lower()
        if "data" in normalized:
            key = "de_roadmap"
        elif "backend" in normalized or "api" in normalized:
            key = "backend_ai_roadmap"
        else:
            # Default to Machine Learning Engineer
            key = "mle_roadmap"

        if key in self._cache:
            return self._cache[key]

        # If cache lookup fails, return the first available fallback
        if self._cache:
            return next(iter(self._cache.values()))

        raise RuntimeError("No validated fallback roadmaps available on disk.")


class CircuitBreaker:
    """Manages failure tracking and state transitions for external service calls."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 45.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0

    def _update_state(self) -> None:
        """Evaluates time-based state transitions from OPEN to HALF-OPEN."""
        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.recovery_timeout_sec:
                logger.info("Recovery timeout elapsed. Circuit transitioning to HALF-OPEN.")
                self.state = CircuitState.HALF_OPEN

    def record_success(self) -> None:
        """Resets failure counters upon a successful external invocation."""
        if self.state != CircuitState.CLOSED:
            logger.info("Upstream call succeeded. Healing circuit to CLOSED.")
        self.state = CircuitState.CLOSED
        self.failure_count = 0

    def record_failure(self) -> None:
        """Increments failure count and trips the breaker if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Canary call failed in HALF-OPEN. Re-tripping circuit to OPEN.")
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            logger.error(
                f"Failure threshold ({self.failure_threshold}) reached. Tripping circuit to OPEN."
            )
            self.state = CircuitState.OPEN

    def execute(
        self,
        func: Callable[..., T],
        fallback_func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Executes func if CLOSED/HALF-OPEN. If OPEN or on execution error,
        invokes fallback_func immediately.
        """
        self._update_state()

        if self.state == CircuitState.OPEN:
            logger.warning("Circuit is OPEN. Fast-failing and executing fallback handler.")
            return fallback_func(*args, **kwargs)

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            logger.error(f"External call failed: {e}. Recording failure and invoking fallback.")
            self.record_failure()
            return fallback_func(*args, **kwargs)
