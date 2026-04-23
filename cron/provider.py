"""Scheduler provider selection and backend construction for Hermes cron jobs."""

import os
from collections.abc import Mapping
from typing import Any

from cron.backends import (
    BuiltinSchedulerBackend,
    FlyMachineSchedulerBackend,
    SchedulerBackend,
    SchedulerBackendConfig,
    SchedulerProviderError,
    SchedulerRemoteConfig,
)
from hermes_cli.config import load_config

DEFAULT_SCHEDULER_PROVIDER = "builtin"
REMOTE_SCHEDULER_PROVIDER = "fly_machine_scheduler"
SUPPORTED_SCHEDULER_PROVIDERS = frozenset({DEFAULT_SCHEDULER_PROVIDER, REMOTE_SCHEDULER_PROVIDER})


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SchedulerProviderError(f"Invalid Hermes config: '{path}' must be a mapping.")
    return value


def _load_root_config(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if config is None:
        config = load_config() or {}
    return _require_mapping(config, "config")


def _get_scheduler_config_mapping(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    root_cfg = _load_root_config(config)
    cron_cfg = _require_mapping(root_cfg.get("cron", {}), "cron")
    return _require_mapping(cron_cfg.get("scheduler", {}), "cron.scheduler")


def _get_env_override(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def get_scheduler_provider(config: Mapping[str, Any] | None = None) -> str:
    """Return the configured scheduler provider, defaulting to ``builtin``."""
    scheduler_cfg = _get_scheduler_config_mapping(config)

    provider = _get_env_override("HERMES_SCHEDULER_PROVIDER")
    if provider is None:
        provider = scheduler_cfg.get("provider", DEFAULT_SCHEDULER_PROVIDER)
    if provider is None:
        return DEFAULT_SCHEDULER_PROVIDER
    if not isinstance(provider, str):
        raise SchedulerProviderError("Invalid Hermes config: 'cron.scheduler.provider' must be a string.")

    normalized = provider.strip().lower()
    return normalized or DEFAULT_SCHEDULER_PROVIDER


def get_scheduler_backend_config(config: Mapping[str, Any] | None = None) -> SchedulerBackendConfig:
    scheduler_cfg = _get_scheduler_config_mapping(config)
    provider = get_scheduler_provider(config)
    remote_cfg = _require_mapping(scheduler_cfg.get("remote", {}), "cron.scheduler.remote")

    return SchedulerBackendConfig(
        provider=provider,
        remote=SchedulerRemoteConfig(
            base_url=_get_env_override("HERMES_REMOTE_SCHEDULER_BASE_URL")
            or str(remote_cfg.get("base_url") or "").strip()
            or None,
            api_token=_get_env_override("HERMES_REMOTE_SCHEDULER_API_TOKEN")
            or str(remote_cfg.get("api_token") or "").strip()
            or None,
            dispatch_token=_get_env_override("HERMES_SCHEDULER_DISPATCH_BEARER_TOKEN")
            or str(remote_cfg.get("dispatch_token") or "").strip()
            or None,
        ),
    )


def ensure_supported_scheduler_provider(config: Mapping[str, Any] | None = None) -> str:
    """Return the configured provider or raise a clear configuration error."""
    provider = get_scheduler_provider(config)
    if provider not in SUPPORTED_SCHEDULER_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_SCHEDULER_PROVIDERS))
        raise SchedulerProviderError(
            f"Unsupported cron scheduler provider '{provider}'. Supported providers: {supported}."
        )
    return provider


def build_scheduler_backend(config: Mapping[str, Any] | None = None) -> SchedulerBackend:
    provider = ensure_supported_scheduler_provider(config)
    backend_config = get_scheduler_backend_config(config)
    if provider == DEFAULT_SCHEDULER_PROVIDER:
        backend: SchedulerBackend = BuiltinSchedulerBackend(backend_config)
    elif provider == REMOTE_SCHEDULER_PROVIDER:
        backend = FlyMachineSchedulerBackend(backend_config)
    else:
        supported = ", ".join(sorted(SUPPORTED_SCHEDULER_PROVIDERS))
        raise SchedulerProviderError(
            f"Unsupported cron scheduler provider '{provider}'. Supported providers: {supported}."
        )
    backend.validate_configuration()
    return backend


def ensure_scheduler_backend_runtime(config: Mapping[str, Any] | None = None) -> SchedulerBackend:
    """Return the configured backend after verifying it can service cron operations now."""
    backend = build_scheduler_backend(config)
    backend.assert_runtime_ready()
    return backend
