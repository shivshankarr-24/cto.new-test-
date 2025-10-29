# Edge Hardware and OS Reference Architecture

## Overview

This document defines the reference architecture for customer edge sites delivering industrial telemetry and local analytics. The target deployment footprint supports a three-node micro-cluster to ensure high availability, with an optional single-node configuration for low criticality sites.

## Hardware Bill of Materials

| Component | Recommended Specification | Notes |
|-----------|---------------------------|-------|
| Compute   | 3 × x86_64 nodes, Intel Xeon D-1746NT or AMD EPYC 3151, 8 cores, 32 GB RAM | Hardware AES-NI required for encrypted workloads. |
| Storage   | 1 × 512 GB NVMe SSD (system), 1 × 1 TB NVMe SSD (data) per node | Use industrial-grade SSDs with PLP. RAID1 via mdadm for system volume. |
| Networking| Dual NIC: 1 × 1/2.5 GbE management, 1 × 10 GbE data | VLAN segmented management (out-of-band) and production data planes. |
| Out-of-Band Mgmt | BMC with Redfish/IPMI support | Mandatory for remote recovery. |
| Power     | Dual redundant PSUs per chassis, managed PDU | Power monitoring integrated with facility BMS. |
| Optional GPU | NVIDIA A2/T4 single-slot | Required for on-prem inference workloads. |

### Environmental Considerations

- Operating temperature: 0°C–50°C, fanless enclosures for dusty environments.
- All systems must withstand EN 300 019-1-3 Class 3.3 shock/vibration for light industrial use.

## Operating System Baseline

- **Distribution**: Ubuntu Server LTS (24.04) minimal image
- **Kernel**: Low-latency kernel flavour for jitter-sensitive workloads
- **Filesystem**: `ext4` with journaling, tune2fs configured for reduced write amplification
- **Security Baseline**:
  - Secure boot enabled
  - TPM 2.0 used for measured boot and key storage
  - Full disk encryption via LUKS2 with Tang fallback for unattended unlock
  - Mandatory access control via AppArmor profiles for edge agent and workload containers
- **Patch Management**: unattended-upgrades for security fixes, maintained apt mirror hosted centrally

## Container Runtime Stack

- **Container Runtime**: containerd 1.7.x
- **Orchestrator**: K3s (lightweight Kubernetes) with embedded etcd, configured for multi-master
- **Ingress**: Traefik (default in K3s) secured with Let’s Encrypt certificates issued by internal CA
- **Service Mesh (optional)**: Linkerd for mutual TLS between microservices when site-critical communications require zero-trust posture
- **Storage Provisioning**: Longhorn CSI for replicated block storage across nodes

## Edge Node Roles

| Role | Responsibilities |
|------|------------------|
| Control Plane Nodes | Host K3s server components, run cluster core services, expose management APIs. |
| Worker Nodes | Execute application workloads, edge agent daemonset, and data pipelines. |
| Witness Node (optional) | Lightweight node to provide quorum in dual-node deployments. |

## Networking Topology

- Management network (`mgmt0`): dedicated, routable subnet using TLS mutual authentication for backend access.
- Production network (`data0`): carries workload traffic, segregated via VLAN 20.
- Optional sensor network (`fieldbus0`): connected through gateway for OT data ingestion.
- Zero-trust overlay via WireGuard tunnels connecting edge nodes to cloud control plane.

## Sizing Guidance

### Tier 1 Sites (Mission Critical)
- Cluster: 3 control-plane capable nodes + 1 optional GPU worker
- Storage: 4 TB usable (Longhorn replicated factor 2)
- Workload headroom: 60% CPU, 70% memory reserved for failover

### Tier 2 Sites (Standard)
- Cluster: 2 nodes + witness VM (Intel NUC) for quorum
- Storage: 2 TB usable
- Workload headroom: 40% CPU, 50% memory reserved

### Tier 3 Sites (Satellite)
- Single node with RAID1 SSDs
- Edge agent runs directly on host OS with systemd supervision
- Container workloads limited to data ingestion and buffering

## Supportability

- Hardware vendor must provide 4-hour on-site parts replacement SLA for Tier 1/2.
- Out-of-band management network reachable via VPN with strict RBAC.
- BMC firmware locked to validated versions with quarterly security review.

## Monitoring and Telemetry

- Node metrics exported via Prometheus Node Exporter and scraped by fleet backend.
- Hardware events forwarded to central syslog using TLS.
- Power and thermal telemetry integrated with facility dashboards via Modbus TCP gateway.

## Compliance Considerations

- Edge hardware certified for IEC 62443-4-2 security requirements.
- Ensure FIPS 140-3 validated crypto modules when deploying to regulated industries.

## Lifecycle Management

1. Hardware arrival inspection and asset tagging.
2. Automated provisioning via PXE/iPXE and Ansible playbooks.
3. Execution of platform validation tests (CPU burn-in, storage SMART checks).
4. Final enrollment with fleet backend using TPM-backed device identity.
