# Edge Deployment Playbook

This playbook guides field engineers through provisioning, deploying, and maintaining edge compute clusters.

## 1. Pre-Deployment Checklist

- ✅ Site survey completed and rack/power requirements validated.
- ✅ Hardware inventory reconciled with bill of materials.
- ✅ Network connectivity verified (management + data VLANs).
- ✅ VPN credentials for remote access provisioned.
- ✅ Spare parts kit available on-site.

## 2. Bare-Metal Provisioning

1. **Power and Cabling**
   - Install redundant PDUs and connect dual power supplies per node.
   - Connect management NICs to the secure management switch, data NICs to production switch.
2. **Bootstrapping**
   - Attach USB with iPXE bootloader or enable ISO virtual media via BMC.
   - Boot nodes into the provisioning environment and select the appropriate profile (Tier 1/2/3).
3. **Automated Install**
   - PXE workflow applies Ubuntu Server LTS image, partitions disks, and configures RAID.
   - Ansible playbook `playbooks/os-baseline.yaml` hardens the OS and enrolls the node with TPM-backed identity.
4. **Verification**
   - Run acceptance script `scripts/bootstrap_edge_node.sh --validate` on each node.
   - Confirm fleet backend enrollment via the NOC dashboard.

## 3. Kubernetes Stack Installation (K3s)

1. **Primary Node**
   - Execute `scripts/deploy_edge_stack.sh --role=primary` to install K3s server components.
   - Verify control-plane readiness: `kubectl get nodes` (expect status `Ready`).
2. **Secondary Nodes**
   - Join with `scripts/deploy_edge_stack.sh --role=secondary --token <cluster-token> --server <primary-ip>`.
   - Validate etcd member health: `kubectl get endpoints kube-system/traefik`.
3. **Workload Namespaces**
   - Run `kubectl apply -f manifests/namespaces.yaml` to create tenant namespaces.
   - Deploy Longhorn and monitoring stack via Helm.

## 4. Edge Agent Deployment

1. **Containerized Deployment**
   - Build agent image: `docker build -t registry.example.com/edge/agent:$(git rev-parse --short HEAD) .`
   - Push to registry and update Helm values `manifests/edge-agent/values.yaml` with new tag.
   - Deploy as a DaemonSet: `helm upgrade --install edge-agent manifests/edge-agent`.
2. **Bare-Metal Deployment (Tier 3)**
   - Install dependencies: `scripts/bootstrap_edge_node.sh --agent-only`.
   - Configure `/etc/edge-agent/config.yaml` with site credentials.
   - Enable service: `systemctl enable --now edge-agent`.

## 5. Remote Management Enablement

- Ensure WireGuard tunnel established to fleet backend.
- Register node inventory: `edgectl register --site <site-id>`.
- Validate remote diagnostics by retrieving logs: `edgectl logs --site <site-id> --tail 100`.

## 6. Resilience Validation

1. **Intermittent Connectivity Test**
   - Simulate outage: disconnect data uplink for 10 minutes.
   - Confirm edge agent continues to buffer data (`edgectl status`).
   - Reconnect uplink and verify synchronization completes without loss.
2. **Update Rollout Simulation**
   - Push staged update via backend UI.
   - Monitor agent applying update (`journalctl -u edge-agent -f`).
3. **Failover Drill**
   - Power down one node; ensure workloads reschedule to remaining nodes within 120 seconds.

## 7. Monitoring and Alerting

- Integrate Prometheus with fleet backend using `prometheus-remote-write`.
- Configure alert rules: connectivity loss, update failure, cache pressure > 80%.
- Use Grafana dashboard `Edge Health Overview` for visualization.

## 8. Ongoing Maintenance

- Patch cadence: apply OS security updates monthly via Ansible automation.
- Perform quarterly hardware health checks (SMART, PSU, fan diagnostics).
- Rotate secrets (WireGuard keys, API tokens) every 180 days.
- Review logs weekly for anomalies, escalate per incident response plan.

## 9. Incident Response

- Severity 1 incidents require response within 15 minutes.
- Use remote KVM via BMC for recovery actions.
- If automated remediation fails, dispatch on-site technician with pre-approved RMA procedure.

## 10. Documentation and Handover

- Update CMDB with final deployment state.
- Store signed deployment checklist and validation results in ticketing system.
- Provide customer handover briefing covering support contacts and escalation paths.
