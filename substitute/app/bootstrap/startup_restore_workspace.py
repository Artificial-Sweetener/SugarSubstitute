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

"""Read prompt-safe facts from optional restored workspace snapshots."""

from __future__ import annotations


def restored_workspace_workflow_count(workspace: object | None) -> int:
    """Return workflow count from an optional startup workspace snapshot."""

    workflows = getattr(workspace, "workflows", ()) if workspace is not None else ()
    return len(workflows) if isinstance(workflows, tuple) else 0


def restored_active_workflow_id(workspace: object | None) -> str:
    """Return the active workflow id from an optional restored workspace."""

    if workspace is None:
        return ""
    active_workflow_id = getattr(workspace, "active_workflow_id", "")
    return active_workflow_id if isinstance(active_workflow_id, str) else ""


def restored_active_workflow_cube_count(workspace: object | None) -> int:
    """Return cube count for the active restored workflow snapshot."""

    active_workflow_id = restored_active_workflow_id(workspace)
    workflows = getattr(workspace, "workflows", ()) if workspace is not None else ()
    if not active_workflow_id or not isinstance(workflows, tuple):
        return 0
    for workflow in workflows:
        if getattr(workflow, "workflow_id", "") != active_workflow_id:
            continue
        workflow_state = getattr(workflow, "workflow", None)
        cubes = getattr(workflow_state, "cubes", {})
        return len(cubes) if isinstance(cubes, dict) else 0
    return 0


__all__ = [
    "restored_active_workflow_cube_count",
    "restored_active_workflow_id",
    "restored_workspace_workflow_count",
]
