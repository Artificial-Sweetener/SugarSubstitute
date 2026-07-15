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

"""Test owner task-scope lifetime behavior."""

from __future__ import annotations

from typing import cast

import pytest

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
    TaskScope,
)
from tests.execution_testing import (
    ManualTaskHandle,
    QueuedTaskSubmitter,
)


def _request(request_id: int = 1) -> TaskRequest[str]:
    """Build one queued test request."""

    return TaskRequest(
        identity=TaskIdentity(request_id=request_id, domain="settings"),
        context=ExecutionContext(operation="load", reason="refresh", lane="settings"),
        work=lambda _token: "done",
    )


def test_task_scope_tracks_and_forgets_completed_handles() -> None:
    """Track pending work and remove handles after completion."""

    submitter = QueuedTaskSubmitter()
    scope = TaskScope(submitter=submitter, scope_id="settings")

    handle = cast(ManualTaskHandle[str], scope.submit(_request()))

    assert scope.has_pending_work() is True
    handle.complete_success("done")
    assert scope.has_pending_work() is False


def test_task_scope_close_cancels_active_handles() -> None:
    """Cancel submitted work when the owner closes."""

    submitter = QueuedTaskSubmitter()
    scope = TaskScope(submitter=submitter, scope_id="settings")
    handle = cast(ManualTaskHandle[str], scope.submit(_request()))

    scope.close(reason="owner_destroyed")

    assert scope.is_closed is True
    assert handle.outcome is not None
    assert handle.outcome.status == "cancelled"
    assert handle.outcome.cancellation_reason == "owner_destroyed"
    assert submitter.cancellations[0].is_cancelled is True


def test_task_scope_rejects_submit_after_close() -> None:
    """Prevent new work after owner lifetime ends."""

    scope = TaskScope(submitter=QueuedTaskSubmitter(), scope_id="settings")

    scope.close(reason="owner_destroyed")

    with pytest.raises(RuntimeError, match="closed"):
        scope.submit(_request())


def test_task_scope_cancel_all_leaves_scope_open() -> None:
    """Allow owners to cancel active work without closing."""

    submitter = QueuedTaskSubmitter()
    scope = TaskScope(submitter=submitter, scope_id="settings")
    handle = cast(ManualTaskHandle[str], scope.submit(_request()))

    scope.cancel_all(reason="route_changed")

    assert scope.is_closed is False
    assert handle.outcome is not None
    assert handle.outcome.status == "cancelled"
