from __future__ import annotations

from typing import Any

from cron.remote_client import SchedulerRemoteClient

from .base import SchedulerBackend, SchedulerProviderError


class FlyMachineSchedulerBackend(SchedulerBackend):
    def __init__(self, config) -> None:
        super().__init__(config)
        self._client = SchedulerRemoteClient(
            base_url=self.config.remote.base_url or "",
            api_token=self.config.remote.api_token or "",
        )

    @property
    def provider_name(self) -> str:
        return "fly_machine_scheduler"

    @property
    def uses_remote_timing(self) -> bool:
        return True

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
        machine = self.config.remote.machine
        if not machine.machine_id or not machine.app_name or not machine.region:
            raise SchedulerProviderError(
                "Cron scheduler provider 'fly_machine_scheduler' requires machine identity via "
                "'cron.scheduler.remote.machine.machine_id', 'app_name', and 'region' "
                "or the FLY_MACHINE_ID, FLY_APP_NAME, and FLY_REGION environment variables."
            )

    def assert_runtime_ready(self) -> None:
        self.validate_configuration()

    def register_job(self, job: dict[str, Any]) -> dict[str, Any]:
        remote_job = self._client.register_job(self._job_payload(job))
        return self._sync_metadata(remote_job.get("job_id") or job["id"])

    def update_job(self, job: dict[str, Any]) -> dict[str, Any]:
        remote_job = self._client.update_job(job["id"], self._job_payload(job))
        return self._sync_metadata(remote_job.get("job_id") or job["id"])

    def pause_job(self, job: dict[str, Any]) -> dict[str, Any]:
        remote_job = self._client.pause_job(job["id"])
        return self._sync_metadata(remote_job.get("job_id") or job["id"])

    def resume_job(self, job: dict[str, Any]) -> dict[str, Any]:
        remote_job = self._client.resume_job(job["id"])
        return self._sync_metadata(remote_job.get("job_id") or job["id"])

    def trigger_job(self, job: dict[str, Any]) -> dict[str, Any]:
        remote_job = self._client.trigger_job(job["id"])
        return self._sync_metadata(remote_job.get("job_id") or job["id"])

    def delete_job(self, job: dict[str, Any]) -> None:
        self._client.delete_job(job["id"])

    def _job_payload(self, job: dict[str, Any]) -> dict[str, Any]:
        machine = self.config.remote.machine
        payload = {
            "job_id": job["id"],
            "task_payload": {
                "hermes_job_id": job["id"],
            },
            "schedule": self._render_schedule(job["schedule"]),
            "machine": {
                "machine_id": machine.machine_id,
                "app_name": machine.app_name,
                "region": machine.region,
            },
        }
        if machine.machine_name:
            payload["machine"]["machine_name"] = machine.machine_name
        return payload

    @staticmethod
    def _render_schedule(schedule: dict[str, Any]) -> str:
        kind = schedule.get("kind")
        if kind == "cron":
            return str(schedule["expr"])
        if kind == "interval":
            return f"every {int(schedule['minutes'])}m"
        if kind == "once":
            return str(schedule["run_at"])
        raise SchedulerProviderError(f"Unsupported Hermes schedule kind for remote sync: {kind!r}")
