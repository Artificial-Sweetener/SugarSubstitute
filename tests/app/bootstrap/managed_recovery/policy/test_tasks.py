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

"""Cover recovery task submission and outcome adaptation."""

from __future__ import annotations


from pathlib import Path


from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryOutcome,
    managed_compatibility_recovery_outcome_from_task,
    submit_managed_compatibility_recovery,
)


from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
)


from tests.support.execution import ManualTaskHandle


from substitute.application.backend_compatibility import (
    RuntimeCompatibilityStatus,
)


from .support import (
    _CleanupResult,
    _QueuedSubmitter,
    _compatibility,
    _target,
)


def test_managed_recovery_outcome_carries_compatibility_and_error() -> None:
    """Managed recovery outcomes should carry task success or failure state."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)
    error = RuntimeError("failed")

    success = ManagedCompatibilityRecoveryOutcome(compatibility)
    failure = ManagedCompatibilityRecoveryOutcome(compatibility, error=error)

    assert success.compatibility is compatibility
    assert success.error is None
    assert failure.compatibility is compatibility
    assert failure.error is error


def test_managed_recovery_submit_publishes_handle_outcome(tmp_path: Path) -> None:
    """Recovery submission should normalize and publish task outcomes."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)
    submitter = _QueuedSubmitter()
    published: list[ManagedCompatibilityRecoveryOutcome] = []

    def cleanup_state(_state: object | None) -> _CleanupResult:
        """Return a no-op cleanup result."""

        return _CleanupResult(
            managed_resource_present=False,
            termination_status=None,
            user_safe_detail="No cleanup.",
        )

    handle = submit_managed_compatibility_recovery(
        submitter=submitter,
        compatibility=compatibility,
        target=_target(tmp_path, launch_owned=True),
        state_to_recover=None,
        confirmed_termination_status=object(),
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=(
            lambda _target, _nodepacks, _emit_log: None
        ),
        emit_recovery_log=lambda _line: None,
        publish_outcome=published.append,
    )

    submitter.run_next()

    assert handle.is_finished
    assert published == [ManagedCompatibilityRecoveryOutcome(compatibility)]


def test_managed_recovery_handle_failure_normalizes_outcome() -> None:
    """Unexpected handle failures should still publish compatibility context."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)
    request: TaskRequest[ManagedCompatibilityRecoveryOutcome] = TaskRequest(
        identity=TaskIdentity(
            request_id=1,
            domain="managed_compatibility_recovery",
        ),
        context=ExecutionContext(
            operation="managed_compatibility_recovery",
            reason="test",
            lane="startup",
        ),
        work=lambda _token: ManagedCompatibilityRecoveryOutcome(compatibility),
    )
    handle: ManualTaskHandle[ManagedCompatibilityRecoveryOutcome] = ManualTaskHandle(
        request
    )
    error = RuntimeError("task crashed")
    handle.complete_failed(error)
    task_outcome = handle.outcome
    assert task_outcome is not None

    outcome = managed_compatibility_recovery_outcome_from_task(
        task_outcome,
        compatibility=compatibility,
    )

    assert outcome.compatibility is compatibility
    assert outcome.error is error
