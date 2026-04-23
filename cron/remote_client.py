from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cron.backends.base import SchedulerRemoteError


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


@dataclass(frozen=True)
class SchedulerRemoteClient:
    base_url: str
    api_token: str
    timeout_seconds: float = 10.0

    def register_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", "/v1/jobs", payload).get("job") or {}

    def update_job(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        encoded_job_id = quote(job_id, safe="")
        return self._request_json("PUT", f"/v1/jobs/{encoded_job_id}", payload).get("job") or {}

    def pause_job(self, job_id: str) -> dict[str, Any]:
        encoded_job_id = quote(job_id, safe="")
        return self._request_json("POST", f"/v1/jobs/{encoded_job_id}/pause").get("job") or {}

    def resume_job(self, job_id: str) -> dict[str, Any]:
        encoded_job_id = quote(job_id, safe="")
        return self._request_json("POST", f"/v1/jobs/{encoded_job_id}/resume").get("job") or {}

    def trigger_job(self, job_id: str) -> dict[str, Any]:
        encoded_job_id = quote(job_id, safe="")
        return self._request_json("POST", f"/v1/jobs/{encoded_job_id}/trigger").get("job") or {}

    def delete_job(self, job_id: str) -> None:
        encoded_job_id = quote(job_id, safe="")
        self._request_json("DELETE", f"/v1/jobs/{encoded_job_id}")

    def acknowledge_occurrence(self, occurrence_id: str) -> dict[str, Any]:
        encoded_occurrence_id = quote(occurrence_id, safe="")
        return self._request_json("POST", f"/v1/occurrences/{encoded_occurrence_id}/ack").get("occurrence") or {}

    def fail_occurrence(self, occurrence_id: str, reason: str) -> dict[str, Any]:
        encoded_occurrence_id = quote(occurrence_id, safe="")
        return self._request_json(
            "POST",
            f"/v1/occurrences/{encoded_occurrence_id}/fail",
            {"reason": reason},
        ).get("occurrence") or {}

    def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = {"Authorization": f"Bearer {self.api_token}"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(_join_url(self.base_url, path), method=method, headers=headers, data=data)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8") or "{}"
                return json.loads(payload)
        except HTTPError as exc:
            try:
                payload = exc.read().decode("utf-8") or "{}"
                body_json = json.loads(payload)
                message = str(body_json.get("error") or f"{exc.code} {exc.reason}")
            except Exception:
                message = f"{exc.code} {exc.reason}"
            finally:
                exc.close()
            raise SchedulerRemoteError(f"Remote scheduler request failed: {message}") from exc
        except URLError as exc:
            raise SchedulerRemoteError(f"Remote scheduler request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SchedulerRemoteError("Remote scheduler request timed out.") from exc
        except json.JSONDecodeError as exc:
            raise SchedulerRemoteError("Remote scheduler returned invalid JSON.") from exc
