from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .backend import FleetBackendProtocol


@dataclass
class ConnectivityState:
    last_successful_ping: Optional[float] = None
    last_failure: Optional[float] = None
    consecutive_failures: int = 0
    is_online: bool = True


@dataclass
class ConnectivityMonitor:
    backend: FleetBackendProtocol
    site_id: str
    ping_timeout_seconds: int = 5
    state: ConnectivityState = field(default_factory=ConnectivityState)

    def evaluate(self) -> ConnectivityState:
        now = time.time()
        try:
            if self.backend.ping(self.site_id):
                self.state.last_successful_ping = now
                self.state.consecutive_failures = 0
                self.state.is_online = True
            else:
                self._register_failure(now)
        except Exception:  # pragma: no cover - defensive safeguard
            self._register_failure(now)
        return self.state

    def _register_failure(self, timestamp: float) -> None:
        self.state.last_failure = timestamp
        self.state.consecutive_failures += 1
        self.state.is_online = False

    def online(self) -> bool:
        return self.state.is_online
