#!/usr/bin/env bash
set -euo pipefail

ROLE="primary"
SERVER=""
TOKEN=""

usage() {
  cat <<EOF
Usage: $0 [--role=primary|secondary] [--server <url>] [--token <token>]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --role=*)
      ROLE="${1#*=}"
      shift
      ;;
    --role)
      ROLE="$2"
      shift 2
      ;;
    --server)
      SERVER="$2"
      shift 2
      ;;
    --token)
      TOKEN="$2"
      shift 2
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

INSTALL_K3S_EXEC=""

if [[ "$ROLE" == "primary" ]]; then
  INSTALL_K3S_EXEC="server --write-kubeconfig-mode 644 --disable traefik=false"
else
  if [[ -z "$SERVER" || -z "$TOKEN" ]]; then
    echo "Secondary nodes require --server and --token" >&2
    exit 1
  fi
  INSTALL_K3S_EXEC="agent --server ${SERVER} --token ${TOKEN}"
fi

curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="$INSTALL_K3S_EXEC" sh -

mkdir -p /etc/rancher/k3s
cat <<EOF >/etc/rancher/k3s/config.yaml
tls-san:
  - $(hostname -f)
write-kubeconfig-mode: "0644"
node-label:
  - site-role=${ROLE}
EOF

systemctl restart k3s || systemctl restart k3s-agent
