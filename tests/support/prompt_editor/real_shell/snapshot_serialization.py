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

"""Serialize prompt-editor snapshots into replayable diagnostic JSON."""

from __future__ import annotations

import json
from pathlib import Path

from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot


def snapshot_json(snapshot: PromptEditorStateSnapshot) -> dict[str, object]:
    """Serialize snapshot diagnostics without embedding image payloads."""

    return {
        "label": snapshot.label,
        "source_text": snapshot.source_text,
        "selected_text": snapshot.selected_text,
        "selected_source_text": snapshot.selected_source_text,
        "selection_range": snapshot.selection_range,
        "selection_rects": snapshot.selection_rects,
        "cursor_position": snapshot.cursor_position,
        "caret_state_placement": snapshot.caret_state_placement,
        "anchor_state_placement": snapshot.anchor_state_placement,
        "display_mode": snapshot.display_mode,
        "focus_widget_path": snapshot.focus_widget_path,
        "active_window_path": snapshot.active_window_path,
        "target_event_widget_path": snapshot.target_event_widget_path,
        "geometries": dict(snapshot.geometries),
        "global_geometries": dict(snapshot.global_geometries),
        "scroll_values": dict(snapshot.scroll_values),
        "device_pixel_ratio": snapshot.device_pixel_ratio,
        "autocomplete_gateway_calls": snapshot.autocomplete_gateway_calls,
        "popup_widget_exists": snapshot.popup_widget_exists,
        "popup_state_visible": snapshot.popup_state_visible,
        "popup_visual_visible": snapshot.popup_visual_visible,
        "popup_global_rect": snapshot.popup_global_rect,
        "ghost_visual_visible": snapshot.ghost_visual_visible,
        "expected_ghost_suffix": snapshot.expected_ghost_suffix,
        "autocomplete_preview_active": snapshot.autocomplete_preview_active,
        "autocomplete_preview_suffix": snapshot.autocomplete_preview_suffix,
        "autocomplete_preview_source_position": (
            snapshot.autocomplete_preview_source_position
        ),
        "autocomplete_session_lifecycle": snapshot.autocomplete_session_lifecycle,
        "autocomplete_session_mode": snapshot.autocomplete_session_mode,
        "autocomplete_session_selected_index": (
            snapshot.autocomplete_session_selected_index
        ),
        "autocomplete_session_prefix": snapshot.autocomplete_session_prefix,
        "autocomplete_session_word_start": snapshot.autocomplete_session_word_start,
        "autocomplete_session_word_end": snapshot.autocomplete_session_word_end,
        "autocomplete_session_active_tag_end": (
            snapshot.autocomplete_session_active_tag_end
        ),
        "autocomplete_session_suggestions": snapshot.autocomplete_session_suggestions,
        "autocomplete_has_active_session": snapshot.autocomplete_has_active_session,
        "autocomplete_presenter_panel_visible": (
            snapshot.autocomplete_presenter_panel_visible
        ),
        "autocomplete_presenter_panel_under_mouse": (
            snapshot.autocomplete_presenter_panel_under_mouse
        ),
        "autocomplete_source_revision": snapshot.autocomplete_source_revision,
        "autocomplete_snapshot_source_length": (
            snapshot.autocomplete_snapshot_source_length
        ),
        "autocomplete_snapshot_cursor_position": (
            snapshot.autocomplete_snapshot_cursor_position
        ),
        "source_revision": snapshot.source_revision,
        "semantic_source_revision": snapshot.semantic_source_revision,
        "semantic_revision": snapshot.semantic_revision,
        "projection_semantic_revision": snapshot.projection_semantic_revision,
        "projection_revision": snapshot.projection_revision,
        "layout_revision": snapshot.layout_revision,
        "viewport_revision": snapshot.viewport_revision,
        "paint_revision": snapshot.paint_revision,
        "semantic_is_current": snapshot.semantic_is_current,
        "projection_is_current": snapshot.projection_is_current,
        "layout_is_current": snapshot.layout_is_current,
        "paint_is_current": snapshot.paint_is_current,
        "editing_session_source_revision": snapshot.editing_session_source_revision,
        "editing_session_cursor_position": snapshot.editing_session_cursor_position,
        "editing_session_anchor_position": snapshot.editing_session_anchor_position,
        "document_view_source_text": snapshot.document_view_source_text,
        "document_view_region_separator_count": (
            snapshot.document_view_region_separator_count
        ),
        "projection_document_source_text": snapshot.projection_document_source_text,
        "projection_region_separator_count": (
            snapshot.projection_region_separator_count
        ),
        "active_projection_source_text": snapshot.active_projection_source_text,
        "layout_projection_source_text": snapshot.layout_projection_source_text,
        "projection_text": snapshot.projection_text,
        "active_projection_text": snapshot.active_projection_text,
        "layout_projection_text": snapshot.layout_projection_text,
        "active_projection_layout_required": (
            snapshot.active_projection_layout_required
        ),
        "layout_uses_projection_document": snapshot.layout_uses_projection_document,
        "layout_uses_active_projection_document": (
            snapshot.layout_uses_active_projection_document
        ),
        "paint_cache_key_present": snapshot.paint_cache_key_present,
        "paint_cache_source_revision": snapshot.paint_cache_source_revision,
        "paint_cache_projection_document_identity_matches_layout": (
            snapshot.paint_cache_projection_document_identity_matches_layout
        ),
        "paint_cache_layout_snapshot_identity_matches_layout": (
            snapshot.paint_cache_layout_snapshot_identity_matches_layout
        ),
        "paint_cache_ghosted_run_ids": snapshot.paint_cache_ghosted_run_ids,
        "autocomplete_ghost_paint_visible_by_owner_state": (
            snapshot.autocomplete_ghost_paint_visible_by_owner_state
        ),
        "projection_freshness": snapshot.projection_freshness,
        "projection_has_pending_update": snapshot.projection_has_pending_update,
        "projection_has_stale_geometry": snapshot.projection_has_stale_geometry,
        "caret_state_source_position": snapshot.caret_state_source_position,
        "anchor_state_source_position": snapshot.anchor_state_source_position,
        "caret_map_source_length": snapshot.caret_map_source_length,
        "caret_map_stop_count": snapshot.caret_map_stop_count,
        "caret_preferred_x": snapshot.caret_preferred_x,
        "caret_rect_override": snapshot.caret_rect_override,
        "skip_next_same_source_soft_wrap_move": (
            snapshot.skip_next_same_source_soft_wrap_move
        ),
        "projection_token_count": snapshot.projection_token_count,
        "projection_run_count": snapshot.projection_run_count,
        "layout_line_count": snapshot.layout_line_count,
        "layout_text_fragment_count": snapshot.layout_text_fragment_count,
        "layout_inline_object_fragment_count": (
            snapshot.layout_inline_object_fragment_count
        ),
        "layout_content_width": snapshot.layout_content_width,
        "layout_content_height": snapshot.layout_content_height,
        "layout_text_width": snapshot.layout_text_width,
        "visible_layout_rows": [
            {
                "row_index": row.row_index,
                "source_start": row.source_start,
                "source_end": row.source_end,
                "document_top": row.document_top,
                "viewport_top": row.viewport_top,
                "height": row.height,
                "text": row.text,
            }
            for row in snapshot.visible_layout_rows
        ],
        "visible_text_fragments": [
            {
                "fragment_index": fragment.fragment_index,
                "source_start": fragment.source_start,
                "source_end": fragment.source_end,
                "document_rect": fragment.document_rect,
                "viewport_rect": fragment.viewport_rect,
                "document_baseline": fragment.document_baseline,
                "viewport_baseline": fragment.viewport_baseline,
                "text": fragment.text,
            }
            for fragment in snapshot.visible_text_fragments
        ],
        "caret_token_id": snapshot.caret_token_id,
        "anchor_token_id": snapshot.anchor_token_id,
        "caret_token_id_resolves": snapshot.caret_token_id_resolves,
        "anchor_token_id_resolves": snapshot.anchor_token_id_resolves,
        "caret_rect": snapshot.caret_rect,
        "viewport_rect": snapshot.viewport_rect,
        "caret_rect_finite": snapshot.caret_rect_finite,
        "caret_rect_has_area": snapshot.caret_rect_has_area,
        "caret_rect_intersects_viewport": snapshot.caret_rect_intersects_viewport,
        "vertical_scroll_minimum": snapshot.vertical_scroll_minimum,
        "vertical_scroll_maximum": snapshot.vertical_scroll_maximum,
        "vertical_scroll_page_step": snapshot.vertical_scroll_page_step,
        "horizontal_scroll_minimum": snapshot.horizontal_scroll_minimum,
        "horizontal_scroll_maximum": snapshot.horizontal_scroll_maximum,
        "horizontal_scroll_page_step": snapshot.horizontal_scroll_page_step,
        "transient_caret_geometry_present": snapshot.transient_caret_geometry_present,
        "transient_caret_geometry_valid": snapshot.transient_caret_geometry_valid,
        "transient_insertion_overlay_present": (
            snapshot.transient_insertion_overlay_present
        ),
        "transient_insertion_overlay_valid": (
            snapshot.transient_insertion_overlay_valid
        ),
        "transient_insertion_overlay_source_range": (
            snapshot.transient_insertion_overlay_source_range
        ),
        "transient_insertion_overlay_viewport_rect": (
            snapshot.transient_insertion_overlay_viewport_rect
        ),
        "transient_insertion_overlay_repaint_rect": (
            snapshot.transient_insertion_overlay_repaint_rect
        ),
        "transient_deletion_overlay_present": (
            snapshot.transient_deletion_overlay_present
        ),
        "transient_deletion_overlay_valid": snapshot.transient_deletion_overlay_valid,
        "transient_deletion_overlay_source_range": (
            snapshot.transient_deletion_overlay_source_range
        ),
        "transient_deletion_overlay_viewport_rects": (
            snapshot.transient_deletion_overlay_viewport_rects
        ),
        "transient_deletion_overlay_erase_rects": (
            snapshot.transient_deletion_overlay_erase_rects
        ),
        "transient_deletion_overlay_repaint_rect": (
            snapshot.transient_deletion_overlay_repaint_rect
        ),
        "undo_available": snapshot.undo_available,
        "redo_available": snapshot.redo_available,
        "undo_depth": snapshot.undo_depth,
        "redo_depth": snapshot.redo_depth,
        "undo_max_depth": snapshot.undo_max_depth,
        "redo_max_depth": snapshot.redo_max_depth,
        "undo_edit_block_depth": snapshot.undo_edit_block_depth,
        "undo_pending_state_present": snapshot.undo_pending_state_present,
        "undo_typing_group_active": snapshot.undo_typing_group_active,
        "undo_typing_group_last_cursor_position": (
            snapshot.undo_typing_group_last_cursor_position
        ),
        "undo_delete_group_active": snapshot.undo_delete_group_active,
        "undo_delete_group_key": snapshot.undo_delete_group_key,
        "observed_event_start_index": snapshot.observed_event_start_index,
        "observed_event_end_index": snapshot.observed_event_end_index,
        "recent_observed_events": [
            {
                "index": event.index,
                "owner": event.owner,
                "method": event.method,
                "source_before": event.source_before,
                "source_after": event.source_after,
                "cursor_before": event.cursor_before,
                "cursor_after": event.cursor_after,
                "preview_before": event.preview_before,
                "preview_after": event.preview_after,
                "session_before": event.session_before,
                "session_after": event.session_after,
                "panel_before": event.panel_before,
                "panel_after": event.panel_after,
                "result": event.result,
            }
            for event in snapshot.recent_observed_events
        ],
    }


def write_snapshot_json(path: Path, snapshot: PromptEditorStateSnapshot) -> None:
    """Write one snapshot diagnostic JSON file."""

    path.write_text(
        json.dumps(snapshot_json(snapshot), indent=2, sort_keys=True),
        encoding="utf-8",
    )
