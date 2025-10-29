from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol


@dataclass
class SyncResult:
    acknowledged: List[int]
    rejected: Dict[int, str]


@dataclass
class UpdateManifest:
    version: str
    artifact_url: str
    signature: str
    timestamp: float


class FleetBackendProtocol(Protocol):
    """Protocol defining the backend integration layer."""

    def ping(self, site_id: str) -> bool: ...

    def send_batch(self, site_id: str, items: Iterable[Dict]) -> SyncResult: ...

    def fetch_commands(self, site_id: str) -> List[Dict]: ...

    def get_update_manifest(self, site_id: str) -> Optional[UpdateManifest]: ...

    def post_inventory(self, site_id: str, inventory: Dict) -> None: ...

    def post_diagnostics(self, site_id: str, diagnostics: Dict) -> None: ...

    def post_metrics(self, site_id: str, metrics: Dict) -> None: ...


class MockFleetBackend(FleetBackendProtocol):
    """In-memory backend emulation used for tests and simulations."""

    def __init__(self) -> None:
        self._online = True
        self.received_batches: List[Dict] = []
        self.received_inventory: List[Dict] = []
        self.received_diagnostics: List[Dict] = []
        self.received_metrics: List[Dict] = []
        self._commands: List[Dict] = []
        self._command_lock = threading.Lock()
        self._manifest: Optional[UpdateManifest] = None

    def set_online(self, online: bool) -> None:
        self._online = online

    def queue_command(self, command: Dict) -> None:
        with self._command_lock:
            self._commands.append(command)

    def set_manifest(self, manifest: Optional[UpdateManifest]) -> None:
        self._manifest = manifest

    def ping(self, site_id: str) -> bool:  # noqa: ARG002 - site_id useful for real implementations
        return self._online

    def send_batch(self, site_id: str, items: Iterable[Dict]) -> SyncResult:  # noqa: ARG002
        if not self._online:
            raise ConnectionError("backend offline")
        acknowledged: List[int] = []
        rejected: Dict[int, str] = {}
        for item in items:
            message_id = item["id"]
            if random.random() < 0.01:  # simulate rare rejection
                rejected[message_id] = "corrupted payload"
            else:
                self.received_batches.append(item)
                acknowledged.append(message_id)
        return SyncResult(acknowledged=acknowledged, rejected=rejected)

    def fetch_commands(self, site_id: str) -> List[Dict]:  # noqa: ARG002
        with self._command_lock:
            commands = list(self._commands)
            self._commands.clear()
        return commands

    def get_update_manifest(self, site_id: str) -> Optional[UpdateManifest]:  # noqa: ARG002
        if not self._online:
            return None
        manifest = self._manifest
        self._manifest = None
        return manifest

    def post_inventory(self, site_id: str, inventory: Dict) -> None:  # noqa: ARG002
        if not self._online:
            raise ConnectionError("backend offline")
        self.received_inventory.append(inventory)

    def post_diagnostics(self, site_id: str, diagnostics: Dict) -> None:  # noqa: ARG002
        if not self._online:
            raise ConnectionError("backend offline")
        diagnostics = {**diagnostics, "timestamp": time.time()}
        self.received_diagnostics.append(diagnostics)

    def post_metrics(self, site_id: str, metrics: Dict) -> None:  # noqa: ARG002
        if not self._online:
            raise ConnectionError("backend offline")
        metrics = {**metrics, "timestamp": time.time()}
        self.received_metrics.append(metrics)
