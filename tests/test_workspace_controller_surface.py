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

"""Static surface guardrails for WorkspaceController ownership boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)

REMOVED_PASS_THROUGH_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "prompt scene enqueue",
        ("def enqueue_prompt_scene(",),
    ),
    (
        "file actions",
        (
            "def on_save_clicked(",
            "def on_save_as_clicked(",
            "def on_export_comfy_workflow_clicked(",
            "def on_load_clicked(",
            "def load_recipe_document(",
        ),
    ),
    (
        "workflow lifecycle",
        (
            "def _apply_workflow_rename(",
            "def on_workflow_tab_inline_renamed(",
            "def on_add_workflow_tab_requested(",
            "def on_workflow_tab_close_requested_by_id(",
            "def on_reopen_closed_workflow_requested(",
            "def on_workflow_tab_close_requested(",
            "def on_workflow_selected(",
        ),
    ),
    (
        "search actions",
        (
            "def on_context_search_changed(",
            "def on_search_closed(",
            "def on_cycle_search_match(",
            "def on_cycle_search_match_backward(",
            "def proxy_override_menu_toggled(",
        ),
    ),
    (
        "cube actions",
        (
            "def on_tab_mouse_released(",
            "def on_cube_rename_requested(",
            "def on_cube_rename_edit_requested(",
            "def on_cube_rename_edit_finished(",
            "def on_cube_stack_compact_mode_manually_requested(",
            "def on_cube_move_finished(",
            "def on_cube_close_requested(",
            "def on_cube_bypass_toggle_requested(",
            "def show_cube_picker(",
            "def highlight_tab_for_cube(",
            "def prepare_node_behavior_runtime(",
        ),
    ),
    (
        "canvas actions",
        (
            "def on_active_output_changed(",
            "def on_active_output_grid_changed(",
            "def on_active_output_scene_changed(",
            "def on_output_compare_changed(",
            "def display_preview_image(",
            "def clear_output_previews(",
            "def open_image_in_external_editor(",
            "def open_images_in_external_editor(",
            "def handle_add_output_image(",
            "def commit_prepared_output_image(",
            "def handle_output_image_preparation_failed(",
            "def update_canvas_callback(",
        ),
    ),
    (
        "generation results",
        ("def open_generation_job_as_workflow(",),
    ),
    (
        "generation actions",
        (
            "def on_generate_clicked(",
            "def on_interrupt_clicked(",
            "def on_skip_generation_clicked(",
            "def on_stop_generation_clicked(",
        ),
    ),
    (
        "workflow duplication",
        ("def duplicate_workflow_tab(",),
    ),
)


@pytest.mark.parametrize(("concern", "forbidden_defs"), REMOVED_PASS_THROUGH_GROUPS)
def test_workspace_controller_does_not_reintroduce_extracted_pass_throughs(
    concern: str,
    forbidden_defs: tuple[str, ...],
) -> None:
    """WorkspaceController should keep extracted collaborator methods out."""

    source = WORKSPACE_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    present = [definition for definition in forbidden_defs if definition in source]

    assert present == [], concern
