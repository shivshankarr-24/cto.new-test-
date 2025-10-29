from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the edge agent runtime."""

    site_id: str
    backend_url: str
    secret_key: str
    cache_path: Path
    sync_interval_seconds: int = 30
    max_batch_size: int = 100
    offline_cache_limit_bytes: int = 200 * 1024 * 1024  # 200 MB
    telemetry_push_interval_seconds: int = 60
    update_poll_interval_seconds: int = 300
    inventory_refresh_hours: int = 12
    diag_log_lines: int = 500
    hostname: Optional[str] = None
    log_directory: Path = field(default_factory=lambda: Path("/var/log/edge-agent"))
    data_directory: Path = field(default_factory=lambda: Path("/var/lib/edge-agent"))

    def ensure_directories(self) -> None:
        """Ensure required directories exist on disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.data_directory.mkdir(parents=True, exist_ok=True)
