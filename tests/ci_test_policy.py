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

"""Own CI test execution and platform-applicability policy."""

from __future__ import annotations

import sys
from enum import StrEnum


class CiPlatform(StrEnum):
    """Identify one operating system supported by the application test suite."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


MAX_PARALLEL_TEST_WORKERS = 4


PLATFORM_TEST_MODULES = {
    "tests/test_spellcheck_infrastructure.py": frozenset({CiPlatform.WINDOWS}),
}


SERIAL_TEST_MODULES = frozenset(
    {
        "tests/test_about_settings_page.py",
        "tests/test_app_orb_action_cluster.py",
        "tests/test_app_orb_menu.py",
        "tests/test_app_orb_renderer.py",
        "tests/test_canvas_tab_manager_contract.py",
        "tests/test_canvas_zoom_indicator.py",
        "tests/test_comfy_output_panel_contract.py",
        "tests/test_cube_staging_stack.py",
        "tests/test_danbooru_wiki_dialog.py",
        "tests/test_danbooru_wiki_inline_flow.py",
        "tests/test_dimension_row_context_menu.py",
        "tests/test_editor_wheel_intent_integration.py",
        "tests/test_execution_inventory_guardrails.py",
        "tests/test_generation_queue_presentation.py",
        # Registry controls own native titlebar widgets that can terminate xdist.
        "tests/test_generation_titlebar_control_registry.py",
        "tests/test_license_dialog.py",
        # Installer payload replacement is not reliable under xdist handle contention.
        "tests/test_launcher_first_run_install.py",
        # Real launcher-shell construction can terminate an xdist Qt worker.
        "tests/test_launcher_skeleton.py",
        "tests/test_managed_text_asset_modal.py",
        "tests/test_managed_text_asset_wheel_intent.py",
        "tests/test_media_wall.py",
        "tests/test_menu_button_toggle_contract.py",
        "tests/test_model_picker_field.py",
        "tests/test_model_picker_popup.py",
        "tests/test_node_cards_additional_contract.py",
        "tests/test_node_title_preset_actions.py",
        "tests/test_numbered_prompt_editor_frame.py",
        "tests/test_onboarding_automation_scenarios.py",
        "tests/test_onboarding_controller_contract.py",
        "tests/test_onboarding_terminal_contract.py",
        "tests/test_onboarding_window_contract.py",
        "tests/test_output_canvas_floating_grid_reflow.py",
        "tests/test_pending_restart_toolbar_button.py",
        "tests/test_prompt_autocomplete_surface_contract.py",
        "tests/test_prompt_card_mode_contract.py",
        # Prompt menu presentation constructs QFluent menu state unsafe in xdist.
        "tests/test_prompt_context_menu_request_presenter.py",
        # Dialog execution owns a real Qt event loop that can terminate an xdist worker.
        "tests/test_prompt_danbooru_dialog_runner.py",
        "tests/test_prompt_editor_context_menu_contract.py",
        "tests/test_prompt_editor_debounce.py",
        "tests/test_prompt_editor_main_thread_dispatcher.py",
        "tests/test_prompt_editor_phase1_characterization.py",
        "tests/test_prompt_editor_phase2_characterization.py",
        "tests/test_prompt_editor_phase3_characterization.py",
        "tests/test_prompt_editor_phase4_characterization.py",
        "tests/test_prompt_editor_phase5_characterization.py",
        "tests/test_prompt_editor_reorder_keyboard_integration.py",
        "tests/test_prompt_editor_sizing_contract.py",
        "tests/test_prompt_editor_visual_parity_contract.py",
        "tests/test_prompt_emphasis_overlay_contract.py",
        "tests/test_prompt_lora_picker_popup.py",
        "tests/test_prompt_projection_autocomplete_preview.py",
        "tests/test_prompt_projection_caret_navigation.py",
        "tests/test_prompt_projection_diagnostics.py",
        "tests/test_prompt_projection_display_mode_contract.py",
        "tests/test_prompt_projection_emphasis_surface.py",
        "tests/test_prompt_projection_fill_bands.py",
        "tests/test_prompt_projection_geometry_authority.py",
        "tests/test_prompt_projection_incremental_caret_map_contract.py",
        "tests/test_prompt_projection_incremental_editing.py",
        # Input-method events exercise native Qt composition state.
        "tests/test_prompt_projection_input_method.py",
        "tests/test_prompt_projection_layout_surface.py",
        "tests/test_prompt_projection_literal_normalization.py",
        "tests/test_prompt_projection_lora_surface.py",
        # Paint-cache tests construct Qt text layouts that are not xdist-safe.
        "tests/test_prompt_projection_paint_cache.py",
        "tests/test_prompt_projection_reorder_surface.py",
        "tests/test_prompt_projection_selection_contract.py",
        "tests/test_prompt_projection_surface_lifecycle.py",
        "tests/test_prompt_projection_token_editing_contract.py",
        "tests/test_prompt_projection_undo.py",
        "tests/test_prompt_projection_update_scheduler.py",
        # Token geometry creates native Qt text layouts that can terminate xdist.
        "tests/test_prompt_token_weight_geometry.py",
        "tests/test_prompt_reorder_animation.py",
        "tests/test_prompt_reorder_performance_counters.py",
        "tests/test_prompt_segment_reorder_overlay_contract.py",
        "tests/test_prompt_wildcard_overlay_contract.py",
        # QFluent menu construction can terminate an xdist Qt worker.
        "tests/test_qfluent_menu_renderer.py",
        # QFluent's process-global font/QSS refresh can terminate an xdist worker.
        "tests/test_qfluent_font_adapter.py",
        # Real Output QPane interaction owns native scene and popup state.
        "tests/test_real_shell_output_canvas_abuse_matrix.py",
        "tests/test_real_shell_output_canvas_scenarios.py",
        "tests/test_real_shell_prompt_editor_autocomplete_scenarios.py",
        "tests/test_real_shell_prompt_editor_harness.py",
        "tests/test_reorderable_tabs_base_contract.py",
        "tests/test_restart_required_dialog.py",
        "tests/test_restart_requirement_ui_controller.py",
        "tests/test_searchable_combo_box.py",
        "tests/test_settings_async.py",
        "tests/test_settings_comfy_connection_page.py",
        "tests/test_settings_cube_library_page.py",
        "tests/test_settings_environment_page.py",
        "tests/test_settings_expander.py",
        "tests/test_settings_generation_page.py",
        "tests/test_settings_infobar.py",
        "tests/test_settings_integrated_workspace.py",
        "tests/test_settings_prompt_editor_page.py",
        "tests/test_settings_row.py",
        "tests/test_shutdown_progress_dialog_contract.py",
        "tests/test_shutdown_recovery_dialog_contract.py",
        "tests/test_splash_paper_flip_widget.py",
        "tests/test_splash_pose_library.py",
        "tests/test_splash_window_terminal_contract.py",
        "tests/test_startup_diagnostics_callout.py",
        "tests/test_startup_diagnostics_titlebar_controller.py",
        "tests/test_tab_and_stack_contract.py",
        "tests/test_tab_stack_qt_serial_contract.py",
        "tests/test_terminal_output_view_contract.py",
        "tests/test_theme_awareness_contract.py",
        "tests/test_thumbnail_picker_relayout_contract.py",
        "tests/test_titlebar_generation_action_cluster.py",
        "tests/test_titlebar_output_toggle_contract.py",
        "tests/test_titlebar_startup_diagnostics_button.py",
        "tests/test_toolbar_rendering_harness.py",
        "tests/test_wheel_intent_controller.py",
        "tests/test_widget_state_abuse_harness.py",
        "tests/test_wildcard_management_opener.py",
        "tests/test_workflow_tab_actions_contract.py",
        "tests/test_workflow_tab_interactions.py",
        "tests/test_workflow_tab_orb_cutout.py",
        "tests/test_workflow_tab_unread_highlight.py",
        "tests/test_workflow_tabs_settings_route.py",
        "tests/test_workspace_side_panel_host.py",
    }
)


def parallel_test_worker_count(available_workers: int | None) -> int:
    """Bound xdist concurrency to the native Qt suite's stable envelope."""

    if available_workers is None or available_workers < 1:
        return 1
    return min(available_workers, MAX_PARALLEL_TEST_WORKERS)


def current_test_platform(sys_platform: str = sys.platform) -> CiPlatform:
    """Return the supported test platform represented by ``sys.platform``."""

    if sys_platform == "win32":
        return CiPlatform.WINDOWS
    if sys_platform.startswith("linux"):
        return CiPlatform.LINUX
    if sys_platform == "darwin":
        return CiPlatform.MACOS
    raise ValueError(f"Unsupported test platform: {sys_platform}")


def marker_test_platforms(values: tuple[object, ...]) -> frozenset[CiPlatform]:
    """Validate and return platform names declared by a pytest marker."""

    if not values:
        raise ValueError("The platforms marker requires at least one platform name.")
    try:
        platforms = frozenset(CiPlatform(str(value)) for value in values)
    except ValueError as error:
        supported = ", ".join(platform.value for platform in CiPlatform)
        raise ValueError(
            f"Unsupported platforms marker value; expected one of: {supported}"
        ) from error
    return platforms


def platform_skip_reason(
    *,
    supported: frozenset[CiPlatform],
    current: CiPlatform,
) -> str | None:
    """Return a skip reason when a test does not apply to the current platform."""

    if current in supported:
        return None
    supported_names = ", ".join(sorted(platform.value for platform in supported))
    return (
        f"Test applies only to: {supported_names}; current platform: {current.value}."
    )


__all__ = [
    "MAX_PARALLEL_TEST_WORKERS",
    "PLATFORM_TEST_MODULES",
    "SERIAL_TEST_MODULES",
    "CiPlatform",
    "current_test_platform",
    "marker_test_platforms",
    "parallel_test_worker_count",
    "platform_skip_reason",
]
