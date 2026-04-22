"""Scheduler provider selection for Hermes scheduled jobs.

Phase 1 only supports the built-in provider. This module centralizes
provider lookup and validation so scheduled-job entry points can fail
clearly instead of silently falling back.
"""

from collections.abc import Mapping
from typing import Any

from hermes_cli.config import load_config

DEFAULT_SCHEDULER_PROVIDER = "builtin"
SUPPORTED_SCHEDULER_PROVIDERS = frozenset({DEFAULT_SCHEDULER_PROVIDER})


class SchedulerProviderError(RuntimeError):
    """Raised when scheduler provider configuration is invalid."""


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SchedulerProviderError(f"Invalid Hermes config: '{path}' must be a mapping.")
    return value


def get_scheduler_provider(config: Mapping[str, Any] | None = None) -> str:
    """Return the configured scheduler provider, defaulting to ``builtin``."""
    if config is None:
        config = load_config() or {}

    root_cfg = _require_mapping(config, "config")
    cron_cfg = _require_mapping(root_cfg.get("cron", {}), "cron")
    scheduler_cfg = _require_mapping(cron_cfg.get("scheduler", {}), "cron.scheduler")

    provider = scheduler_cfg.get("provider", DEFAULT_SCHEDULER_PROVIDER)
    if provider is None:
        return DEFAULT_SCHEDULER_PROVIDER
    if not isinstance(provider, str):
        raise SchedulerProviderError("Invalid Hermes config: 'cron.scheduler.provider' must be a string.")

    normalized = provider.strip().lower()
    return normalized or DEFAULT_SCHEDULER_PROVIDER


def ensure_supported_scheduler_provider(config: Mapping[str, Any] | None = None) -> str:
    """Return the configured provider or raise a clear configuration error."""
    provider = get_scheduler_provider(config)
    if provider not in SUPPORTED_SCHEDULER_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_SCHEDULER_PROVIDERS))
        raise SchedulerProviderError(
            f"Unsupported cron scheduler provider '{provider}'. Supported providers: {supported}."
        )
    return provider
