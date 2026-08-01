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

"""Translate public CuteCanvas jobs into host-owned physical scheduling."""

from __future__ import annotations

from collections.abc import Callable

from cutecanvas import (
    BackendSubmission,
    DiagnosticsSubscription,
    ExecutionBackendCapabilities,
    ExecutionJob,
    ExecutionLeaseRelease,
    ExecutionRejected,
    ExecutionRejectionReason,
    ExecutionRequirements,
    ExecutionResource,
    ExecutionSnapshot,
    ExecutionUrgency,
)

from substitute.infrastructure.execution.host_execution_model import (
    HostExecutionJob,
    HostExecutionLeaseRelease,
    HostExecutionRequirements,
    HostExecutionResource,
    HostExecutionSnapshot,
)
from substitute.infrastructure.execution.host_execution_scheduler import (
    HostExecutionRejected,
    HostExecutionScheduler,
)

_RESOURCE_MAP = {
    ExecutionResource.BLOCKING_IO: HostExecutionResource.BLOCKING_IO,
    ExecutionResource.PYTHON_CPU: HostExecutionResource.PYTHON_CPU,
    ExecutionResource.NATIVE_CPU: HostExecutionResource.NATIVE_CPU,
    ExecutionResource.DEVICE: HostExecutionResource.DEVICE,
    ExecutionResource.THREAD_AFFINE_NATIVE: (
        HostExecutionResource.THREAD_AFFINE_NATIVE
    ),
}
_URGENCY_RANK = {
    ExecutionUrgency.INTERACTIVE: 0,
    ExecutionUrgency.FOREGROUND: 10,
    ExecutionUrgency.BACKGROUND: 20,
    ExecutionUrgency.OPPORTUNISTIC: 30,
    ExecutionUrgency.MAINTENANCE: 40,
}


class CuteCanvasExecutionBackend:
    """Adapt CuteCanvas lifecycle jobs without duplicating their ownership."""

    def __init__(
        self,
        scheduler: HostExecutionScheduler,
    ) -> None:
        """Bind public execution requirements to one host scheduler."""

        self._scheduler = scheduler
        self._capabilities = ExecutionBackendCapabilities(
            resources=frozenset(_RESOURCE_MAP),
            stable_affinity=True,
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
        """Admit one job without adding host task lifecycle semantics."""

        if not self.supports(job.requirements):
            raise ExecutionRejected(
                ExecutionRejectionReason.UNSUPPORTED_REQUIREMENTS,
                "CuteCanvas execution requirements exceed host lane capabilities",
            )
        requirements = job.requirements
        try:
            return self._scheduler.submit(
                HostExecutionJob(
                    task_id=job.task_id,
                    operation=job.operation,
                    requirements=HostExecutionRequirements(
                        resource=_RESOURCE_MAP[requirements.resource],
                        urgency_rank=_URGENCY_RANK[requirements.urgency],
                        resource_id=requirements.resource_id,
                        exclusive_key=requirements.exclusive_key,
                        affinity_key=requirements.affinity_key,
                        maximum_concurrency=requirements.maximum_concurrency,
                        lease_release=(
                            HostExecutionLeaseRelease.SETTLEMENT_FINISHED
                            if requirements.lease_release
                            is ExecutionLeaseRelease.ADOPTION_FINISHED
                            else HostExecutionLeaseRelease.WORK_FINISHED
                        ),
                        estimated_retained_bytes=(
                            requirements.estimated_retained_bytes or 0
                        ),
                    ),
                    run=job.run,
                    cancel_before_start=lambda reason: job.cancel_before_start(
                        reason=reason
                    ),
                    observe_settlement=job.add_settled_callback,
                )
            )
        except HostExecutionRejected as rejection:
            reason = (
                ExecutionRejectionReason.BACKEND_UNAVAILABLE
                if rejection.limit == "scheduler_closed"
                else ExecutionRejectionReason.SATURATED
            )
            raise ExecutionRejected(
                reason,
                "SugarSubstitute host execution rejected CuteCanvas work",
                details=(("limit", rejection.limit),),
            ) from rejection

    def execution_snapshot(self) -> ExecutionSnapshot:
        """Translate current host scheduler state for CuteCanvas diagnostics."""

        return _execution_snapshot(self._scheduler.snapshot())

    def subscribe_diagnostics(
        self,
        callback: Callable[[ExecutionSnapshot], None],
    ) -> DiagnosticsSubscription:
        """Publish coalesced host scheduler snapshots through CuteCanvas."""

        subscription = self._scheduler.subscribe_diagnostics(
            lambda snapshot: callback(_execution_snapshot(snapshot))
        )
        return DiagnosticsSubscription(subscription.close)

    def shutdown(self, *, wait: bool = False) -> None:
        """Release the adapter's host scheduler at process teardown."""

        self._scheduler.shutdown(wait=wait)


def _execution_snapshot(snapshot: HostExecutionSnapshot) -> ExecutionSnapshot:
    """Convert host-only diagnostics to the public CuteCanvas value."""

    return ExecutionSnapshot(
        accepted=snapshot.accepted,
        pending=snapshot.pending,
        running=snapshot.running,
        retained_bytes=snapshot.retained_bytes,
        rejected=snapshot.rejected,
        completed=snapshot.completed,
        cancelled_before_start=snapshot.cancelled_before_start,
    )


__all__ = ["CuteCanvasExecutionBackend"]
