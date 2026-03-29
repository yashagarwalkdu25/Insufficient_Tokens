"""Per-source circuit breaker with CLOSED → OPEN → HALF_OPEN states."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any

import structlog

from ..config.constants import (
    CB_FAILURE_THRESHOLD,
    CB_FAILURE_WINDOW_SECONDS,
    CB_RECOVERY_TIMEOUT_SECONDS,
)

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Lightweight async circuit breaker for a single upstream source."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = CB_FAILURE_THRESHOLD,
        failure_window: float = CB_FAILURE_WINDOW_SECONDS,
        recovery_timeout: float = CB_RECOVERY_TIMEOUT_SECONDS,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.failure_window = failure_window
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failures: list[float] = []
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "circuit_breaker.half_open",
                    source=self.name,
                    elapsed=round(elapsed, 1),
                )
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state is CircuitState.OPEN

    def _prune_old_failures(self) -> None:
        cutoff = time.monotonic() - self.failure_window
        self._failures = [t for t in self._failures if t > cutoff]

    def record_failure(self) -> None:
        now = time.monotonic()
        self._failures.append(now)
        self._last_failure_time = now
        self._prune_old_failures()

        if len(self._failures) >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "circuit_breaker.opened",
                source=self.name,
                failures=len(self._failures),
                window=self.failure_window,
            )

    def record_success(self) -> None:
        self._failures.clear()
        if self._state is not CircuitState.CLOSED:
            logger.info("circuit_breaker.closed", source=self.name)
        self._state = CircuitState.CLOSED

    # ------------------------------------------------------------------
    # Async context manager: auto-record success / failure
    # ------------------------------------------------------------------

    async def __aenter__(self) -> CircuitBreaker:
        if self.is_open:
            raise CircuitOpenError(self.name)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if exc_type is not None:
            self.record_failure()
        else:
            self.record_success()
        return False


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        super().__init__(f"Circuit breaker OPEN for {source_name}")
