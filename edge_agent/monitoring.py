from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict


class TelemetryBuffer:
    """Collects operational metrics for remote observability."""

    def __init__(self) -> None:
        self._metrics: Dict[str, float] = defaultdict(float)
        self._last_flush = time.time()

    def increment(self, key: str, value: float = 1.0) -> None:
        self._metrics[key] += value

    def gauge(self, key: str, value: float) -> None:
        self._metrics[key] = value

    def snapshot(self, include_timestamp: bool = True) -> Dict[str, float]:
        snapshot = dict(self._metrics)
        if include_timestamp:
            snapshot["timestamp"] = time.time()
        return snapshot

    def flush(self) -> Dict[str, float]:
        data = self.snapshot()
        self._metrics.clear()
        self._last_flush = time.time()
        return data

    @property
    def seconds_since_flush(self) -> float:
        return time.time() - self._last_flush
