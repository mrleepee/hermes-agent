from __future__ import annotations

from .base import SchedulerBackend


class BuiltinSchedulerBackend(SchedulerBackend):
    @property
    def provider_name(self) -> str:
        return "builtin"

