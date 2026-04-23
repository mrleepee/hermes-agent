from __future__ import annotations

from .base import SchedulerBackend, SchedulerProviderError


class FlyMachineSchedulerBackend(SchedulerBackend):
    @property
    def provider_name(self) -> str:
        return "fly_machine_scheduler"

    def validate_configuration(self) -> None:
        if not self.config.remote.base_url:
            raise SchedulerProviderError(
                "Cron scheduler provider 'fly_machine_scheduler' requires 'cron.scheduler.remote.base_url' "
                "or HERMES_REMOTE_SCHEDULER_BASE_URL."
            )
        if not self.config.remote.api_token:
            raise SchedulerProviderError(
                "Cron scheduler provider 'fly_machine_scheduler' requires 'cron.scheduler.remote.api_token' "
                "or HERMES_REMOTE_SCHEDULER_API_TOKEN."
            )

    def assert_runtime_ready(self) -> None:
        self.validate_configuration()
        raise SchedulerProviderError(
            "Cron scheduler provider 'fly_machine_scheduler' is configured, but Hermes remote scheduler "
            "integration is not implemented in this phase yet."
        )

