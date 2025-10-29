#!/usr/bin/env bash
set -euo pipefail

ROLE="full"
VALIDATE=false

usage() {
  cat <<EOF
Usage: $0 [--agent-only] [--validate]

Options:
  --agent-only   Install only edge agent dependencies (Tier 3 sites)
  --validate     Run post-install validation checks
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-only)
      ROLE="agent"
      shift
      ;;
    --validate)
      VALIDATE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ $(id -u) -ne 0 ]]; then
  echo "This script must be run as root" >&2
  exit 1
fi

apt-get update
apt-get install -y curl jq wireguard resolvconf containerd

if [[ "$ROLE" == "full" ]]; then
  apt-get install -y python3 python3-venv sqlite3
fi

mkdir -p /etc/edge-agent /var/lib/edge-agent /var/log/edge-agent

if ! id edge >/dev/null 2>&1; then
  useradd --system --home /var/lib/edge-agent --shell /usr/sbin/nologin edge
fi
chown -R edge:edge /var/lib/edge-agent /var/log/edge-agent

if [[ ! -f /etc/edge-agent/config.yaml ]]; then
  cat <<EOF >/etc/edge-agent/config.yaml
site_id: REPLACE_ME
backend_url: https://fleet.example.com
secret_key: change-me
cache_path: /var/lib/edge-agent/cache.db
EOF
fi

if command -v systemctl >/dev/null 2>&1; then
  cat <<'EOF' >/etc/systemd/system/edge-agent.service
[Unit]
Description=Edge Agent Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=edge
Group=edge
ExecStart=/usr/local/bin/edge-agent
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable edge-agent.service >/dev/null 2>&1 || true
fi

if $VALIDATE; then
  python3 - <<'PYCODE'
import os
required = ["/etc/edge-agent/config.yaml", "/var/lib/edge-agent", "/var/log/edge-agent"]
missing = [path for path in required if not os.path.exists(path)]
if missing:
    raise SystemExit(f"Validation failed. Missing: {', '.join(missing)}")
print("Validation successful")
PYCODE
fi
