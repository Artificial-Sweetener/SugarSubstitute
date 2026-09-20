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

"""Workflow inline-rename and progress-rekeying contracts."""

from __future__ import annotations


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _build_view,
)


def test_rejected_inline_rename_restores_old_label() -> None:
    """Rejected inline renames should restore the existing workflow label."""

    mod = _import_module()
    view = _build_view()

    mod.WorkflowWorkspaceCoordinator(view).rename_workflow("wf-a", "bad/name")

    assert view.workflow_tabbar.itemMap["wf-a"].text() == "wf-a"


def test_accepted_inline_rename_changes_label_without_rekeying_identity() -> None:
    """Accepted workflow renames must preserve every workflow-keyed owner."""

    mod = _import_module()
    view = _build_view()
    workflow = view.workflow_session_service.get_workflow("wf-a")
    assert workflow is not None
    workflow.metadata["asset_refs"] = {
        "input_masks": {
            "Cube:Mask": {
                "kind": "project_mask",
                "relative_path": "mask.png",
            }
        }
    }

    mod.WorkflowWorkspaceCoordinator(view).rename_workflow(
        "wf-a",
        "Renamed Workflow",
    )

    assert view.workflow_tabbar.itemMap["wf-a"].text() == "Renamed Workflow"
    assert view.workflow_session_service.active_workflow_id == "wf-a"
    assert set(view.workflow_session_service.workflows) == {"wf-a", "wf-b"}
    assert set(view.editor_panels) == {"wf-a", "wf-b"}
    assert set(view.cube_stacks) == {"wf-a", "wf-b"}
    assert not any(call.startswith("progress:rename:") for call in view.calls)
    assert (
        workflow.metadata["asset_refs"]["input_masks"]["Cube:Mask"]["storage_owner"]
        == "wf-a"
    )
