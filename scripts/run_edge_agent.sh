#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/etc/edge-agent/config.yaml"
LOG_DIR="/var/log/edge-agent"
DATA_DIR="/var/lib/edge-agent"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing configuration at $CONFIG_FILE" >&2
  exit 1
fi

python3 - <<'PYCODE'
from pathlib import Path

from edge_agent.agent import EdgeAgent
from edge_agent.backend import MockFleetBackend
from edge_agent.config import AgentConfig


def load_config(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data

config_path = Path("/etc/edge-agent/config.yaml")
config_data = load_config(config_path)
required = {"site_id", "backend_url", "secret_key"}
missing = [key for key in required if key not in config_data]
if missing:
    raise SystemExit(f"Missing required config values: {', '.join(missing)}")
cache_path = Path(config_data.get("cache_path", "/var/lib/edge-agent/cache.db"))
config = AgentConfig(
    site_id=config_data["site_id"],
    backend_url=config_data["backend_url"],
    secret_key=config_data["secret_key"],
    cache_path=cache_path,
    log_directory=Path(config_data.get("log_directory", "/var/log/edge-agent")),
    data_directory=Path(config_data.get("data_directory", "/var/lib/edge-agent")),
)
backend = MockFleetBackend()
agent = EdgeAgent(config=config, backend=backend)

print("Edge agent started. Press Ctrl+C to stop.")
try:
    agent.run(cycles=1000000)
except KeyboardInterrupt:
    pass
finally:
    agent.close()
PYCODE
