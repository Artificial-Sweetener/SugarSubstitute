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

"""Verify public OutputCanvas host-facing behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas


OUTPUT_CANVAS_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "presentation"
    / "canvas"
    / "output"
    / "output_canvas_view.py"
)
OUTPUT_NAVIGATION_CONTROLLER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "presentation"
    / "canvas"
    / "output"
    / "output_canvas_navigation_controller.py"
)


def test_set_dock_action_text_updates_menu_label() -> None:
    """Output dock action label should be stored for the next context menu."""

    fake = SimpleNamespace(_dock_action_text="Undock canvas")

    cast(Any, OutputCanvas).set_dock_action_text(fake, "Redock canvas")

    assert fake._dock_action_text == "Redock canvas"


def test_output_canvas_has_no_private_compare_pass_through_wrappers() -> None:
    """Output compare seams should call composed controllers directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_compare_controller" not in source
    assert "def _output_compare_presenter" not in source
    assert "def _output_compare_rendering_controller" not in source
    assert "def _set_compare_mode_enabled" not in source
    assert "def _sync_compare_rendering" not in source
    assert "def _on_pane_comparison_changed" not in source


def test_output_canvas_has_no_private_preview_cache_pass_through_wrappers() -> None:
    """Output preview lifecycle seams should read the revision cache directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _preview_registry_snapshot" not in source
    assert "def _scene_preview_slots" not in source
    assert "def _source_preview_ids_by_slot" not in source
    assert "def _completed_preview_slots" not in source
    assert "def _pending_final_preview_retire_ids" not in source


def test_output_canvas_has_no_private_source_tab_adapter_wrappers() -> None:
    """Output source-tab controller adapters should stay in controller composition."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_source_tabs_controller" not in source
    assert "def _rebuild_source_tabs" not in source
    assert "def _source_tab_tooltip_filter_map" not in source
    assert "def _sync_source_selector_adapter" not in source
    assert "def _refresh_source_tab_tooltips" not in source


def test_output_canvas_has_no_private_navigation_measurement_wrappers() -> None:
    """Output navigation measurement should call the navigation controller directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_navigation_controller" not in source
    assert "def _available_tabbar_container_width" not in source
    assert "def _preferred_tabbar_width" not in source
    assert "def _measure_tabbar_preferred_width" not in source


def test_output_canvas_has_no_private_compare_bar_placement_wrapper() -> None:
    """Output compare bar placement should call the navigation controller directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _place_compare_bar" not in source


def test_output_canvas_has_no_private_theme_style_wrapper() -> None:
    """Output chrome styling should be wired directly to the chrome controller."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _apply_theme_styles" not in source
    assert "def apply_theme_styles" not in source
    assert "def _output_chrome_controller" not in source
    assert "OutputCanvasChromeController" not in source
    assert "connect_theme_refresh" not in source
    assert "floating_surface_rgba" not in source


def test_output_canvas_has_no_private_asset_lookup_wrappers() -> None:
    """Output asset lookup should call the asset owner directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_asset_lookup" not in source
    assert "def _final_output_payload" not in source
    assert "def _final_output_metadata" not in source
    assert "def _preview_image_cache" not in source
    assert "_final_output_payload_lookup" not in source
    assert "_final_output_metadata_lookup" not in source


def test_output_canvas_has_no_private_scene_preview_wrapper() -> None:
    """Scene preview mutation should call the preview controller directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _set_scene_preview_image" not in source


def test_output_canvas_has_no_private_route_application_wrappers() -> None:
    """Output route application should call the route controller directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_route_application_controller" not in source
    assert "def _output_interaction_controller" not in source
    assert "def _output_route_projector" not in source
    assert "def _output_qpane_presenter" not in source
    assert "def _output_route_presenter" not in source
    assert "def _output_grid_composer" not in source
    assert "def _output_scene_overview_composer" not in source
    assert "def _compose_scene_overview_grid" not in source
    assert "def _compose_grid_scene_for_source" not in source


def test_output_canvas_has_no_private_context_menu_accessor() -> None:
    """Output context-menu wiring should use the composed controller."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_context_menu_controller" not in source


def test_output_canvas_has_no_private_compare_state_wrappers() -> None:
    """Output compare state should use explicit host adapter callbacks."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _visible_output_compare_state" not in source
    assert "def visible_output_compare_state" not in source
    assert "def _set_visible_output_compare_state" not in source
    assert "def store_visible_output_compare_state" not in source
    assert "def _sync_compare_projection" not in source
    assert "def _sync_comparison_nav_buttons" not in source
    assert "def _sync_compare_set_button" not in source
    assert "def _sync_compare_source_button" not in source
    assert "def _sync_compare_scene_button" not in source


def test_output_canvas_has_no_private_selector_metric_wrappers() -> None:
    """Output selector sizing policy should live in the navigation-bar owner."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _scene_selector_width" not in source
    assert "def _source_selector_width" not in source
    assert "def _scene_selector_width_for_text" not in source
    assert "def scene_selector_width_for_text" not in source
    assert "def _scene_selector_display_text" not in source
    assert "def scene_selector_display_text" not in source
    assert "def _source_selector_width_for_text" not in source
    assert "def source_selector_width_for_text" not in source
    assert "def _source_selector_display_text" not in source
    assert "def source_selector_display_text" not in source
    assert "def _text_width_for_scene_selector" not in source
    assert "def _text_width_for_source_selector" not in source
    assert "def _scene_selector_font_metrics" not in source
    assert "def _source_selector_font_metrics" not in source
    assert "def _sync_scene_selector_button" not in source
    assert "def _sync_set_selector_button" not in source
    assert "def _sync_source_selector_button" not in source


def test_output_canvas_has_no_private_picker_row_width_wrappers() -> None:
    """Output picker row-width policy should call the picker owner directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_picker_controller" not in source
    assert "def _scene_picker_row_width" not in source
    assert "def _source_picker_row_width" not in source


def test_output_canvas_has_no_private_preview_controller_accessor() -> None:
    """Output preview mutations should use the composed preview controller."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _output_preview_controller" not in source


def test_output_canvas_has_no_loose_scalar_preview_ingress() -> None:
    """Live previews should enter through strict preview acceptance only."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def set_preview_image" not in source


def test_output_canvas_projection_session_binding_is_public_adapter_only() -> None:
    """Projection binding policy should live in the projection controller."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")
    start = source.index("    def bind_projection_session")
    end = source.index("    def eventFilter", start)
    method_source = source[start:end]

    assert (
        "self._runtime.projection.controller.bind_projection_session" in method_source
    )
    assert "reconcile_output_compare_state" not in method_source
    assert "consume_final_output_preview_retirement" not in method_source
    assert "active_scene_overview" not in method_source


def test_output_canvas_event_filter_is_public_adapter_only() -> None:
    """Grid event policy should live in the composed grid event controller."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")
    start = source.index("    def eventFilter")
    end = source.index("    def resizeEvent", start)
    method_source = source[start:end]

    assert "_runtime.grid.event_controller.handle_event_filter" in method_source
    assert "grid_mouse_release_activation" not in method_source
    assert "activate_output_scene" not in method_source
    assert "activate_output_item" not in method_source


def test_output_canvas_resize_event_contains_no_content_layout_policy() -> None:
    """Output resize should remain a chrome-only host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")
    start = source.index("    def resizeEvent")
    end = source.index("\n\n\n__all__", start)
    method_source = source[start:end]

    assert "update_output_tabbar_container" in method_source
    assert "super().resizeEvent" in method_source
    assert "compose" not in method_source
    assert "grid_layout" not in method_source
    assert "preferred_grid_dimensions" not in method_source


def test_output_canvas_has_no_private_preview_registry_accessor() -> None:
    """Preview registry lookup should use the module host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _preview_registry" not in source


def test_output_canvas_has_no_private_scene_overview_preview_adapter() -> None:
    """Scene overview preview adaptation should live with the composer."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _scene_overview_preview_for_composer" not in source


def test_output_canvas_has_no_private_source_fallback_wrapper() -> None:
    """Source fallback policy should be resolved through the navigation owner."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _activate_source_fallback" not in source


def test_output_canvas_has_no_private_set_selection_wrapper() -> None:
    """Set selection should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _on_set_selected" not in source


def test_output_canvas_has_no_private_source_selection_wrapper() -> None:
    """Source selection should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _on_tab_changed" not in source


def test_output_canvas_has_no_private_scene_selection_wrapper() -> None:
    """Scene selection should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _on_scene_selected" not in source


def test_output_canvas_has_no_private_scene_overview_activation_wrapper() -> None:
    """Scene overview activation should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _activate_scene_overview" not in source


def test_output_canvas_has_no_private_output_item_activation_wrapper() -> None:
    """Concrete output activation should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _activate_output_item" not in source


def test_output_canvas_has_no_private_source_grid_activation_wrapper() -> None:
    """Source-grid activation should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _activate_grid_for_source" not in source


def test_output_canvas_has_no_private_scene_activation_wrapper() -> None:
    """Concrete scene activation should route through the navigation host adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _activate_scene" not in source


def test_output_navigation_adapters_use_explicit_chrome_callback() -> None:
    """Navigation adapters should not discover private tabbar methods by name."""

    source = OUTPUT_NAVIGATION_CONTROLLER_SOURCE.read_text(encoding="utf-8")

    assert "_call_host_method" not in source
    assert '"_update_tabbar_container"' not in source


def test_output_canvas_has_no_private_navigation_chrome_methods() -> None:
    """Output navigation chrome should live in the navigation chrome adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _update_tabbar_container" not in source
    assert "def _update_compare_nav_containers" not in source


def test_output_canvas_has_no_private_revision_cache_binding_wrapper() -> None:
    """Preview revision-cache binding should stay in the lifecycle service."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _bind_revision_cache" not in source


def test_output_canvas_does_not_mirror_preview_run_state_to_fake_hosts() -> None:
    """Preview run identity should stay in OutputCanvasRevisionCache."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert '"active_preview_generation_run_id"' not in source
    assert '"active_preview_scene_run_id"' not in source


def test_output_canvas_has_no_private_scene_source_group_accessors() -> None:
    """Scene/source group lookup should use route-state adapters."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _scene_groups_by_key" not in source
    assert "def _visible_source_groups_by_key" not in source
    assert "def output_scene_groups_by_key" not in source
    assert "def visible_output_source_groups_by_key" not in source


def test_output_canvas_has_no_private_revision_cache_accessor() -> None:
    """Preview state lookup should use the preview-state adapter owner."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def output_preview_registry" not in source
    assert "def output_revision_cache" not in source
    assert "def _output_revision_cache" not in source
    assert "OutputCanvasRevisionCache(" not in source


def test_output_canvas_has_no_private_final_output_preview_retirement_wrapper() -> None:
    """Final-output preview retirement should call the lifecycle command directly."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _retire_pending_preview_for_final_output" not in source


def test_output_canvas_has_no_private_single_preview_retirement_executor() -> None:
    """Single-preview retirement should use the preview-retirement adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _retire_preview_id" not in source
    assert "def retire_output_preview_id" not in source


def test_output_canvas_has_no_private_completed_slot_retirement_executor() -> None:
    """Completed-slot retirement should use the preview-retirement adapter."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _retire_previews_for_completed_slot" not in source
    assert "def retire_output_previews_for_completed_slot" not in source


def test_output_canvas_has_no_dead_previous_preview_run_wrapper() -> None:
    """Preview run transitions should stay in lifecycle service coverage."""

    source = OUTPUT_CANVAS_SOURCE.read_text(encoding="utf-8")

    assert "def _retire_previous_preview_run" not in source
