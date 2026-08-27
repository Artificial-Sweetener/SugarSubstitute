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

"""Validate complete real-shell prompt-editor state snapshots."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from tests.support.prompt_editor.real_shell.invariants.autocomplete import (
    popup_geometry_violations,
    preview_violations,
    session_violations,
)
from tests.support.prompt_editor.real_shell.invariants.projection import (
    accepted_selected_text_for_source,
    caret_row_height_contract_violations,
    projection_metrics_contract_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transient_overlay import (
    deletion_overerase_violations,
    rectangle_is_finite_nonnegative,
    violations as transient_overlay_violations,
)

if TYPE_CHECKING:
    from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot


def snapshot_invariant_violations(
    snapshot: PromptEditorStateSnapshot,
) -> tuple[str, ...]:
    """Return code-level prompt editor invariant violations for one snapshot."""

    violations: list[str] = []
    source_length = len(snapshot.source_text)
    if not 0 <= snapshot.cursor_position <= source_length:
        violations.append(
            f"cursor_out_of_source_bounds:{snapshot.cursor_position}:{source_length}"
        )
    selection_start, selection_end = snapshot.selection_range
    if not 0 <= selection_start <= selection_end <= source_length:
        violations.append(
            f"selection_out_of_source_bounds:{selection_start}:{selection_end}:"
            f"{source_length}"
        )
    if snapshot.selected_text not in accepted_selected_text_for_source(
        snapshot.selected_source_text
    ):
        violations.append("selected_text_source_slice_mismatch")
    selection_is_empty = selection_start == selection_end
    if selection_is_empty and snapshot.selection_rects:
        violations.append("selection_rects_present_for_empty_selection")
    if snapshot.editing_session_cursor_position != snapshot.cursor_position:
        violations.append(
            "editing_session_cursor_mismatch:"
            f"{snapshot.editing_session_cursor_position}:{snapshot.cursor_position}"
        )
    if snapshot.caret_state_source_position != snapshot.cursor_position:
        violations.append(
            "caret_state_cursor_mismatch:"
            f"{snapshot.caret_state_source_position}:{snapshot.cursor_position}"
        )
    projection_is_allowed_to_lag = (
        snapshot.projection_has_pending_update
        and snapshot.projection_has_stale_geometry
    )
    if not projection_is_allowed_to_lag:
        if not snapshot.semantic_is_current:
            violations.append("semantic_revision_lineage_stale")
        if not snapshot.projection_is_current:
            violations.append("projection_revision_lineage_stale")
        if not snapshot.layout_is_current:
            violations.append("layout_revision_lineage_stale")
    if snapshot.paint_cache_key_present and not snapshot.paint_is_current:
        violations.append("paint_revision_lineage_stale")
    if not selection_is_empty and not projection_is_allowed_to_lag:
        if not snapshot.selection_rects:
            violations.append("selection_rects_missing_for_nonempty_selection")
        for rect in snapshot.selection_rects:
            if not rectangle_is_finite_nonnegative(rect):
                violations.append(f"selection_rect_invalid:{rect}")
            elif not document_rect_within_layout_envelope(
                rect,
                content_width=snapshot.layout_text_width,
                content_height=snapshot.layout_content_height,
            ):
                violations.append(f"selection_rect_outside_layout:{rect}")
    if (
        not projection_is_allowed_to_lag
        and snapshot.caret_map_source_length != source_length
    ):
        violations.append(
            f"caret_map_source_length_mismatch:{snapshot.caret_map_source_length}:"
            f"{source_length}"
        )
    if snapshot.caret_map_stop_count is not None and snapshot.caret_map_stop_count < 1:
        violations.append("caret_map_has_no_stops")
    if snapshot.caret_preferred_x is not None:
        if not math.isfinite(snapshot.caret_preferred_x):
            violations.append(
                f"caret_preferred_x_not_finite:{snapshot.caret_preferred_x}"
            )
        elif snapshot.caret_preferred_x < -4.0:
            violations.append(
                f"caret_preferred_x_negative:{snapshot.caret_preferred_x}"
            )
        elif snapshot.caret_preferred_x > snapshot.layout_text_width + 64.0:
            violations.append(
                "caret_preferred_x_outside_layout_width:"
                f"{snapshot.caret_preferred_x}:{snapshot.layout_text_width}"
            )
    if snapshot.caret_rect_override is not None:
        if not rectangle_is_finite_nonnegative(snapshot.caret_rect_override):
            violations.append(
                f"caret_rect_override_invalid:{snapshot.caret_rect_override}"
            )
        elif not document_rect_within_layout_envelope(
            snapshot.caret_rect_override,
            content_width=snapshot.layout_text_width,
            content_height=snapshot.layout_content_height,
        ):
            violations.append(
                f"caret_rect_override_outside_layout:{snapshot.caret_rect_override}"
            )
    if snapshot.projection_run_count < 0:
        violations.append("projection_run_count_negative")
    if snapshot.projection_token_count < 0:
        violations.append("projection_token_count_negative")
    if snapshot.layout_line_count < 0:
        violations.append("layout_line_count_negative")
    if snapshot.layout_text_fragment_count < 0:
        violations.append("layout_text_fragment_count_negative")
    if snapshot.layout_inline_object_fragment_count < 0:
        violations.append("layout_inline_object_fragment_count_negative")
    if (
        not math.isfinite(snapshot.layout_content_width)
        or snapshot.layout_content_width < 0.0
    ):
        violations.append(
            f"layout_content_width_invalid:{snapshot.layout_content_width}"
        )
    if (
        not math.isfinite(snapshot.layout_content_height)
        or snapshot.layout_content_height < 0.0
    ):
        violations.append(
            f"layout_content_height_invalid:{snapshot.layout_content_height}"
        )
    if (
        not math.isfinite(snapshot.layout_text_width)
        or snapshot.layout_text_width < 1.0
    ):
        violations.append(f"layout_text_width_invalid:{snapshot.layout_text_width}")
    if not snapshot.caret_token_id_resolves:
        violations.append(f"caret_token_id_unresolved:{snapshot.caret_token_id}")
    if not snapshot.anchor_token_id_resolves:
        violations.append(f"anchor_token_id_unresolved:{snapshot.anchor_token_id}")
    if not snapshot.caret_rect_finite:
        violations.append("caret_rect_not_finite")
    if not snapshot.caret_rect_has_area:
        violations.append("caret_rect_missing_area")
    if not (
        snapshot.vertical_scroll_minimum
        <= snapshot.scroll_values["editor_vertical"]
        <= snapshot.vertical_scroll_maximum
    ):
        violations.append(
            "vertical_scroll_value_out_of_range:"
            f"{snapshot.vertical_scroll_minimum}:"
            f"{snapshot.scroll_values['editor_vertical']}:"
            f"{snapshot.vertical_scroll_maximum}"
        )
    if snapshot.vertical_scroll_page_step < 0:
        violations.append("vertical_scroll_page_step_negative")
    if snapshot.vertical_scroll_maximum < snapshot.vertical_scroll_minimum:
        violations.append("vertical_scroll_range_inverted")
    if not (
        snapshot.horizontal_scroll_minimum
        <= snapshot.scroll_values["editor_horizontal"]
        <= snapshot.horizontal_scroll_maximum
    ):
        violations.append(
            "horizontal_scroll_value_out_of_range:"
            f"{snapshot.horizontal_scroll_minimum}:"
            f"{snapshot.scroll_values['editor_horizontal']}:"
            f"{snapshot.horizontal_scroll_maximum}"
        )
    if snapshot.horizontal_scroll_page_step < 0:
        violations.append("horizontal_scroll_page_step_negative")
    if snapshot.horizontal_scroll_maximum < snapshot.horizontal_scroll_minimum:
        violations.append("horizontal_scroll_range_inverted")
    violations.extend(transient_overlay_violations(snapshot))
    violations.extend(projection_metrics_contract_violations(snapshot))
    violations.extend(caret_row_height_contract_violations(snapshot))
    violations.extend(deletion_overerase_violations(snapshot))
    if snapshot.undo_depth < 0:
        violations.append("undo_depth_negative")
    if snapshot.redo_depth < 0:
        violations.append("redo_depth_negative")
    if snapshot.undo_edit_block_depth < 0:
        violations.append("undo_edit_block_depth_negative")
    if snapshot.undo_max_depth < 1:
        violations.append(f"undo_max_depth_invalid:{snapshot.undo_max_depth}")
    if snapshot.redo_max_depth < 1:
        violations.append(f"redo_max_depth_invalid:{snapshot.redo_max_depth}")
    if snapshot.undo_depth > snapshot.undo_max_depth:
        violations.append(
            f"undo_depth_exceeds_max:{snapshot.undo_depth}:{snapshot.undo_max_depth}"
        )
    if snapshot.redo_depth > snapshot.redo_max_depth:
        violations.append(
            f"redo_depth_exceeds_max:{snapshot.redo_depth}:{snapshot.redo_max_depth}"
        )
    if snapshot.undo_pending_state_present != (snapshot.undo_edit_block_depth > 0):
        violations.append(
            "undo_pending_state_edit_block_mismatch:"
            f"{snapshot.undo_pending_state_present}:"
            f"{snapshot.undo_edit_block_depth}"
        )
    if snapshot.undo_available != (snapshot.undo_depth > 0):
        violations.append(
            "undo_availability_depth_mismatch:"
            f"{snapshot.undo_available}:{snapshot.undo_depth}"
        )
    if snapshot.redo_available != (snapshot.redo_depth > 0):
        violations.append(
            "redo_availability_depth_mismatch:"
            f"{snapshot.redo_available}:{snapshot.redo_depth}"
        )
    if snapshot.undo_typing_group_active and snapshot.undo_delete_group_active:
        violations.append("undo_typing_and_delete_groups_both_active")
    if snapshot.undo_typing_group_active:
        if snapshot.undo_edit_block_depth <= 0:
            violations.append("undo_typing_group_without_edit_block")
        if snapshot.undo_typing_group_last_cursor_position is None:
            violations.append("undo_typing_group_missing_last_cursor")
        elif not 0 <= snapshot.undo_typing_group_last_cursor_position <= source_length:
            violations.append(
                "undo_typing_group_last_cursor_out_of_bounds:"
                f"{snapshot.undo_typing_group_last_cursor_position}:"
                f"{source_length}"
            )
    elif snapshot.undo_typing_group_last_cursor_position is not None:
        violations.append("undo_typing_group_last_cursor_without_active_group")
    if snapshot.undo_delete_group_active:
        if snapshot.undo_edit_block_depth <= 0:
            violations.append("undo_delete_group_without_edit_block")
        if snapshot.undo_delete_group_key is None:
            violations.append("undo_delete_group_missing_key")
    elif snapshot.undo_delete_group_key is not None:
        violations.append("undo_delete_group_key_without_active_group")
    if snapshot.document_view_source_text != snapshot.source_text:
        violations.append("document_view_source_mismatch")
    if (
        not projection_is_allowed_to_lag
        and snapshot.projection_document_source_text != snapshot.source_text
    ):
        violations.append("projection_document_source_mismatch")
    if (
        not projection_is_allowed_to_lag
        and snapshot.active_projection_source_text != snapshot.source_text
    ):
        violations.append("active_projection_source_mismatch")
    if (
        not snapshot.autocomplete_preview_active
        and not snapshot.active_projection_layout_required
        and snapshot.active_projection_text != snapshot.projection_text
    ):
        violations.append("active_projection_preview_leaked_without_preview_state")
    if not projection_is_allowed_to_lag and not snapshot.autocomplete_preview_active:
        if snapshot.autocomplete_ghost_paint_visible_by_owner_state:
            violations.append("autocomplete_ghost_paint_visible_without_preview_state")
        if snapshot.layout_projection_source_text != snapshot.source_text:
            violations.append("layout_projection_source_mismatch")
        if snapshot.layout_projection_text != snapshot.projection_text:
            violations.append("layout_projection_preview_leaked_without_preview_state")
        if (
            not snapshot.layout_uses_projection_document
            and snapshot.layout_projection_text != snapshot.projection_text
        ):
            violations.append("layout_not_restored_to_base_projection_document")
        if snapshot.paint_cache_ghosted_run_ids:
            violations.append(
                "paint_cache_ghosted_runs_without_preview_state:"
                f"{','.join(snapshot.paint_cache_ghosted_run_ids)}"
            )
    cache_was_reused = (
        snapshot.selection_range[0] == snapshot.selection_range[1]
        and not snapshot.autocomplete_preview_active
        and snapshot.paint_is_current
        and snapshot.last_content_paint_result == "hit"
        and snapshot.last_content_paint_frame_is_current
    )
    if snapshot.paint_cache_key_present and cache_was_reused:
        if not snapshot.paint_cache_identity_matches_render_frame:
            violations.append("paint_cache_identity_mismatch_render_frame")
        if (
            not projection_is_allowed_to_lag
            and not snapshot.paint_cache_projection_document_identity_matches_layout
        ):
            violations.append("paint_cache_projection_document_identity_mismatch")
        if (
            not projection_is_allowed_to_lag
            and not snapshot.paint_cache_layout_snapshot_identity_matches_layout
        ):
            violations.append("paint_cache_layout_snapshot_identity_mismatch")
        if (
            not projection_is_allowed_to_lag
            and snapshot.paint_cache_source_revision != snapshot.source_revision
        ):
            violations.append(
                "paint_cache_source_revision_mismatch:"
                f"{snapshot.paint_cache_source_revision}:"
                f"{snapshot.source_revision}"
            )
    if (
        snapshot.autocomplete_preview_active
        and snapshot.active_projection_source_text != snapshot.source_text
    ):
        violations.append("autocomplete_active_projection_source_mismatch")
    if snapshot.autocomplete_snapshot_source_length not in (None, source_length):
        violations.append(
            "autocomplete_snapshot_source_length_mismatch:"
            f"{snapshot.autocomplete_snapshot_source_length}:{source_length}"
        )
    if (
        snapshot.autocomplete_snapshot_cursor_position is not None
        and snapshot.autocomplete_snapshot_cursor_position != snapshot.cursor_position
        and snapshot.autocomplete_has_active_session
    ):
        violations.append(
            "autocomplete_snapshot_cursor_mismatch:"
            f"{snapshot.autocomplete_snapshot_cursor_position}:"
            f"{snapshot.cursor_position}"
        )
    if snapshot.autocomplete_has_active_session:
        violations.extend(session_violations(snapshot))
    if snapshot.autocomplete_preview_active:
        violations.extend(preview_violations(snapshot))
    if (
        snapshot.autocomplete_has_active_session
        and not snapshot.autocomplete_presenter_panel_visible
    ):
        violations.append("active_autocomplete_session_without_presenter_panel")
    if snapshot.popup_state_visible and not snapshot.autocomplete_has_active_session:
        violations.append("visible_popup_without_active_autocomplete_session")
    if snapshot.popup_state_visible:
        violations.extend(popup_geometry_violations(snapshot))
    return tuple(violations)


def document_rect_within_layout_envelope(
    rect: tuple[float, float, float, float],
    *,
    content_width: float,
    content_height: float,
) -> bool:
    """Return whether a document-space rectangle stays in the layout envelope."""

    x, y, width, height = rect
    return (
        x >= -1.0
        and y >= -1.0
        and x + width <= content_width + 1.0
        and y + height <= content_height + 1.0
    )
