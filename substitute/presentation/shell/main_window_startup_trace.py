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

"""Provide startup trace helpers for MainWindow orchestration."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any


def startup_phase(startup_timer: Any | None, name: str) -> Any:
    """Return a duck-typed startup timing context when instrumentation is present."""

    phase = getattr(startup_timer, "phase", None)
    return phase(name) if callable(phase) else nullcontext()


def mark_startup_milestone(startup_timer: Any | None, name: str) -> None:
    """Record a duck-typed startup milestone when instrumentation is present."""

    mark = getattr(startup_timer, "mark", None)
    if callable(mark):
        mark(name)


def snapshot_trace_fields(snapshot: object | None) -> dict[str, object]:
    """Return compact workspace snapshot details for startup trace records."""

    workflows = getattr(snapshot, "workflows", ()) if snapshot is not None else ()
    workflow_count = len(workflows) if isinstance(workflows, tuple) else 0
    active_workflow_id = getattr(snapshot, "active_workflow_id", "")
    active_route = getattr(snapshot, "active_route", "")
    shell_layout = getattr(snapshot, "shell_layout", None)
    return {
        "workspace_present": snapshot is not None,
        "workflow_count": workflow_count,
        "active_workflow_id": active_workflow_id,
        "active_route": active_route,
        "shell_layout_present": shell_layout is not None,
    }


def workflow_snapshot_trace_fields(snapshot: object | None) -> dict[str, object]:
    """Return compact workflow snapshot details for startup trace records."""

    workflow = getattr(snapshot, "workflow", None)
    cubes = getattr(workflow, "cubes", {})
    stack_order = getattr(workflow, "stack_order", ())
    return {
        "workflow_id": getattr(snapshot, "workflow_id", ""),
        "tab_label": getattr(snapshot, "tab_label", ""),
        "active_cube_alias": getattr(snapshot, "active_cube_alias", ""),
        "cube_count": len(cubes) if isinstance(cubes, dict) else 0,
        "stack_order_length": len(stack_order)
        if isinstance(stack_order, list | tuple)
        else 0,
        "input_image_count": len(getattr(snapshot, "input_images", ()) or ()),
        "input_mask_count": len(getattr(snapshot, "input_masks", ()) or ()),
        "output_image_count": len(getattr(snapshot, "output_images", ()) or ()),
    }


__all__ = [
    "mark_startup_milestone",
    "snapshot_trace_fields",
    "startup_phase",
    "workflow_snapshot_trace_fields",
]
