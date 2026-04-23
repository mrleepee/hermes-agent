"""Tests for remote scheduler dispatch execution and idempotency."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cron.dispatch_receipts import get_receipt
from cron.jobs import save_jobs
from cron.scheduler import process_remote_dispatch


class FakeRemoteBackend:
    provider_name = "fly_machine_scheduler"

    def __init__(self) -> None:
        self.acked: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def acknowledge_occurrence(self, occurrence_id: str) -> None:
        self.acked.append(occurrence_id)

    def fail_occurrence(self, occurrence_id: str, reason: str) -> None:
        self.failed.append((occurrence_id, reason))


@pytest.fixture()
def remote_dispatch_env(tmp_path, monkeypatch):
    cron_dir = tmp_path / "cron"
    monkeypatch.setattr("cron.jobs.CRON_DIR", cron_dir)
    monkeypatch.setattr("cron.jobs.JOBS_FILE", cron_dir / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", cron_dir / "output")
    monkeypatch.setattr("cron.dispatch_receipts.CRON_DIR", cron_dir)
    monkeypatch.setattr("cron.dispatch_receipts.RECEIPTS_FILE", cron_dir / "dispatch_receipts.json")
    monkeypatch.setattr("cron.jobs.ensure_scheduler_backend_runtime", lambda: None)
    return cron_dir


def _remote_job(*, state: str = "scheduled", enabled: bool = True) -> dict:
    now = datetime(2026, 4, 23, 9, 0, tzinfo=timezone.utc).isoformat()
    return {
        "id": "aabbccddeeff",
        "name": "Remote job",
        "prompt": "Summarize overnight activity",
        "skills": [],
        "skill": None,
        "schedule": {"kind": "interval", "minutes": 60},
        "schedule_display": "every 60m",
        "repeat": {"times": None, "completed": 0},
        "enabled": enabled,
        "state": state,
        "paused_at": None,
        "paused_reason": None,
        "created_at": now,
        "next_run_at": now,
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "deliver": "local",
        "origin": None,
        "scheduler_provider": "fly_machine_scheduler",
        "scheduler_remote": {
            "job_id": "aabbccddeeff",
            "last_synced_at": now,
            "last_sync_error": None,
        },
    }


def _payload() -> dict:
    return {
        "job": {"job_id": "aabbccddeeff"},
        "occurrence": {
            "occurrence_id": "occ_20260423T090000_aabbccddeeff",
            "job_id": "aabbccddeeff",
            "scheduled_for": "2026-04-23T09:00:00+00:00",
            "dispatch_status": "pending",
        },
    }


class TestRemoteDispatchExecution:
    def test_successful_dispatch_acknowledges_occurrence(self, remote_dispatch_env, monkeypatch):
        backend = FakeRemoteBackend()
        save_jobs([_remote_job()])
        monkeypatch.setattr("cron.scheduler.build_scheduler_backend_for_provider", lambda provider: backend)

        with patch("cron.scheduler.run_job", return_value=(True, "# output", "All good", None)), patch(
            "cron.scheduler.save_job_output", return_value="/tmp/out.md"
        ), patch("cron.scheduler._deliver_result", return_value=None) as deliver_mock, patch(
            "cron.scheduler.mark_job_run"
        ) as mark_mock:
            result = process_remote_dispatch(_payload(), run_async=False)

        assert result["state"] == "accepted"
        assert backend.acked == ["occ_20260423T090000_aabbccddeeff"]
        assert backend.failed == []
        assert get_receipt("occ_20260423T090000_aabbccddeeff")["state"] == "completed"
        deliver_mock.assert_called_once()
        mark_mock.assert_called_once_with("aabbccddeeff", True, None, delivery_error=None)

    def test_duplicate_completed_occurrence_is_suppressed(self, remote_dispatch_env, monkeypatch):
        backend = FakeRemoteBackend()
        save_jobs([_remote_job()])
        monkeypatch.setattr("cron.scheduler.build_scheduler_backend_for_provider", lambda provider: backend)
        run_job = MagicMock(return_value=(True, "# output", "All good", None))

        with patch("cron.scheduler.run_job", run_job), patch(
            "cron.scheduler.save_job_output", return_value="/tmp/out.md"
        ), patch("cron.scheduler._deliver_result", return_value=None), patch(
            "cron.scheduler.mark_job_run"
        ):
            first = process_remote_dispatch(_payload(), run_async=False)
            second = process_remote_dispatch(_payload(), run_async=False)

        assert first["state"] == "accepted"
        assert second["state"] == "duplicate_completed"
        assert run_job.call_count == 1

    def test_failed_dispatch_reports_failure(self, remote_dispatch_env, monkeypatch):
        backend = FakeRemoteBackend()
        save_jobs([_remote_job()])
        monkeypatch.setattr("cron.scheduler.build_scheduler_backend_for_provider", lambda provider: backend)

        with patch("cron.scheduler.run_job", return_value=(False, "# output", "", "some error")), patch(
            "cron.scheduler.save_job_output", return_value="/tmp/out.md"
        ), patch("cron.scheduler._deliver_result", return_value=None), patch(
            "cron.scheduler.mark_job_run"
        ) as mark_mock:
            result = process_remote_dispatch(_payload(), run_async=False)

        assert result["state"] == "accepted"
        assert backend.failed == [("occ_20260423T090000_aabbccddeeff", "some error")]
        assert get_receipt("occ_20260423T090000_aabbccddeeff")["state"] == "failed"
        mark_mock.assert_called_once_with("aabbccddeeff", False, "some error", delivery_error=None)

    def test_paused_job_is_rejected(self, remote_dispatch_env):
        save_jobs([_remote_job(state="paused", enabled=False)])

        result = process_remote_dispatch(_payload(), run_async=False)

        assert result["state"] == "rejected_paused"
        assert result["http_status"] == 409

    def test_unknown_job_is_rejected(self, remote_dispatch_env):
        result = process_remote_dispatch(_payload(), run_async=False)

        assert result["state"] == "rejected_unknown_job"
        assert result["http_status"] == 404

    def test_builtin_job_is_rejected_for_remote_dispatch(self, remote_dispatch_env):
        job = _remote_job()
        job["scheduler_provider"] = "builtin"
        job["scheduler_remote"] = None
        save_jobs([job])

        result = process_remote_dispatch(_payload(), run_async=False)

        assert result["state"] == "rejected_provider_mismatch"
        assert result["http_status"] == 409
