#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Adapt SugarSubstitute physical admission to CuteCanvas execution contracts."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from cutecanvas import (
    BackendSubmission,
    ExecutionBackendCapabilities,
    ExecutionJob,
    ExecutionRejected,
    ExecutionRejectionReason,
    ExecutionRequirements,
    ExecutionResource,
)

from substitute.infrastructure.execution.canvas_execution_scheduler import (
    CanvasExecutionPolicy,
    CanvasExecutionScheduler,
)
from substitute.infrastructure.execution.thread_pool_admission import (
    ThreadPoolAdmission,
)


class CuteCanvasExecutionBackend:
    """Schedule CuteCanvas jobs once on the host's selected physical lane."""

    def __init__(
        self,
        admissions: Mapping[ExecutionResource, ThreadPoolAdmission],
        *,
        policy: CanvasExecutionPolicy | None = None,
    ) -> None:
        """Bind CuteCanvas scheduling to host-owned resource-specific lanes."""

        self._scheduler = CanvasExecutionScheduler(admissions, policy=policy)
        self._capabilities = ExecutionBackendCapabilities(
            resources=self._scheduler.resources,
            exclusive_resources=True,
            adoption_held_leases=True,
        )

    @property
    def capabilities(self) -> ExecutionBackendCapabilities:
        """Return requirements honestly supported by the host lane."""

        return self._capabilities

    def supports(self, requirements: ExecutionRequirements) -> bool:
        """Return whether the lane can satisfy the typed CuteCanvas request."""

        return self._capabilities.supports(requirements)

    def submit(self, job: ExecutionJob) -> BackendSubmission:
        """Admit ``job.run`` without imposing Sugar task outcome semantics."""

        if not self.supports(job.requirements):
            raise ExecutionRejected(
                ExecutionRejectionReason.UNSUPPORTED_REQUIREMENTS,
                "CuteCanvas execution requirements exceed host lane capabilities",
            )
        self._scheduler.submit(job)
        return _CuteCanvasBackendSubmission(
            scheduler=self._scheduler,
            task_id=job.task_id,
        )

    def shutdown(self, *, wait: bool = False) -> None:
        """Cancel scheduler-pending work without closing host-owned lanes."""

        del wait
        self._scheduler.close()


class _CuteCanvasBackendSubmission:
    """Cancel a not-yet-started host-future and settle its CuteCanvas job."""

    def __init__(
        self,
        *,
        scheduler: CanvasExecutionScheduler,
        task_id: uuid.UUID,
    ) -> None:
        """Retain the scheduler identity for one accepted CuteCanvas job."""

        self._scheduler = scheduler
        self._task_id = task_id

    def cancel(self, *, reason: str) -> bool:
        """Cancel pending physical work and terminalize CuteCanvas before activation."""

        if not reason.strip():
            raise ValueError("cancellation reason must not be blank")
        return self._scheduler.cancel(self._task_id, reason=reason)


__all__ = ["CuteCanvasExecutionBackend"]
