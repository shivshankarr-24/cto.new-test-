from __future__ import annotations

import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .backend import FleetBackendProtocol, SyncResult
from .cache import CacheItem, OfflineCache
from .config import AgentConfig
from .connectivity import ConnectivityMonitor
from .management import ManagementCommand, RemoteManagement
from .monitoring import TelemetryBuffer
from .update import UpdateManager, UpdateState


@dataclass
class AgentState:
    offline_since: Optional[float] = None
    last_inventory_sync: float = field(default_factory=lambda: 0.0)
    last_metrics_flush: float = field(default_factory=lambda: 0.0)
    last_update_poll: float = field(default_factory=lambda: 0.0)
    events_sent: int = 0
    events_cached: int = 0
    rejected_events: int = 0


class EdgeAgent:
    """Resilient edge runtime coordinating connectivity, caching, and updates."""

    def __init__(
        self,
        config: AgentConfig,
        backend: FleetBackendProtocol,
        update_state: Optional[UpdateState] = None,
        cache: Optional[OfflineCache] = None,
    ) -> None:
        self._config = config
        self._config.ensure_directories()
        cache_path = cache.path if cache else self._config.cache_path
        self._cache = cache or OfflineCache(cache_path)
        self._backend = backend
        self._connectivity = ConnectivityMonitor(backend=backend, site_id=config.site_id)
        self._management = RemoteManagement(config.log_directory, config.diag_log_lines)
        self._telemetry = TelemetryBuffer()
        self._state = AgentState()
        updates_dir = self._config.data_directory / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)

        def install_callback(artifact_path: Path) -> None:
            destination = updates_dir / artifact_path.name
            shutil.copy(artifact_path, destination)

        self._update_manager = UpdateManager(
            secret_key=config.secret_key,
            state=update_state or UpdateState(current_version="0.0.0"),
            install_callback=install_callback,
        )
        self._logger = logging.getLogger("edge_agent")
        self._setup_logging()

    def _setup_logging(self) -> None:
        log_file = self._config.log_directory / "edge-agent.log"
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            self._logger.addHandler(handler)

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def telemetry(self) -> TelemetryBuffer:
        return self._telemetry

    @property
    def current_version(self) -> str:
        return self._update_manager.current_version

    def ingest_payload(self, payload: Dict) -> None:
        envelope = {
            "payload": payload,
            "ingested_at": time.time(),
            "site_id": self._config.site_id,
            "uuid": uuid.uuid4().hex,
        }
        self._cache.append(envelope)
        self._state.events_cached = self._cache.count()
        self._telemetry.increment("events_ingested")

    def process_cycle(self) -> None:
        self._telemetry.gauge("cache_depth", float(self._cache.count()))
        self._telemetry.gauge("cache_size_bytes", float(self._cache.total_size_bytes()))
        self._cache.trim_to_limit(self._config.offline_cache_limit_bytes)
        connectivity_state = self._connectivity.evaluate()

        if connectivity_state.is_online:
            self._handle_online_cycle()
        else:
            self._handle_offline_cycle()

    def _handle_online_cycle(self) -> None:
        if self._state.offline_since:
            duration = time.time() - self._state.offline_since
            self._telemetry.gauge("offline_duration_seconds", duration)
            self._state.offline_since = None
            self._logger.info("Recovered connectivity after %.2fs", duration)
        self._flush_payloads()
        self._sync_inventory_if_needed()
        self._flush_metrics_if_needed(force=True)
        self._poll_remote_commands()
        self._poll_updates_if_due()

    def _handle_offline_cycle(self) -> None:
        if not self._state.offline_since:
            self._state.offline_since = time.time()
            self._logger.warning("Connectivity lost, entering offline mode")
        self._flush_metrics_if_needed(force=False)

    def _flush_payloads(self) -> None:
        batch = self._cache.get_batch(self._config.max_batch_size)
        while batch:
            payload = self._format_batch(batch)
            try:
                result = self._backend.send_batch(self._config.site_id, payload)
            except Exception as exc:
                self._logger.error("Failed to send batch: %s", exc)
                break
            self._handle_sync_result(batch, result)
            batch = self._cache.get_batch(self._config.max_batch_size)

    def _handle_sync_result(self, batch: List[CacheItem], result: SyncResult) -> None:
        acknowledged = set(result.acknowledged)
        self._cache.remove(acknowledged)
        rejected_ids = set(result.rejected.keys())
        if rejected_ids:
            self._cache.remove(rejected_ids)
            self._state.rejected_events += len(rejected_ids)
            self._telemetry.increment("events_rejected", len(rejected_ids))
            self._logger.warning("Rejected %d events: %s", len(rejected_ids), result.rejected)
        sent_count = len(acknowledged)
        self._state.events_sent += sent_count
        self._telemetry.increment("events_sent", sent_count)
        self._state.events_cached = self._cache.count()

    def _format_batch(self, batch: List[CacheItem]) -> List[Dict]:
        formatted = []
        for item in batch:
            envelope = dict(item.payload)
            envelope["id"] = item.id
            formatted.append(envelope)
        return formatted

    def _sync_inventory_if_needed(self) -> None:
        now = time.time()
        if now - self._state.last_inventory_sync < self._config.inventory_refresh_hours * 3600:
            return
        inventory = self._management.collect_inventory()
        try:
            self._backend.post_inventory(self._config.site_id, inventory)
            self._state.last_inventory_sync = now
            self._logger.info("Inventory sync completed")
        except Exception as exc:
            self._logger.error("Failed to sync inventory: %s", exc)

    def _flush_metrics_if_needed(self, force: bool) -> None:
        if not force and self._telemetry.seconds_since_flush < self._config.telemetry_push_interval_seconds:
            return
        metrics = self._telemetry.flush()
        if not metrics or (len(metrics) == 1 and "timestamp" in metrics):
            return
        try:
            self._backend.post_metrics(self._config.site_id, metrics)
            self._state.last_metrics_flush = time.time()
        except Exception:
            # metrics will be refilled on next increment; losing one snapshot acceptable
            self._logger.debug("Metric flush skipped due to backend failure", exc_info=True)

    def _poll_remote_commands(self) -> None:
        try:
            raw_commands = self._backend.fetch_commands(self._config.site_id)
        except Exception as exc:
            self._logger.error("Failed to fetch commands: %s", exc)
            return
        commands = [ManagementCommand(name=item["command"], parameters=item.get("parameters", {})) for item in raw_commands]
        if not commands:
            return
        results = self._management.execute_commands(commands)
        for result in results:
            try:
                if "diagnostics" in result:
                    self._backend.post_diagnostics(self._config.site_id, result["diagnostics"])
                if "inventory" in result:
                    self._backend.post_inventory(self._config.site_id, result["inventory"])
            except Exception as exc:  # pragma: no cover - defensive logging
                self._logger.error("Failed to post command result: %s", exc)
        output_file = Path(self._config.data_directory) / "command-results.json"
        self._management.write_remote_command_result(results, output_file)
        self._logger.info("Executed %d remote commands", len(results))

    def _poll_updates_if_due(self) -> None:
        now = time.time()
        if now - self._state.last_update_poll < self._config.update_poll_interval_seconds:
            return
        self._state.last_update_poll = now
        manifest = self._backend.get_update_manifest(self._config.site_id)
        if not manifest:
            return
        if not self._update_manager.needs_update(manifest.version):
            return
        try:
            applied_version = self._update_manager.apply_update(manifest)
            self._telemetry.increment("updates_applied")
            self._logger.info("Applied update %s", applied_version)
        except Exception as exc:
            self._telemetry.increment("update_failures")
            self._logger.error("Update application failed: %s", exc)

    def close(self) -> None:
        self._cache.close()

    def run(self, cycles: int = 1) -> None:
        for _ in range(cycles):
            self.process_cycle()
            time.sleep(self._config.sync_interval_seconds)
