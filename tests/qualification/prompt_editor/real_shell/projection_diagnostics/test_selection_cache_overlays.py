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

"""Verify selection, cache, and transient-overlay snapshot invariants."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from PySide6.QtGui import QTextCursor

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.models import PromptEditorStateSnapshot
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_detects_selection_cache_and_transient_overlay_violations(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Reject invalid selection, cache, viewport, and transient-overlay owner state."""

    snapshot = _selected_snapshot(real_shell_scenario)
    selected_text_mismatch = snapshot_invariant_violations(
        replace(snapshot, selected_text="wrong")
    )
    empty_selection_with_rects = snapshot_invariant_violations(
        replace(
            snapshot,
            selection_range=(0, 0),
            selection_rects=((0.0, 0.0, 8.0, 16.0),),
        )
    )
    nonempty_selection_without_rects = snapshot_invariant_violations(
        replace(snapshot, selection_rects=())
    )
    invalid_selection_rect = snapshot_invariant_violations(
        replace(snapshot, selection_rects=((0.0, 0.0, -1.0, 16.0),))
    )
    out_of_bounds_selection_rect = snapshot_invariant_violations(
        replace(
            snapshot,
            selection_rects=((snapshot.layout_text_width + 999.0, 0.0, 8.0, 16.0),),
        )
    )
    caret_outside_viewport = transition_violations(
        action_name="caret",
        before=snapshot,
        after=replace(
            snapshot,
            selected_text="",
            selected_source_text="",
            selection_range=(snapshot.cursor_position, snapshot.cursor_position),
            selection_rects=(),
            caret_rect=(99999.0, 99999.0, 1.0, 16.0),
            caret_rect_intersects_viewport=False,
        ),
        snapshot_violations=snapshot_invariant_violations,
    )
    scroll_out_of_range = snapshot_invariant_violations(
        replace(
            snapshot,
            scroll_values={**snapshot.scroll_values, "editor_vertical": 99999},
        )
    )
    empty_selection_snapshot = replace(snapshot, selection_range=(0, 0))
    cache_document_mismatch = snapshot_invariant_violations(
        replace(
            empty_selection_snapshot,
            paint_cache_key_present=True,
            last_content_paint_result="hit",
            last_content_paint_frame_is_current=True,
            paint_cache_identity_matches_render_frame=False,
            paint_cache_projection_document_identity_matches_layout=False,
        )
    )
    selected_cache_document_mismatch = snapshot_invariant_violations(
        replace(
            snapshot,
            paint_cache_key_present=True,
            last_content_paint_result="hit",
            last_content_paint_frame_is_current=True,
            paint_cache_identity_matches_render_frame=False,
            paint_cache_projection_document_identity_matches_layout=False,
        )
    )
    stale_render_frame_cache_mismatch = snapshot_invariant_violations(
        replace(
            empty_selection_snapshot,
            paint_cache_key_present=True,
            last_content_paint_result="hit",
            last_content_paint_frame_is_current=False,
            paint_cache_identity_matches_render_frame=True,
            paint_cache_projection_document_identity_matches_layout=False,
            paint_cache_layout_snapshot_identity_matches_layout=False,
        )
    )
    cache_source_revision_mismatch = snapshot_invariant_violations(
        replace(
            empty_selection_snapshot,
            paint_cache_key_present=True,
            last_content_paint_result="hit",
            last_content_paint_frame_is_current=True,
            paint_cache_identity_matches_render_frame=False,
            paint_cache_source_revision=-1,
        )
    )
    autocomplete_preview_cache_mismatch = snapshot_invariant_violations(
        replace(
            empty_selection_snapshot,
            autocomplete_preview_active=True,
            paint_cache_key_present=True,
            paint_cache_projection_document_identity_matches_layout=False,
            paint_cache_layout_snapshot_identity_matches_layout=False,
            paint_cache_source_revision=-1,
        )
    )
    stale_insertion_overlay = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_present=True,
            transient_insertion_overlay_valid=False,
        )
    )
    insertion_overlay_range = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_source_range=(0, len(snapshot.source_text) + 1),
        )
    )
    missing_insertion_repaint_rect = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_present=True,
            transient_insertion_overlay_valid=True,
            transient_insertion_overlay_viewport_rect=(0.0, 0.0, 12.0, 18.0),
            transient_insertion_overlay_repaint_rect=None,
        )
    )
    invalid_insertion_repaint_rect = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_repaint_rect=(0.0, 0.0, float("nan"), 18.0),
        )
    )
    broad_insertion_repaint_rect = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_insertion_overlay_repaint_rect=(0.0, 0.0, 99999.0, 18.0),
        )
    )
    missing_deletion_erase_rects = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_deletion_overlay_present=True,
            transient_deletion_overlay_valid=True,
            transient_deletion_overlay_viewport_rects=((0.0, 0.0, 12.0, 18.0),),
            transient_deletion_overlay_erase_rects=(),
            transient_deletion_overlay_repaint_rect=(0.0, 0.0, 12.0, 18.0),
        )
    )
    invalid_deletion_erase_rect = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_deletion_overlay_erase_rects=((0.0, 0.0, -1.0, 18.0),),
        )
    )
    broad_deletion_repaint_rect = snapshot_invariant_violations(
        replace(
            snapshot,
            transient_deletion_overlay_repaint_rect=(0.0, 0.0, 12.0, 99999.0),
        )
    )

    assert "selected_text_source_slice_mismatch" in selected_text_mismatch
    assert "selection_rects_present_for_empty_selection" in empty_selection_with_rects
    assert (
        "selection_rects_missing_for_nonempty_selection"
        in nonempty_selection_without_rects
    )
    assert any(
        violation.startswith("selection_rect_invalid")
        for violation in invalid_selection_rect
    )
    assert any(
        violation.startswith("selection_rect_outside_layout")
        for violation in out_of_bounds_selection_rect
    )
    assert "caret_rect_outside_viewport_after_settle" in caret_outside_viewport
    assert any(
        violation.startswith("vertical_scroll_value_out_of_range")
        for violation in scroll_out_of_range
    )
    assert (
        "paint_cache_projection_document_identity_mismatch" in cache_document_mismatch
    )
    assert "paint_cache_identity_mismatch_render_frame" in cache_document_mismatch
    assert (
        "paint_cache_projection_document_identity_mismatch"
        not in selected_cache_document_mismatch
    )
    assert not any(
        violation.startswith("paint_cache_")
        for violation in stale_render_frame_cache_mismatch
    )
    assert any(
        violation.startswith("paint_cache_source_revision_mismatch")
        for violation in cache_source_revision_mismatch
    )
    assert not any(
        violation.startswith("paint_cache_")
        for violation in autocomplete_preview_cache_mismatch
    )
    assert "stale_transient_insertion_overlay" in stale_insertion_overlay
    assert any(
        violation.startswith("transient_insertion_overlay_range_out_of_bounds")
        for violation in insertion_overlay_range
    )
    assert (
        "transient_insertion_overlay_repaint_rect_missing"
        in missing_insertion_repaint_rect
    )
    assert any(
        violation.startswith("transient_insertion_overlay_repaint_rect_invalid")
        for violation in invalid_insertion_repaint_rect
    )
    assert any(
        violation.startswith("transient_insertion_overlay_repaint_rect_too_broad")
        for violation in broad_insertion_repaint_rect
    )
    assert (
        "transient_deletion_overlay_erase_rects_missing" in missing_deletion_erase_rects
    )
    assert any(
        violation.startswith("transient_deletion_overlay_erase_rect_invalid")
        for violation in invalid_deletion_erase_rect
    )
    assert any(
        violation.startswith("transient_deletion_overlay_repaint_rect_too_broad")
        for violation in broad_deletion_repaint_rect
    )


def _selected_snapshot(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> PromptEditorStateSnapshot:
    """Return a selected multi-line snapshot for invariant mutation tests."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text="alpha\nbeta"
    )
    cursor = cast(Any, field.editor).textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    cast(Any, field.editor).setTextCursor(cursor)
    return real_shell_scenario.snapshots.capture(
        field,
        label="common-sense-invariant-baseline",
    )
