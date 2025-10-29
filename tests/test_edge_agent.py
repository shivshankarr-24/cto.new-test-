from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from edge_agent.agent import EdgeAgent
from edge_agent.backend import MockFleetBackend, UpdateManifest
from edge_agent.config import AgentConfig
from edge_agent.update import UpdateState


def _build_config(base: Path, **overrides):
    params = dict(
        site_id="site-123",
        backend_url="https://backend.example.com",
        secret_key="super-secret",
        cache_path=base / "cache.db",
        log_directory=base / "logs",
        data_directory=base / "data",
        sync_interval_seconds=0,
        telemetry_push_interval_seconds=0,
        update_poll_interval_seconds=0,
        inventory_refresh_hours=0,
    )
    params.update(overrides)
    return AgentConfig(**params)


def test_agent_recovers_and_resyncs_after_outage():
    backend = MockFleetBackend()
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        config = _build_config(base)
        agent = EdgeAgent(config=config, backend=backend)
        backend.set_online(False)
        agent.ingest_payload({"temperature": 18.9})
        agent.process_cycle()
        assert backend.received_batches == []
        backend.set_online(True)
        agent.process_cycle()
        assert len(backend.received_batches) == 1
        payload = backend.received_batches[0]
        assert payload["payload"]["temperature"] == 18.9
        assert payload["site_id"] == "site-123"
        assert agent.state.events_cached == 0
        assert agent.state.events_sent == 1
        agent.close()


def test_secure_update_flow_validates_signature():
    backend = MockFleetBackend()
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        config = _build_config(base)
        agent = EdgeAgent(config=config, backend=backend, update_state=UpdateState(current_version="0.0.0"))
        timestamp = time.time()
        manifest = _manifest(secret=config.secret_key, version="1.0.0", timestamp=timestamp)
        backend.set_manifest(manifest)
        agent.process_cycle()
        assert agent.state.last_update_poll > 0
        assert agent.current_version == "1.0.0"
        assert any(metric.get("updates_applied") == 1 for metric in backend.received_metrics)
        agent.close()


def test_remote_management_executes_commands_and_stores_results(tmp_path):
    backend = MockFleetBackend()
    log_file = tmp_path / "logs" / "app.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text("line-1\nline-2\nline-3\n")
    config = _build_config(tmp_path, log_directory=tmp_path / "logs", data_directory=tmp_path / "data")
    agent = EdgeAgent(config=config, backend=backend)
    backend.queue_command({"command": "capture_logs", "parameters": {"limit": 2}})
    backend.queue_command({"command": "run_diagnostic", "parameters": {}})
    agent.process_cycle()
    results_file = config.data_directory / "command-results.json"
    assert results_file.exists()
    results = json.loads(results_file.read_text())
    commands = {entry["command"] for entry in results}
    assert "capture_logs" in commands
    capture_entry = next(entry for entry in results if entry["command"] == "capture_logs")
    assert "app.log" in capture_entry["logs"]
    assert len(capture_entry["logs"]["app.log"]) == 2
    assert backend.received_inventory
    assert backend.received_diagnostics
    agent.close()


def _manifest(secret: str, version: str, timestamp: float) -> UpdateManifest:
    artifact_url = f"https://cdn.example.com/{version}/artifact.tar.gz"
    payload = f"{version}:{artifact_url}:{timestamp}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return UpdateManifest(version=version, artifact_url=artifact_url, signature=signature, timestamp=timestamp)
