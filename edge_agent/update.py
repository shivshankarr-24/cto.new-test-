from __future__ import annotations

import hashlib
import hmac
import os
import pathlib
import shutil
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from .backend import UpdateManifest


class UpdateValidationError(Exception):
    """Raised when an update package fails validation."""


@dataclass
class UpdateState:
    current_version: str


class UpdateManager:
    """Coordinates secure delivery and application of software updates."""

    def __init__(
        self,
        secret_key: str,
        state: UpdateState,
        artifact_fetcher: Optional[Callable[[str, pathlib.Path], None]] = None,
        install_callback: Optional[Callable[[pathlib.Path], None]] = None,
    ) -> None:
        self._secret_key = secret_key.encode("utf-8")
        self._state = state
        self._artifact_fetcher = artifact_fetcher or self._default_fetcher
        self._install_callback = install_callback or self._default_install

    @property
    def current_version(self) -> str:
        return self._state.current_version

    def needs_update(self, version: str) -> bool:
        return version != self._state.current_version

    def validate_manifest(self, manifest: UpdateManifest) -> None:
        message = f"{manifest.version}:{manifest.artifact_url}:{manifest.timestamp}".encode("utf-8")
        signature = hmac.new(self._secret_key, message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, manifest.signature):
            raise UpdateValidationError("update signature validation failed")

    def apply_update(self, manifest: UpdateManifest) -> str:
        self.validate_manifest(manifest)
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = pathlib.Path(tmpdir) / "artifact"
            self._artifact_fetcher(manifest.artifact_url, download_path)
            self._install_callback(download_path)
        self._state.current_version = manifest.version
        return manifest.version

    @staticmethod
    def _default_fetcher(artifact_url: str, destination: pathlib.Path) -> None:  # noqa: ARG004 - url for real impl
        """Placeholder artifact fetcher that creates a mock artifact."""
        destination.write_text(f"artifact from {artifact_url}\n")

    @staticmethod
    def _default_install(artifact_path: pathlib.Path) -> None:
        target_dir = pathlib.Path("/var/lib/edge-agent/updates")
        target_dir.mkdir(parents=True, exist_ok=True)
        version_dir = target_dir / os.path.basename(artifact_path)
        shutil.copy(artifact_path, version_dir)
