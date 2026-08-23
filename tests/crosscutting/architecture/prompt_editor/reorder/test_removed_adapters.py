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

"""Keep deleted reorder overlay adapters and mirrors from returning."""

from __future__ import annotations

from ..inventory import (
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_removed_reorder_overlay_adapters_cannot_return() -> None:
    """Keep deleted reorder overlay adapters and mirrors from returning."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    landing_capture = f"{prefix}overlays.reorder_landing_capture"
    landing_diagnostics = f"{prefix}overlays.reorder_landing_diagnostics"
    landing_events = f"{prefix}overlays.reorder_landing_events"
    landing_paint_cache = f"{prefix}overlays.reorder_landing_paint_cache"
    landing_paint_policy = f"{prefix}overlays.reorder_landing_paint_policy"
    landing_request_owner = f"{prefix}overlays.reorder_landing_request_owner"
    landing_state = f"{prefix}overlays.reorder_landing_state"
    landing_session = f"{prefix}overlays.reorder_landing_session"
    landing_paint_owner = f"{prefix}overlays.reorder_landing_paint"
    landing_visual_owner = landing_paint_owner
    view = f"{prefix}overlays.reorder_view"
    overlay = f"{prefix}overlays.reorder_overlay"
    factory = f"{prefix}composition.reorder_overlay_factory"
    interaction_geometry = f"{prefix}projection.reorder_interaction_geometry"

    overlay_sources = "\n".join(
        (PROMPT_PRESENTATION_ROOT / "overlays" / module_name).read_text(
            encoding="utf-8"
        )
        for module_name in ("reorder_overlay.py",)
    )
    removed_mirrors = (
        "_preview_visuals_by_index",
        "_preview_chip_geometry_snapshot",
        "_base_drag_chip_geometry_snapshot",
        "_placement_snapshot",
        "_active_placement",
        "_drop_target_visuals",
        "_drop_target_lanes",
        "_preview_geometry_target_identity",
        "_live_raster_entries_render_key",
        "_live_raster_entries_by_index",
        "_preview_raster_entries_render_key",
        "_preview_raster_entries_by_index",
        "_animation_presenter",
        "_held_chip_presenter",
        "_animation_frame_batch_depth",
        "_animation_frame_sync_pending",
        "_animation_visual_owner",
        "_animation_planner",
        "_displacement_session",
        "_animation_generation_id",
        "_animated_pointer_region_indices",
        "_instrumentation_animation_plan_build_count",
        "_drag_proxy",
        "_drag_proxy_host",
        "_drag_proxy_state_factory",
        "_drag_proxy_placement",
        "_last_suppressed_chip_snapshots_by_index",
        "_render_state_sync_revision",
        "_last_drop_commit_visual",
        "_last_drop_commit_geometry",
        "_last_drop_commit_target",
        "_last_drop_commit_placement",
        "_last_drop_commit_segment_index",
        "_last_drop_commit_gesture_id",
        "_last_drop_commit_event_id",
        "_prepared_drag_proxy_segment_index",
        "_drop_target_tracker",
        "_visuals_by_index",
        "_live_visual_snapshots_by_index",
        "_chip_geometry_snapshot",
        "_last_live_visual_geometry_key",
        "_visual_snapshot_cache",
        "_preview_visual_snapshots_by_index",
        "_segments_by_index",
        "_source_identity",
    )
    assert all(f"self.{field} =" not in overlay_sources for field in removed_mirrors)
    assert "self._instrumentation_" not in overlay_sources
    assert "self._pointer_loop_depth" not in overlay_sources
    assert "def _log_interaction_event" not in overlay_sources
    assert "def log_interaction_event" not in overlay_sources
    assert "def _log_interaction_timing" not in overlay_sources
    assert "def _log_reorder_anomaly" not in overlay_sources
    assert "self._drag_handler" not in overlay_sources
    assert "self._commit_handler" not in overlay_sources
    assert "self._cancel_handler" not in overlay_sources
    assert "def _emit_drag_intent" not in overlay_sources
    removed_metric_adapters = (
        "current_instrumentation_work_unit_id",
        "instrumentation_gesture_id",
        "instrumentation_event_id",
        "is_drag_pointer_loop_active",
        "record_preview_scheduler_event",
        "record_preview_sync_decision",
        "record_preview_sync_elapsed",
        "record_render_plan_elapsed",
    )
    assert all(
        f"def {method_name}(" not in overlay_sources
        for method_name in removed_metric_adapters
    )
    removed_keyboard_adapters = (
        "move_active_chip_left",
        "move_active_chip_right",
        "move_active_chip_up",
        "move_active_chip_down",
        "_move_active_chip_by_keyboard",
    )
    reorder_interaction_sources = "\n".join(
        (PROMPT_PRESENTATION_ROOT / "interactions" / filename).read_text(
            encoding="utf-8"
        )
        for filename in ("reorder_interaction.py", "reorder_overlay_session.py")
    )
    assert all(
        f"def {method_name}(" not in overlay_sources
        and f".{method_name}(" not in reorder_interaction_sources
        for method_name in removed_keyboard_adapters
    )
    pointer_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_pointer_regions.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderPointerController" not in pointer_source
    assert "self._controller" not in pointer_source
    assert "_drag_intent_rect_from_global_position" not in overlay_sources
    assert "def _update_drop_target_from_global_position" not in overlay_sources
    assert "def _overlay_position_geometry_key" not in overlay_sources
    assert "def reorder_position_geometry_key" not in overlay_sources
    assert "def _emit_preview_layout_changed" not in overlay_sources
    assert "_live_chip_owned_ranges_by_index" not in overlay_sources
    assert "def _update_pointer_region_geometry" not in overlay_sources
    assert "def _update_chip_states" not in overlay_sources
    assert "def _capture_drag_intent_context" not in overlay_sources
    assert "def _drag_intent_source_rect" not in overlay_sources
    assert "def _clear_drag_intent_context" not in overlay_sources
    assert "def _capture_held_shadow_geometry" not in overlay_sources
    assert "self._last_overlay_position_geometry_key" not in overlay_sources
    assert "self._last_overlay_refresh_geometry_key" not in overlay_sources
    assert "self._last_pointer_region_geometry_key" not in overlay_sources
    assert "def _overlay_refresh_geometry_key" not in overlay_sources
    assert "def _pointer_region_geometry_key" not in overlay_sources
    assert "def _sync_pointer_region_geometry_if_needed" not in overlay_sources
    assert "def _autoscroll_context" not in overlay_sources
    assert "def _handle_autoscroll_step" not in overlay_sources
    assert "def _chip_visual_snapshots_from_projection" not in overlay_sources
    assert "def _prepare_preview_visual_snapshots" not in overlay_sources
    assert "def _preview_mode_active" not in overlay_sources
    assert "def _layout_for_painted_preview" not in overlay_sources
    assert "def _landing_visual_request" not in overlay_sources
    assert "def _preview_chip_geometry_for_segment" not in overlay_sources
    assert "def _drop_target_visual_for_target" not in overlay_sources
    assert "def _preview_target_identity_for_active_target" not in overlay_sources
    assert "def _preview_target_identity_matches_active_target" not in overlay_sources
    assert "def _refresh_preview_geometry(" not in overlay_sources
    assert "def _update_preview_layout(" not in overlay_sources
    assert "def _insertion_marker_rect(" not in overlay_sources
    assert "def _placement_owned_landing_geometry(" not in overlay_sources
    assert "def _pending_landing_visual_rect(" not in overlay_sources
    assert "def _pending_shadow_preview_visual(" not in overlay_sources
    assert "def _landing_preview_for_active_target(" not in overlay_sources
    assert "def _sync_reorder_view_state(" not in overlay_sources
    assert "def _publish_reorder_prepared_visual(" not in overlay_sources
    assert "def _prepare_reorder_visual_publication(" not in overlay_sources
    assert "def _chip_styles_by_index(" not in overlay_sources
    assert "def _visible_visual_for_segment(" not in overlay_sources
    assert "def _chip_geometry_for_segment(" not in overlay_sources
    assert "self._prepared_visual_owner" not in overlay_sources
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_landing_visual_owner.py"
    ).exists()
    assert {
        landing_capture,
        landing_diagnostics,
        landing_events,
        landing_state,
    } <= graph[landing_session]
    assert graph[landing_session].isdisjoint(
        {
            landing_visual_owner,
            landing_request_owner,
            overlay,
            factory,
            interaction_geometry,
            view,
        }
    )
    assert {
        landing_diagnostics,
        landing_events,
        landing_paint_cache,
        landing_paint_policy,
        landing_state,
    } <= graph[landing_visual_owner]
    assert landing_capture not in graph[landing_visual_owner]
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_interaction.py"
    ).exists()
    visual_cache_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_visual_cache.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderVisualSnapshotCache" not in visual_cache_source
    assert "class PromptReorderVisualCacheCounters" not in visual_cache_source
    overlay_ports_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_ports.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderOverlayRenderState" not in overlay_ports_source
    assert "def set_render_state(" not in overlay_ports_source

    obsolete_split_publication_apis = (
        "set_reorder_overlay_suppression_snapshots",
        "set_reorder_surface_chrome",
        "replace_suppression",
        "replace_chrome",
        "clear_suppression",
    )
    for source_path in (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_surface_visual_state.py",
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_ports.py",
        PROMPT_PRESENTATION_ROOT / "shell" / "widget.py",
        PROMPT_PRESENTATION_ROOT / "widget.py",
        PROMPT_PRESENTATION_ROOT / "widget.pyi",
    ):
        source = source_path.read_text(encoding="utf-8")
        assert not any(
            obsolete_api in source for obsolete_api in obsolete_split_publication_apis
        )
