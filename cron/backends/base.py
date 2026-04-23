from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class SchedulerProviderError(RuntimeError):
    """Raised when scheduler provider configuration or runtime state is invalid."""


class SchedulerRemoteError(RuntimeError):
    """Raised when Hermes cannot synchronize state with a remote scheduler."""


@dataclass(frozen=True)
class SchedulerMachineConfig:
    machine_id: str | None = None
    app_name: str | None = None
    region: str | None = None
    machine_name: str | None = None


@dataclass(frozen=True)
class SchedulerRemoteConfig:
    base_url: str | None = None
    api_token: str | None = None
    dispatch_token: str | None = None
    machine: SchedulerMachineConfig = field(default_factory=SchedulerMachineConfig)


@dataclass(frozen=True)
class SchedulerBackendConfig:
    provider: str
    remote: SchedulerRemoteConfig = field(default_factory=SchedulerRemoteConfig)


class SchedulerBackend(ABC):
    """Common contract for Hermes scheduler provider backends."""

    def __init__(self, config: SchedulerBackendConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    def uses_remote_timing(self) -> bool:
        return False

    def validate_configuration(self) -> None:
        """Validate static provider configuration."""

    def assert_runtime_ready(self) -> None:
        """Raise if this backend cannot yet service Hermes cron operations."""

    def register_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._sync_metadata(job["id"])

    def update_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._sync_metadata(job["id"])

    def pause_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._sync_metadata(job["id"])

    def resume_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._sync_metadata(job["id"])

    def trigger_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return self._sync_metadata(job["id"])

    def delete_job(self, job: dict[str, Any]) -> None:
        return None

    def acknowledge_occurrence(self, occurrence_id: str) -> None:
        return None

    def fail_occurrence(self, occurrence_id: str, reason: str) -> None:
        return None

    @staticmethod
    def _sync_metadata(job_id: str, error: str | None = None) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "last_sync_error": error,
        }
