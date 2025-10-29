from __future__ import annotations

import random
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from edge_agent.agent import EdgeAgent
from edge_agent.backend import MockFleetBackend
from edge_agent.config import AgentConfig


def _build_config(root: Path) -> AgentConfig:
    return AgentConfig(
        site_id="simulated-site",
        backend_url="https://backend.simulated",
        secret_key="simulation-secret",
        cache_path=root / "cache.db",
        log_directory=root / "logs",
        data_directory=root / "data",
        sync_interval_seconds=0,
        telemetry_push_interval_seconds=5,
        update_poll_interval_seconds=10,
        inventory_refresh_hours=0,
    )


def run_simulation(cycles: int = 10) -> None:
    backend = MockFleetBackend()
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        agent = EdgeAgent(config=_build_config(base), backend=backend)
        for cycle in range(cycles):
            if cycle == 2:
                backend.set_online(False)
            if cycle == 5:
                backend.set_online(True)
            payload = {
                "temperature": round(random.uniform(18.0, 24.0), 2),
                "humidity": round(random.uniform(30.0, 45.0), 1),
                "cycle": cycle,
            }
            agent.ingest_payload(payload)
            agent.process_cycle()
            time.sleep(0.1)
        agent.close()
    _report_results(backend)


def _report_results(backend: MockFleetBackend) -> None:
    print("=== Simulation Summary ===")
    print(f"Measurements delivered: {len(backend.received_batches)}")
    print(f"Inventory syncs: {len(backend.received_inventory)}")
    print(f"Diagnostics captured: {len(backend.received_diagnostics)}")
    print(f"Metrics pushed: {len(backend.received_metrics)}")


if __name__ == "__main__":
    run_simulation()
