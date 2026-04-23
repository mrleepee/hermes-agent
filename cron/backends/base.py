from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class SchedulerProviderError(RuntimeError):
    """Raised when scheduler provider configuration or runtime state is invalid."""


@dataclass(frozen=True)
class SchedulerRemoteConfig:
    base_url: str | None = None
    api_token: str | None = None
    dispatch_token: str | None = None


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

    def validate_configuration(self) -> None:
        """Validate static provider configuration."""

    def assert_runtime_ready(self) -> None:
        """Raise if this backend cannot yet service Hermes cron operations."""

