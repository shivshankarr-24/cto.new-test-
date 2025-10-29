from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class ManagementCommand:
    name: str
    parameters: Dict


class RemoteManagement:
    """Provides diagnostics, inventory, and log capture capabilities."""

    def __init__(self, log_directory: Path, diag_log_lines: int) -> None:
        self._log_directory = log_directory
        self._diag_log_lines = diag_log_lines

    def collect_inventory(self) -> Dict:
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
            "memory_mb": self._read_meminfo_mb(),
            "kernel_version": platform.release(),
            "timestamp": time.time(),
        }

    def _read_meminfo_mb(self) -> Optional[int]:
        meminfo = Path("/proc/meminfo")
        if not meminfo.exists():
            return None
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) // 1024
        return None

    def collect_diagnostics(self) -> Dict:
        return {
            "processes": self._list_processes(),
            "disk_usage": self._disk_usage(),
            "logs": self.capture_logs(limit=self._diag_log_lines),
            "timestamp": time.time(),
        }

    def execute_commands(self, commands: Iterable[ManagementCommand]) -> List[Dict]:
        results: List[Dict] = []
        for command in commands:
            handler = getattr(self, f"cmd_{command.name}", None)
            if handler is None:
                results.append({"command": command.name, "status": "unknown-command"})
                continue
            results.append(handler(**command.parameters))
        return results

    def cmd_capture_logs(self, limit: int = 200) -> Dict:
        return {"command": "capture_logs", "logs": self.capture_logs(limit=limit)}

    def cmd_run_diagnostic(self) -> Dict:
        return {"command": "run_diagnostic", "diagnostics": self.collect_diagnostics()}

    def cmd_fetch_inventory(self) -> Dict:
        return {"command": "fetch_inventory", "inventory": self.collect_inventory()}

    def capture_logs(self, limit: int = 200) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        if not self._log_directory.exists():
            return result
        for log_file in sorted(self._log_directory.glob("*.log")):
            result[log_file.name] = self._tail(log_file, limit)
        return result

    def _tail(self, log_file: Path, limit: int) -> List[str]:
        if limit <= 0:
            return []
        lines = log_file.read_text().splitlines()
        return lines[-limit:]

    def _disk_usage(self) -> Dict:
        try:
            stat = os.statvfs(str(self._log_directory))
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            return {"total_bytes": total, "free_bytes": free}
        except FileNotFoundError:
            return {"total_bytes": 0, "free_bytes": 0}

    def _list_processes(self) -> List[Dict]:
        try:
            raw = subprocess.check_output(["ps", "-eo", "pid,comm,%cpu,%mem"], text=True)  # noqa: S603, S607
        except Exception:
            return []
        lines = raw.strip().splitlines()[1:]
        processes = []
        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            processes.append(
                {
                    "pid": int(parts[0]),
                    "command": parts[1],
                    "cpu": float(parts[2]),
                    "memory": float(parts[3]),
                }
            )
        return processes

    def write_remote_command_result(self, results: List[Dict], destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(results, indent=2))
        return destination
