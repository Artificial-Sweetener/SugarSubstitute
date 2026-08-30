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

"""Enforce Input-canvas policy ownership at presentation boundaries."""

from __future__ import annotations

from pathlib import Path


def test_input_canvas_view_does_not_own_tool_or_picker_policy() -> None:
    """Keep tool selection and picker authority outside the mounted canvas view."""

    source = Path(
        "substitute/presentation/canvas/input/input_canvas_view.py"
    ).read_text()
    for forbidden in (
        "setControlMode",
        "CONTROL_MODE_DRAW_BRUSH",
        "CONTROL_MODE_SMART_SELECT",
        "CONTROL_MODE_PANZOOM",
        "maskManager",
        "get_masks_for_image",
        "refresh_mask_picker",
        "current_file_path",
        "_current_file_path",
        "request_brush_mode",
    ):
        assert forbidden not in source


def test_workspace_fallbacks_do_not_own_input_canvas_policy() -> None:
    """Keep Input picker policy on its presenter and controller paths."""

    controller_source = Path(
        "substitute/presentation/shell/workspace_controller.py"
    ).read_text()
    actions_source = Path(
        "substitute/presentation/shell/workspace_canvas_actions.py"
    ).read_text()
    for forbidden in (
        "_canvas_actions.on_input_image_changed",
        "_canvas_actions.on_input_canvas_image_loaded",
        "_canvas_actions.on_input_image_clicked",
        "_canvas_actions.refresh_active_mask_pickers",
        "_canvas_actions.on_input_mask_changed",
        "_canvas_actions.on_input_mask_clicked",
        "_canvas_actions.on_mask_save_completed",
        "_canvas_actions.materialize_loaded_cube_input_canvas",
        "_canvas_actions.reconcile_active_input_canvas_image",
    ):
        assert forbidden not in controller_source
    for forbidden in (
        "def on_input_image_changed",
        "def on_input_canvas_image_loaded",
        "def reconcile_active_input_canvas_image",
        "def on_input_image_clicked",
        "def refresh_active_mask_pickers",
        "def on_input_mask_changed",
        "def on_input_mask_clicked",
        "def on_mask_save_completed",
        "def materialize_loaded_cube_input_canvas",
        "request_brush_mode",
    ):
        assert forbidden not in actions_source
