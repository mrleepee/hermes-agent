"""Tests for cron/provider.py backend selection and config parsing."""

from cron.backends import BuiltinSchedulerBackend, FlyMachineSchedulerBackend
from cron.provider import (
    SchedulerProviderError,
    build_scheduler_backend,
    ensure_scheduler_backend_runtime,
    get_scheduler_backend_config,
    get_scheduler_provider,
)


class TestSchedulerProviderSelection:
    def test_defaults_to_builtin(self, monkeypatch):
        monkeypatch.delenv("HERMES_SCHEDULER_PROVIDER", raising=False)
        assert get_scheduler_provider({}) == "builtin"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("HERMES_SCHEDULER_PROVIDER", "fly_machine_scheduler")
        provider = get_scheduler_provider({"cron": {"scheduler": {"provider": "builtin"}}})
        assert provider == "fly_machine_scheduler"

    def test_non_mapping_scheduler_config_raises(self):
        try:
            get_scheduler_provider({"cron": {"scheduler": "builtin"}})
        except SchedulerProviderError as exc:
            assert "'cron.scheduler' must be a mapping" in str(exc)
        else:
            raise AssertionError("Expected SchedulerProviderError")


class TestSchedulerBackendConfig:
    def test_remote_backend_config_reads_nested_values(self, monkeypatch):
        monkeypatch.delenv("HERMES_REMOTE_SCHEDULER_BASE_URL", raising=False)
        monkeypatch.delenv("HERMES_REMOTE_SCHEDULER_API_TOKEN", raising=False)
        monkeypatch.delenv("HERMES_SCHEDULER_DISPATCH_BEARER_TOKEN", raising=False)
        backend_config = get_scheduler_backend_config(
            {
                "cron": {
                    "scheduler": {
                        "provider": "fly_machine_scheduler",
                        "remote": {
                            "base_url": "https://scheduler.internal",
                            "api_token": "api-token",
                            "dispatch_token": "dispatch-token",
                        },
                    }
                }
            }
        )
        assert backend_config.provider == "fly_machine_scheduler"
        assert backend_config.remote.base_url == "https://scheduler.internal"
        assert backend_config.remote.api_token == "api-token"
        assert backend_config.remote.dispatch_token == "dispatch-token"

    def test_remote_backend_env_overrides_take_precedence(self, monkeypatch):
        monkeypatch.setenv("HERMES_REMOTE_SCHEDULER_BASE_URL", "https://env.scheduler")
        monkeypatch.setenv("HERMES_REMOTE_SCHEDULER_API_TOKEN", "env-api-token")
        monkeypatch.setenv("HERMES_SCHEDULER_DISPATCH_BEARER_TOKEN", "env-dispatch-token")
        backend_config = get_scheduler_backend_config(
            {
                "cron": {
                    "scheduler": {
                        "provider": "fly_machine_scheduler",
                        "remote": {
                            "base_url": "https://config.scheduler",
                            "api_token": "config-api-token",
                            "dispatch_token": "config-dispatch-token",
                        },
                    }
                }
            }
        )
        assert backend_config.remote.base_url == "https://env.scheduler"
        assert backend_config.remote.api_token == "env-api-token"
        assert backend_config.remote.dispatch_token == "env-dispatch-token"


class TestSchedulerBackendFactory:
    def test_build_builtin_backend(self):
        backend = build_scheduler_backend({})
        assert isinstance(backend, BuiltinSchedulerBackend)

    def test_build_remote_backend_requires_base_url_and_api_token(self):
        try:
            build_scheduler_backend({"cron": {"scheduler": {"provider": "fly_machine_scheduler"}}})
        except SchedulerProviderError as exc:
            assert "requires 'cron.scheduler.remote.base_url'" in str(exc)
        else:
            raise AssertionError("Expected SchedulerProviderError")

    def test_build_remote_backend(self):
        backend = build_scheduler_backend(
            {
                "cron": {
                    "scheduler": {
                        "provider": "fly_machine_scheduler",
                        "remote": {
                            "base_url": "https://scheduler.internal",
                            "api_token": "api-token",
                        },
                    }
                }
            }
        )
        assert isinstance(backend, FlyMachineSchedulerBackend)

    def test_remote_backend_runtime_not_ready_yet(self):
        try:
            ensure_scheduler_backend_runtime(
                {
                    "cron": {
                        "scheduler": {
                            "provider": "fly_machine_scheduler",
                            "remote": {
                                "base_url": "https://scheduler.internal",
                                "api_token": "api-token",
                            },
                        }
                    }
                }
            )
        except SchedulerProviderError as exc:
            assert "not implemented in this phase yet" in str(exc)
        else:
            raise AssertionError("Expected SchedulerProviderError")
