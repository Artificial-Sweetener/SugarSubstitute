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

"""Tests for workflow session full-state replacement."""

from __future__ import annotations

import pytest

from substitute.application.workflows import WorkflowSessionService
from substitute.domain.workflow import WorkflowState


def test_workflow_session_service_replaces_workflows_for_restore() -> None:
    """Session service should accept trusted restored workflow maps."""

    first = WorkflowState(metadata={"name": "first"})
    second = WorkflowState(metadata={"name": "second"})
    service: WorkflowSessionService[WorkflowState] = WorkflowSessionService()

    service.replace_workflows(
        {"wf-1": first, "wf-2": second}, active_workflow_id="wf-2"
    )

    assert service.workflows == {"wf-1": first, "wf-2": second}
    assert service.active_workflow_id == "wf-2"
    assert service.get_active_workflow() is second


def test_workflow_session_service_rejects_missing_active_restore_id() -> None:
    """Restored active workflow id must exist when non-empty."""

    service: WorkflowSessionService[WorkflowState] = WorkflowSessionService()

    with pytest.raises(ValueError):
        service.replace_workflows({"wf-1": WorkflowState()}, active_workflow_id="wf-2")
