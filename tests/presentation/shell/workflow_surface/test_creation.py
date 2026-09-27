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

"""Verify new workflow tabs register usable state and shell surfaces."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces

from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _CubeStack,
    _Manager,
    _deletable,
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _build_view,
)


def test_new_workflow_detaches_old_controls_and_opens_usable_tab() -> None:
    """Creating a tab should activate its workflow and mount editor and cube stack."""

    view = _build_view(active_workflow_id="wf-a")

    def create_workflow_ui(
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Build the workflow surfaces observed by route projection."""

        cube_stack = _CubeStack(f"{workflow_id}:cube", view.calls)
        editor = _deletable(f"{workflow_id}:editor", view.calls)
        view.cube_stacks[workflow_id] = cube_stack
        view.editor_panels[workflow_id] = editor
        view.override_managers[workflow_id] = _Manager(workflow_id, view.calls)
        view.calls.append(f"create:{workflow_id}:{set_as_current}")
        return WorkflowUiSurfaces(cube_stack, editor, True)

    view.workflow_ui_factory = SimpleNamespace(create_workflow_ui=create_workflow_ui)

    workflow_id = _import_module().WorkflowWorkspaceCoordinator(view).add_workflow()

    assert workflow_id not in {"wf-a", "wf-b"}
    assert view.workflow_session_service.active_workflow_id == workflow_id
    assert (
        view.workflow_tabbar.itemMap[workflow_id].text().startswith("Untitled Workflow")
    )
    assert view.workflow_session_service.workflows[workflow_id].stack_order == []
    assert workflow_id in view.cube_stacks
    assert workflow_id in view.editor_panels
    assert view.calls.index("wf-a:detach") < view.calls.index(
        f"create:{workflow_id}:True"
    )
