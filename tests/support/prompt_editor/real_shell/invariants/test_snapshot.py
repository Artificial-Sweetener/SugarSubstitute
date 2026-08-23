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

"""Verify pure undo, caret, and autocomplete snapshot diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, cast

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)

if TYPE_CHECKING:
    from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot


@dataclass(frozen=True, slots=True)
class _SnapshotInvariantState:
    """Supply the mutable facts covered by snapshot-invariant fault cases."""

    source_text: str = "alpha\nbeta"
    cursor_position: int = 5
    undo_available: bool = False
    redo_available: bool = False
    undo_depth: int = 0
    redo_depth: int = 0
    undo_max_depth: int = 8
    redo_max_depth: int = 8
    undo_edit_block_depth: int = 0
    undo_pending_state_present: bool = False
    undo_typing_group_active: bool = False
    undo_typing_group_last_cursor_position: int | None = None
    undo_delete_group_active: bool = False
    undo_delete_group_key: int | None = None
    layout_content_width: float = 400.0
    layout_content_height: float = 48.0
    caret_token_id: str | None = "token-5"
    caret_token_id_resolves: bool = True
    caret_map_stop_count: int | None = 2
    caret_preferred_x: float | None = 24.0
    caret_rect_override: tuple[float, float, float, float] | None = None
    autocomplete_has_active_session: bool = False
    autocomplete_presenter_panel_visible: bool = False
    autocomplete_session_lifecycle: str = "idle"
    autocomplete_session_mode: str = "none"
    autocomplete_session_selected_index: int = -1
    autocomplete_session_suggestions: tuple[str, ...] = ()
    autocomplete_session_word_start: int | None = None
    autocomplete_session_word_end: int | None = None
    popup_state_visible: bool = False
    popup_global_rect: tuple[int, int, int, int] | None = None

    _VALID_STATE: ClassVar[dict[str, object]] = {
        "active_projection_layout_required": False,
        "active_projection_source_text": "alpha\nbeta",
        "active_projection_text": "alpha\nbeta",
        "anchor_token_id": "token-5",
        "anchor_token_id_resolves": True,
        "autocomplete_ghost_paint_visible_by_owner_state": False,
        "autocomplete_preview_active": False,
        "autocomplete_preview_source_position": None,
        "autocomplete_preview_suffix": "",
        "autocomplete_session_active_tag_end": None,
        "autocomplete_snapshot_cursor_position": None,
        "autocomplete_snapshot_source_length": None,
        "caret_map_source_length": 10,
        "caret_rect": (24.0, 0.0, 1.0, 16.0),
        "caret_rect_finite": True,
        "caret_rect_has_area": True,
        "caret_state_source_position": 5,
        "document_view_source_text": "alpha\nbeta",
        "editing_session_cursor_position": 5,
        "global_geometries": {"viewport": (0, 0, 400, 120)},
        "horizontal_scroll_maximum": 0,
        "horizontal_scroll_minimum": 0,
        "horizontal_scroll_page_step": 0,
        "last_content_paint_frame_is_current": True,
        "last_content_paint_result": "miss",
        "layout_inline_object_fragment_count": 0,
        "layout_is_current": True,
        "layout_line_count": 2,
        "layout_projection_source_text": "alpha\nbeta",
        "layout_projection_text": "alpha\nbeta",
        "layout_text_fragment_count": 2,
        "layout_text_width": 400.0,
        "layout_uses_projection_document": True,
        "paint_cache_ghosted_run_ids": (),
        "paint_cache_identity_matches_render_frame": True,
        "paint_cache_key_present": False,
        "paint_cache_layout_snapshot_identity_matches_layout": True,
        "paint_cache_projection_document_identity_matches_layout": True,
        "paint_cache_source_revision": 1,
        "paint_is_current": True,
        "projection_document_source_text": "alpha\nbeta",
        "projection_has_pending_update": False,
        "projection_has_stale_geometry": False,
        "projection_is_current": True,
        "projection_metrics_content_height": None,
        "projection_metrics_text_line_height": None,
        "projection_run_count": 1,
        "projection_text": "alpha\nbeta",
        "projection_token_count": 2,
        "scroll_values": {"editor_vertical": 0, "editor_horizontal": 0},
        "selected_source_text": "alpha",
        "selected_text": "alpha",
        "selection_range": (0, 5),
        "selection_rects": ((0.0, 0.0, 32.0, 16.0),),
        "semantic_is_current": True,
        "shell_document_vertical_padding": None,
        "shell_natural_height": None,
        "shell_outer_vertical_padding": None,
        "source_revision": 1,
        "transient_caret_geometry_present": False,
        "transient_caret_geometry_valid": True,
        "transient_deletion_overlay_erase_rects": (),
        "transient_deletion_overlay_present": False,
        "transient_deletion_overlay_repaint_rect": None,
        "transient_deletion_overlay_source_range": None,
        "transient_deletion_overlay_valid": True,
        "transient_deletion_overlay_viewport_rects": (),
        "transient_insertion_overlay_present": False,
        "transient_insertion_overlay_repaint_rect": None,
        "transient_insertion_overlay_source_range": None,
        "transient_insertion_overlay_valid": True,
        "transient_insertion_overlay_viewport_rect": None,
        "vertical_scroll_maximum": 0,
        "vertical_scroll_minimum": 0,
        "vertical_scroll_page_step": 0,
        "viewport_rect": (0, 0, 400, 120),
        "visible_layout_rows": (),
        "visible_text_fragments": (),
    }

    def __getattr__(self, name: str) -> object:
        """Return a valid immutable fact or require the test baseline to evolve."""

        try:
            return self._VALID_STATE[name]
        except KeyError as error:
            raise AttributeError(name) from error


def test_snapshot_invariants_report_undo_caret_and_autocomplete_faults() -> None:
    """Reject invalid undo grouping, caret mapping, and autocomplete sessions."""

    snapshot = _SnapshotInvariantState()

    assert _violations(snapshot) == ()

    cases = (
        (replace(snapshot, undo_available=True), "undo_availability_depth_mismatch"),
        (replace(snapshot, redo_available=True), "redo_availability_depth_mismatch"),
        (
            replace(
                snapshot, undo_typing_group_active=True, undo_delete_group_active=True
            ),
            "undo_typing_and_delete_groups_both_active",
        ),
        (replace(snapshot, undo_depth=9), "undo_depth_exceeds_max"),
        (replace(snapshot, redo_depth=9), "redo_depth_exceeds_max"),
        (
            replace(snapshot, undo_pending_state_present=True),
            "undo_pending_state_edit_block_mismatch",
        ),
        (
            replace(
                snapshot,
                undo_typing_group_active=True,
                undo_edit_block_depth=1,
                undo_pending_state_present=True,
            ),
            "undo_typing_group_missing_last_cursor",
        ),
        (
            replace(
                snapshot,
                undo_typing_group_active=True,
                undo_edit_block_depth=1,
                undo_pending_state_present=True,
                undo_typing_group_last_cursor_position=11,
            ),
            "undo_typing_group_last_cursor_out_of_bounds",
        ),
        (
            replace(snapshot, undo_typing_group_last_cursor_position=1),
            "undo_typing_group_last_cursor_without_active_group",
        ),
        (
            replace(
                snapshot,
                undo_delete_group_active=True,
                undo_edit_block_depth=1,
                undo_pending_state_present=True,
            ),
            "undo_delete_group_missing_key",
        ),
        (
            replace(snapshot, undo_delete_group_key=1),
            "undo_delete_group_key_without_active_group",
        ),
        (
            replace(snapshot, layout_content_width=float("nan")),
            "layout_content_width_invalid",
        ),
        (
            replace(snapshot, layout_content_height=-1.0),
            "layout_content_height_invalid:-1.0",
        ),
        (
            replace(
                snapshot, caret_token_id="missing-token", caret_token_id_resolves=False
            ),
            "caret_token_id_unresolved:missing-token",
        ),
        (replace(snapshot, caret_map_stop_count=0), "caret_map_has_no_stops"),
        (
            replace(snapshot, caret_preferred_x=float("inf")),
            "caret_preferred_x_not_finite",
        ),
        (
            replace(snapshot, caret_preferred_x=1_000.0),
            "caret_preferred_x_outside_layout_width",
        ),
        (
            replace(snapshot, caret_rect_override=(0.0, 0.0, -1.0, 16.0)),
            "caret_rect_override_invalid",
        ),
        (
            replace(snapshot, caret_rect_override=(999.0, 0.0, 1.0, 16.0)),
            "caret_rect_override_outside_layout",
        ),
        (
            _active_autocomplete_snapshot(snapshot, selected_index=99),
            "autocomplete_selected_index_out_of_bounds",
        ),
        (
            _active_autocomplete_snapshot(snapshot, selected_index=0, word_end=11),
            "autocomplete_session_word_range_out_of_bounds",
        ),
        (
            _active_autocomplete_snapshot(
                snapshot, selected_index=0, word_end=0, cursor_position=10
            ),
            "autocomplete_session_word_end_not_at_cursor",
        ),
        (
            _active_autocomplete_snapshot(
                snapshot, selected_index=0, popup_visible=True
            ),
            "visible_popup_missing_global_rect",
        ),
        (
            _active_autocomplete_snapshot(
                snapshot,
                selected_index=0,
                popup_visible=True,
                popup_global_rect=(99_999, 99_999, 100, 100),
            ),
            "visible_popup_not_anchored_to_editor",
        ),
    )

    for candidate, expected_violation in cases:
        assert any(
            violation.startswith(expected_violation)
            for violation in _violations(candidate)
        )


def _active_autocomplete_snapshot(
    snapshot: _SnapshotInvariantState,
    *,
    selected_index: int,
    word_end: int | None = None,
    cursor_position: int | None = None,
    popup_visible: bool = False,
    popup_global_rect: tuple[int, int, int, int] | None = None,
) -> _SnapshotInvariantState:
    """Return an active tag-autocomplete snapshot with one controlled mutation."""

    current_cursor = (
        snapshot.cursor_position if cursor_position is None else cursor_position
    )
    return replace(
        snapshot,
        cursor_position=current_cursor,
        autocomplete_has_active_session=True,
        autocomplete_presenter_panel_visible=True,
        popup_state_visible=popup_visible,
        popup_global_rect=popup_global_rect,
        autocomplete_session_lifecycle="active",
        autocomplete_session_mode="tag",
        autocomplete_session_selected_index=selected_index,
        autocomplete_session_suggestions=("alpha",),
        autocomplete_session_word_start=0,
        autocomplete_session_word_end=current_cursor if word_end is None else word_end,
    )


def _violations(snapshot: _SnapshotInvariantState) -> tuple[str, ...]:
    """Evaluate one typed synthetic state at the production invariant boundary."""

    return snapshot_invariant_violations(cast("PromptEditorStateSnapshot", snapshot))
