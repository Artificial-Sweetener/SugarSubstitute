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

"""Apply shared presentation cleanup after durable cube removal."""

from __future__ import annotations


def clear_cube_runtime_issues(
    view: object,
    workflow_id: str,
    cube_alias: str,
) -> None:
    """Clear runtime issue state for a removed cube when available."""

    issue_state = getattr(view, "workflow_issue_state", None)
    clear_cube_issues = getattr(issue_state, "clear_cube_issues", None)
    if callable(clear_cube_issues):
        clear_cube_issues(workflow_id, cube_alias)


def remove_editor_cube_section(view: object, cube_alias: str) -> None:
    """Remove a cube from the active editor when that surface exists."""

    active_panel = getattr(view, "active_editor_panel", None)
    remove_cube = getattr(active_panel, "remove_cube", None)
    if callable(remove_cube):
        remove_cube(cube_alias)


__all__ = ["clear_cube_runtime_issues", "remove_editor_cube_section"]
