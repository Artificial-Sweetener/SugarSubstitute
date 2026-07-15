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

"""Tests for reconfigure flow entry from the live shell."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.workspace_controller import WorkspaceController


def test_workspace_controller_routes_reconfigure_request_to_view() -> None:
    """Shell reconfigure action should open the shared onboarding surface."""

    calls: list[str] = []
    view = SimpleNamespace(
        request_reconfigure=lambda: calls.append("open"),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        workspace_generation_controller=SimpleNamespace(
            handle_generate_clicked=lambda **_kwargs: None,
            interrupt_generation=lambda: SimpleNamespace(status="sent"),
        ),
        _current_generate_mode="generate",
        get_active_workflow=lambda: {},
        input_canvas_shell_adapter=SimpleNamespace(
            resolve_workflow_name=lambda _workflow_id: "Recipe"
        ),
        _randomize_active_seed_boxes=lambda: None,
        _clear_output_for_workflow=lambda _workflow_id: None,
        _on_generation_progress=lambda _progress: None,
        _on_generation_preview=lambda _preview: None,
        _on_generation_output_image=lambda _output: None,
        _on_generation_failure=lambda _failure: None,
        _log_interrupt_failure=lambda _result: None,
        cube_stacks={},
        editor_panels={},
        cube_load_service=SimpleNamespace(),
        cube_stack_service=SimpleNamespace(),
        refresh_active_workflow_surface=lambda: None,
        prepare_node_behavior_runtime=lambda *_args: None,
        canvas_tabs=SimpleNamespace(canvas_map={}),
        canvas_io_service=SimpleNamespace(),
        workflow_input_canvas_service=SimpleNamespace(),
        add_output_image_signal=SimpleNamespace(emit=lambda *_args: None),
        path_bundle=SimpleNamespace(projects_dir=".", cubes_dir="."),
        active_editor_panel=None,
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0, tabText=lambda _idx: ""
        ),
        active_override_manager=None,
        recipe_io_service=SimpleNamespace(),
        workflow_export_service=SimpleNamespace(),
        _pending_cubes={},
        active_cube_stack=None,
    )
    controller = WorkspaceController(view)

    controller.on_reconfigure_clicked()

    assert calls == ["open"]
