# Edge Deployment Reference Implementation

This repository defines a reference implementation for resilient edge compute deployments. It includes:

- A Python-based edge agent capable of operating during connectivity outages, synchronizing buffered data, applying secure updates, and executing remote diagnostics.
- Deployment tooling and reference documentation for hardware, operating system baselines, and field playbooks.
- Simulation harnesses and automated tests validating offline resilience and remote management workflows.

## Project Layout

```
.
├── docs/                          # Architecture, deployment, and validation documentation
├── edge_agent/                    # Edge agent Python package
├── scripts/                       # Bootstrap and deployment automation scripts
├── simulation/                    # Offline/online scenario simulator
├── tests/                         # Automated tests for agent behaviors
└── README.md                      # You are here
```

## Getting Started

1. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   > Note: The agent only depends on Python's standard library for core functionality. Requirements are optional for tooling such as `pytest`.

2. **Run the simulation harness**
   ```bash
   python simulation/run_edge_simulation.py
   ```

3. **Execute the unit tests**
   ```bash
   pytest
   ```

## Configuration

The runtime configuration file `/etc/edge-agent/config.yaml` uses simple `key: value` pairs. Minimum keys:

```yaml
site_id: alpha-site-001
backend_url: https://fleet.example.com
secret_key: super-secret
cache_path: /var/lib/edge-agent/cache.db
log_directory: /var/log/edge-agent
data_directory: /var/lib/edge-agent
```

## Edge Agent Overview

The edge agent coordinates:

- **Connectivity management**: `ConnectivityMonitor` detects backend availability and transitions between online/offline modes.
- **Durable caching**: `OfflineCache` (SQLite-backed) preserves payloads until acknowledgement, with automatic trimming to enforce storage limits.
- **Secure updates**: `UpdateManager` validates HMAC-signed manifests and applies artifacts via pluggable fetch/install callbacks.
- **Remote management**: `RemoteManagement` executes fleet commands for inventory, diagnostics, and log capture, storing results locally and emitting telemetry.
- **Telemetry**: `TelemetryBuffer` tracks metrics which are periodically pushed to the fleet backend.

## Deployment Scripts

- `scripts/bootstrap_edge_node.sh`: Validates hardware prerequisites, installs baseline packages, and configures the agent service.
- `scripts/deploy_edge_stack.sh`: Installs K3s and optional cluster services for primary and secondary nodes.
- `scripts/run_edge_agent.sh`: Convenience launcher for bare-metal agent deployments.

## Documentation

- `docs/hardware-reference-architecture.md`: Hardware and OS baseline.
- `docs/deployment-playbook.md`: Step-by-step deployment and operations guide.
- `docs/edge-test-report.md`: Summary of validation scenarios and outcomes.

## Support & Next Steps

- Integrate agent metrics with the central fleet backend's Prometheus endpoint.
- Extend `simulation/run_edge_simulation.py` with additional fault injection (process restarts, cache saturation).
- Prepare Ansible playbooks referenced in the deployment guide for production rollout.
