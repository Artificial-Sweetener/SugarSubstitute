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

"""Verify explicit prompt reorder state boundaries."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, QSizeF

from substitute.application.prompt_editor import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    PromptReorderAnimationGenerationState,
    PromptReorderGeometryGenerationState,
    PromptReorderKeyboardState,
    PromptReorderOverlayPositionGeometryKey,
    PromptReorderOverlayRefreshGeometryKey,
    PromptReorderPointerState,
    PromptReorderPreparedGeometryIdentity,
    PromptReorderPreviewTargetIdentity,
    PromptReorderPreviewTargetState,
    reorder_base_drag_geometry_key,
    reorder_chip_widget_geometry_key,
    reorder_live_visual_geometry_key,
    reorder_overlay_position_geometry_key,
    reorder_overlay_refresh_geometry_key,
    reorder_source_fingerprint,
)


def _prepared_geometry_identity(
    *,
    active_target: PromptLineDropTarget | None,
) -> PromptReorderPreparedGeometryIdentity:
    """Build one minimal prepared geometry identity for state tests."""

    layout_key = (((0, (0, 1)),), ())
    snapshot_key = (
        reorder_source_fingerprint("alpha, beta"),
        ((0, 0, 5),),
        ((0, 0, 5),),
    )
    return PromptReorderPreparedGeometryIdentity(
        source_fingerprint=reorder_source_fingerprint("alpha, beta"),
        projection_identity=layout_key,
        dragged_segment_index=1,
        active_target=active_target,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        preview_snapshot_key=snapshot_key,
        base_drag_snapshot_key=snapshot_key,
        viewport_identity=("viewport", 320, 180, 0),
    )


def test_reorder_state_docstrings_name_owner_and_state_kind() -> None:
    """Phase 2 state objects should document writer, reader, and state kind."""

    for state_type in (
        PromptReorderPointerState,
        PromptReorderKeyboardState,
        PromptReorderPreviewTargetIdentity,
        PromptReorderPreviewTargetState,
        PromptReorderPreparedGeometryIdentity,
        PromptReorderGeometryGenerationState,
        PromptReorderAnimationGenerationState,
        PromptReorderOverlayPositionGeometryKey,
        PromptReorderOverlayRefreshGeometryKey,
    ):
        docstring = state_type.__doc__
        assert docstring is not None
        assert "Writer:" in docstring
        assert "Readers:" in docstring
        assert "State kind:" in docstring


def test_reorder_pointer_and_keyboard_state_are_immutable() -> None:
    """Pointer and keyboard state should be read-only projection values."""

    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    pointer_state = PromptReorderPointerState(
        hovered_segment_index=1,
        pressed_segment_index=1,
        base_drag_segment_index=1,
        dragged_segment_index=1,
        committed_dragged_segment_index=None,
        active_drop_target=target,
        last_drag_global_position=QPoint(12, 24),
        drag_grab_offset=QPointF(4.0, 5.0),
        drag_intent_size=QSizeF(60.0, 20.0),
        last_drag_intent_rect=QRectF(10.0, 20.0, 60.0, 20.0),
    )
    keyboard_state = PromptReorderKeyboardState(
        active_segment_index=1,
        base_drag_segment_index=1,
        active_drop_target=target,
        keyboard_preferred_x=42.0,
    )

    with pytest.raises(FrozenInstanceError):
        pointer_state.dragged_segment_index = None  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        keyboard_state.keyboard_preferred_x = None  # type: ignore[misc]


def test_reorder_preview_identity_distinguishes_target_and_viewport() -> None:
    """Preview identities should reject stale target and viewport combinations."""

    layout_key = (((0, (0, 1, 2)),), ())
    first_target = PromptLineDropTarget(row_index=0, insertion_index=1)
    second_target = PromptLineDropTarget(row_index=0, insertion_index=2)
    identity = PromptReorderPreviewTargetIdentity(
        source_fingerprint=reorder_source_fingerprint("alpha, beta, gamma"),
        projection_identity=layout_key,
        dragged_segment_index=1,
        target=first_target,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        viewport_identity=("viewport", 320, 180, 0),
    )

    assert identity == PromptReorderPreviewTargetIdentity(
        source_fingerprint=reorder_source_fingerprint("alpha, beta, gamma"),
        projection_identity=layout_key,
        dragged_segment_index=1,
        target=first_target,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        viewport_identity=("viewport", 320, 180, 0),
    )
    assert identity != PromptReorderPreviewTargetIdentity(
        source_fingerprint=reorder_source_fingerprint("alpha, beta, gamma"),
        projection_identity=layout_key,
        dragged_segment_index=1,
        target=second_target,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        viewport_identity=("viewport", 320, 180, 0),
    )
    assert identity != PromptReorderPreviewTargetIdentity(
        source_fingerprint=reorder_source_fingerprint("alpha, beta, gamma"),
        projection_identity=layout_key,
        dragged_segment_index=1,
        target=first_target,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        viewport_identity=("viewport", 320, 180, 12),
    )


def test_reorder_source_fingerprint_keeps_prompt_text_out_of_state() -> None:
    """Text-derived reorder identities should expose only prompt-safe structure."""

    source_text = "alpha, beta, gamma"
    fingerprint = reorder_source_fingerprint(source_text)

    assert fingerprint[0] == len(source_text)
    assert source_text not in repr(fingerprint)


def test_overlay_position_geometry_key_tracks_viewport_inputs() -> None:
    """Overlay position identity should change when viewport geometry changes."""

    first = reorder_overlay_position_geometry_key(
        viewport_left=0,
        viewport_top=0,
        viewport_width=320,
        viewport_height=180,
        content_left=2,
        content_top=4,
        content_width=300,
        content_height=160,
        scroll_offset=0,
    )
    scrolled = reorder_overlay_position_geometry_key(
        viewport_left=0,
        viewport_top=0,
        viewport_width=320,
        viewport_height=180,
        content_left=2,
        content_top=4,
        content_width=300,
        content_height=160,
        scroll_offset=8,
    )
    resized = reorder_overlay_position_geometry_key(
        viewport_left=0,
        viewport_top=0,
        viewport_width=400,
        viewport_height=180,
        content_left=2,
        content_top=4,
        content_width=380,
        content_height=160,
        scroll_offset=0,
    )

    assert first == reorder_overlay_position_geometry_key(
        viewport_left=0,
        viewport_top=0,
        viewport_width=320,
        viewport_height=180,
        content_left=2,
        content_top=4,
        content_width=300,
        content_height=160,
        scroll_offset=0,
    )
    assert first != scrolled
    assert first != resized


def test_overlay_refresh_geometry_key_uses_prompt_safe_source_identity() -> None:
    """Refresh identity should include source/layout/target without raw prompt text."""

    position_key = reorder_overlay_position_geometry_key(
        viewport_left=0,
        viewport_top=0,
        viewport_width=320,
        viewport_height=180,
        content_left=0,
        content_top=0,
        content_width=320,
        content_height=180,
        scroll_offset=0,
    )
    layout_key = (((0, (0, 1)),), ())
    snapshot_key = (
        reorder_source_fingerprint("secret prompt"),
        ((0, 0, 6),),
        ((0, 0, 6),),
    )
    live_key = reorder_live_visual_geometry_key(
        source_text="secret prompt",
        segment_ranges=((0, 0, 6),),
        content_left=0,
        content_top=0,
        content_width=320,
        scroll_offset=0,
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=1)

    key = reorder_overlay_refresh_geometry_key(
        position_key=position_key,
        source_text="secret prompt",
        live_geometry_key=live_key,
        current_layout_key=layout_key,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        preview_snapshot_key=snapshot_key,
        base_drag_snapshot_key=snapshot_key,
        dragged_segment_index=1,
        active_target=target,
    )
    changed_target_key = reorder_overlay_refresh_geometry_key(
        position_key=position_key,
        source_text="secret prompt",
        live_geometry_key=live_key,
        current_layout_key=layout_key,
        preview_layout_key=layout_key,
        base_drag_layout_key=layout_key,
        preview_snapshot_key=snapshot_key,
        base_drag_snapshot_key=snapshot_key,
        dragged_segment_index=1,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    assert key.source_fingerprint == reorder_source_fingerprint("secret prompt")
    assert "secret prompt" not in repr(key)
    assert key != changed_target_key


def test_chip_widget_geometry_key_tracks_preview_and_live_rects() -> None:
    """Chip widget placement identity should distinguish preview/live rect changes."""

    first = reorder_chip_widget_geometry_key(
        dragged_segment_index=1,
        preview_mode_active=True,
        preview_rects=((1, 10.0, 20.0, 30.0, 12.0),),
        live_rects=((0, 0.0, 20.0, 30.0, 12.0),),
    )
    same_unsorted = reorder_chip_widget_geometry_key(
        dragged_segment_index=1,
        preview_mode_active=True,
        preview_rects=((2, 40.0, 20.0, 30.0, 12.0), (1, 10.0, 20.0, 30.0, 12.0)),
        live_rects=((0, 0.0, 20.0, 30.0, 12.0),),
    )
    changed_live = reorder_chip_widget_geometry_key(
        dragged_segment_index=1,
        preview_mode_active=True,
        preview_rects=((1, 10.0, 20.0, 30.0, 12.0),),
        live_rects=((0, 2.0, 20.0, 30.0, 12.0),),
    )

    assert first == reorder_chip_widget_geometry_key(
        dragged_segment_index=1,
        preview_mode_active=True,
        preview_rects=((1, 10.0, 20.0, 30.0, 12.0),),
        live_rects=((0, 0.0, 20.0, 30.0, 12.0),),
    )
    assert same_unsorted[2] == (
        (1, 10.0, 20.0, 30.0, 12.0),
        (2, 40.0, 20.0, 30.0, 12.0),
    )
    assert first != changed_live


def test_base_drag_geometry_key_requires_layout_and_snapshot_identity() -> None:
    """Base-drag geometry identity should be unavailable until core inputs exist."""

    layout_key = (((0, (0, 1)),), ())
    snapshot_key = (
        reorder_source_fingerprint("alpha, beta"),
        ((0, 0, 5),),
        ((0, 0, 5),),
    )

    assert (
        reorder_base_drag_geometry_key(
            base_drag_layout_key=None,
            base_drag_snapshot_key=snapshot_key,
            viewport_identity=("viewport", 1),
            dragged_segment_index=1,
        )
        is None
    )
    assert reorder_base_drag_geometry_key(
        base_drag_layout_key=layout_key,
        base_drag_snapshot_key=snapshot_key,
        viewport_identity=("viewport", 1),
        dragged_segment_index=1,
    ) == (
        layout_key,
        snapshot_key,
        ("viewport", 1),
        1,
    )


def test_reorder_generation_state_keeps_geometry_and_animation_separate() -> None:
    """Animation generation should not replace prepared geometry identity."""

    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    geometry_state = PromptReorderGeometryGenerationState(
        generation_id=7,
        prepared_geometry_identity=_prepared_geometry_identity(active_target=target),
        base_drag_geometry_key=None,
    )
    animation_state = PromptReorderAnimationGenerationState(
        generation_id=0,
        geometry_generation_id=geometry_state.generation_id,
        active_target=target,
    )

    assert animation_state.generation_id == 0
    assert animation_state.geometry_generation_id == 7
    assert (
        animation_state.active_target
        == geometry_state.prepared_geometry_identity.active_target
    )
    assert animation_state.invalidated is False


def test_gesture_controller_exposes_pointer_and_keyboard_state() -> None:
    """Current gesture owner should publish typed state without QWidget access."""

    gesture = PromptReorderGestureController()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)

    gesture.activate_segment(1)
    assert gesture.begin_pointer_drag(
        segment_index=1,
        global_position=QPoint(20, 30),
    )
    gesture.capture_drag_intent_context(
        chip_rect=QRectF(10.0, 10.0, 50.0, 20.0),
        local_pointer=QPointF(25.0, 18.0),
    )
    assert gesture.set_active_drop_target(target)
    gesture.set_keyboard_preferred_x(18.0)

    pointer_state = gesture.pointer_state()
    keyboard_state = gesture.keyboard_state()

    assert pointer_state.dragged_segment_index == 1
    assert pointer_state.active_drop_target == target
    assert pointer_state.drag_grab_offset == QPointF(15.0, 8.0)
    assert keyboard_state.active_segment_index == 1
    assert keyboard_state.active_drop_target == target
    assert keyboard_state.keyboard_preferred_x == 18.0
