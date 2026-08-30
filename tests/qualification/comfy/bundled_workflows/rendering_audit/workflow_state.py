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

"""Read direct-workflow state from the mounted production shell."""

from __future__ import annotations

from substitute.domain.comfy_workflow import DirectWorkflowState
from tests.qualification.comfy.bundled_workflows.direct_workflow_harness.shell import (
    DirectWorkflowShell,
)


def direct_workflow_state(
    shell: DirectWorkflowShell,
) -> DirectWorkflowState:
    """Return the direct document installed in production shell state."""

    workflow = shell.shell.workflow_session_service.get_workflow(
        shell.direct_workflow_id
    )
    direct = workflow.direct_workflow if workflow is not None else None
    if not isinstance(direct, DirectWorkflowState):
        raise AssertionError("direct workflow state is unavailable after loading")
    return direct
