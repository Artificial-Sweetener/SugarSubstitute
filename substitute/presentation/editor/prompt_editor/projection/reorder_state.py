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

"""Define non-widget state identities for prompt segment reorder projection."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b

from PySide6.QtCore import QPoint, QPointF, QRectF, QSizeF

from substitute.application.prompt_editor import PromptReorderDropTarget


type ReorderSourceFingerprint = tuple[int, str]

type ReorderLayoutViewKey = tuple[
    tuple[tuple[int, tuple[int, ...]], ...],
    tuple[tuple[int, str, int, str], ...],
]

type ReorderPreviewSnapshotKey = tuple[
    ReorderSourceFingerprint,
    tuple[tuple[int, int, int], ...],
    tuple[tuple[int, int, int], ...],
]

type ReorderBaseDragGeometryKey = tuple[
    ReorderLayoutViewKey | None,
    ReorderPreviewSnapshotKey | None,
    object,
    int | None,
]

type ReorderLiveVisualGeometryKey = tuple[
    ReorderSourceFingerprint,
    tuple[tuple[int, int, int], ...],
    int,
    int,
    int,
    int,
]

type ReorderChipWidgetVisualRectKey = tuple[int, float, float, float, float]

type ReorderChipWidgetGeometryKey = tuple[
    int | None,
    bool,
    tuple[ReorderChipWidgetVisualRectKey, ...],
    tuple[ReorderChipWidgetVisualRectKey, ...],
]


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayPositionGeometryKey:
    """Identify cheap viewport inputs required to position the reorder overlay.

    Writer:
        `SegmentReorderOverlay` collects QWidget viewport/content scalars and
        asks this projection-state helper to build the immutable identity.
    Readers:
        Overlay refresh and autoscroll paths compare this state to skip
        unchanged positioning work without owning the key policy.
    State kind:
        Geometry-refresh state. It carries no QWidget references and does not
        mutate widgets or source text.
    """

    viewport_left: int
    viewport_top: int
    viewport_width: int
    viewport_height: int
    content_left: int
    content_top: int
    content_width: int
    content_height: int
    scroll_offset: int


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayRefreshGeometryKey:
    """Identify overlay refresh inputs that require geometry or preview work.

    Writer:
        `SegmentReorderOverlay` supplies scalar viewport, source, layout,
        snapshot, and target identities while this module owns the key shape.
    Readers:
        Overlay refresh compares this state to keep `request_geometry_refresh`
        a thin port with a cheap unchanged fast path.
    State kind:
        Geometry-refresh state. It uses a source fingerprint instead of prompt
        text and carries no QWidget references.
    """

    viewport_left: int
    viewport_top: int
    viewport_width: int
    viewport_height: int
    content_left: int
    content_top: int
    content_width: int
    content_height: int
    scroll_offset: int
    source_fingerprint: ReorderSourceFingerprint
    live_geometry_key: ReorderLiveVisualGeometryKey
    current_layout_key: ReorderLayoutViewKey | None
    preview_layout_key: ReorderLayoutViewKey | None
    base_drag_layout_key: ReorderLayoutViewKey | None
    preview_snapshot_key: ReorderPreviewSnapshotKey | None
    base_drag_snapshot_key: ReorderPreviewSnapshotKey | None
    dragged_segment_index: int | None
    active_target: PromptReorderDropTarget | None


@dataclass(frozen=True, slots=True)
class PromptReorderPointerState:
    """Expose pointer reorder state written by the overlay gesture owner.

    Writer:
        `PromptReorderGestureController` updates this state during pointer
        press, drag, drop, and cancel transitions.
    Readers:
        `SegmentReorderOverlay`, projection drop-target code, and focused tests
        read it to distinguish pointer state from preview or commit state.
    State kind:
        Pointer state. It does not decide whether Alt release mutates source.
    """

    hovered_segment_index: int | None
    pressed_segment_index: int | None
    base_drag_segment_index: int | None
    dragged_segment_index: int | None
    committed_dragged_segment_index: int | None
    active_drop_target: PromptReorderDropTarget | None
    last_drag_global_position: QPoint | None
    drag_grab_offset: QPointF | None
    drag_intent_size: QSizeF | None
    last_drag_intent_rect: QRectF | None


@dataclass(frozen=True, slots=True)
class PromptReorderKeyboardState:
    """Expose keyboard reorder state written by the overlay gesture owner.

    Writer:
        `PromptReorderGestureController` updates this state when a segment is
        activated and when Alt+Arrow navigation chooses a target or preferred X.
    Readers:
        `SegmentReorderOverlay`, projection keyboard-navigation code, and
        focused tests read it to distinguish keyboard state from pointer or
        commit state.
    State kind:
        Keyboard state. It is display/navigation state, not source mutation
        authority.
    """

    active_segment_index: int | None
    base_drag_segment_index: int | None
    active_drop_target: PromptReorderDropTarget | None
    keyboard_preferred_x: float | None


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewTargetIdentity:
    """Identify the semantic target that produced one preview geometry snapshot.

    Writer:
        `PromptReorderInteractionGeometry` creates this identity while building
        preview layout and geometry.
    Readers:
        `SegmentReorderOverlay`, landing-shadow checks, and geometry refresh
        code compare it against the active preview target.
    State kind:
        Preview state. It is display-only and must not overwrite commit state.
    """

    source_fingerprint: ReorderSourceFingerprint
    projection_identity: ReorderLayoutViewKey | None
    dragged_segment_index: int
    target: PromptReorderDropTarget
    preview_layout_key: ReorderLayoutViewKey | None
    base_drag_layout_key: ReorderLayoutViewKey | None
    viewport_identity: object | None


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewTargetState:
    """Expose the active preview target and the identities that generated it.

    Writer:
        `SegmentReorderOverlay` and `PromptReorderInteractionGeometry` update
        this state when a pointer or keyboard target changes and preview
        geometry is refreshed.
    Readers:
        The overlay paint/landing-shadow paths, interaction preview sync, and
        tests read it without reaching into QWidget-owned geometry.
    State kind:
        Preview state. It represents display projection, not commit authority.
    """

    dragged_segment_index: int | None
    active_target: PromptReorderDropTarget | None
    ordered_segment_indices: tuple[int, ...]
    preview_layout_target_identity: PromptReorderPreviewTargetIdentity | None
    preview_geometry_target_identity: PromptReorderPreviewTargetIdentity | None
    has_preview_layout: bool
    has_base_drag_layout: bool


@dataclass(frozen=True, slots=True)
class PromptReorderPreparedGeometryIdentity:
    """Identify prepared reorder geometry inputs required for stale-safe reuse.

    Writer:
        `PromptReorderInteractionGeometry` produces this identity from current
        projection snapshots, layout keys, target state, and viewport identity.
    Readers:
        Geometry refresh, landing-shadow validation, future drop-target owners,
        and tests use it to reject stale prepared geometry.
    State kind:
        Geometry-generation state. It describes generated geometry inputs and
        does not mutate widgets or source text.
    """

    source_fingerprint: ReorderSourceFingerprint
    projection_identity: ReorderLayoutViewKey | None
    dragged_segment_index: int | None
    active_target: PromptReorderDropTarget | None
    preview_layout_key: ReorderLayoutViewKey | None
    base_drag_layout_key: ReorderLayoutViewKey | None
    preview_snapshot_key: ReorderPreviewSnapshotKey | None
    base_drag_snapshot_key: ReorderPreviewSnapshotKey | None
    viewport_identity: object | None


@dataclass(frozen=True, slots=True)
class PromptReorderGeometryGenerationState:
    """Expose one read-only generation for prepared reorder geometry.

    Writer:
        `PromptReorderInteractionGeometry` and the overlay geometry-refresh path
        publish this state when prepared geometry inputs are inspected.
    Readers:
        Overlay tests and future animation planning use it to associate visual
        work with a specific prepared-geometry identity.
    State kind:
        Geometry-generation state. It carries no QWidget references.
    """

    generation_id: int
    prepared_geometry_identity: PromptReorderPreparedGeometryIdentity
    base_drag_geometry_key: ReorderBaseDragGeometryKey | None


@dataclass(frozen=True, slots=True)
class PromptReorderAnimationGenerationState:
    """Expose the display-only animation generation used to reject stale plans.

    Writer:
        Animation planning and presentation owners advance this state as
        display-only reorder targets change.
    Readers:
        Animation presenter, overlay integration code, and focused tests read it
        to keep animation state separate from preview and commit state.
    State kind:
        Animation state. It must never decide whether source mutates.
    """

    generation_id: int
    geometry_generation_id: int
    active_target: PromptReorderDropTarget | None
    invalidated: bool = False


def reorder_source_fingerprint(source_text: str) -> ReorderSourceFingerprint:
    """Return a prompt-safe identity for text-derived reorder geometry."""

    digest = blake2b(source_text.encode("utf-8"), digest_size=16).hexdigest()
    return len(source_text), digest


def reorder_overlay_position_geometry_key(
    *,
    viewport_left: int,
    viewport_top: int,
    viewport_width: int,
    viewport_height: int,
    content_left: int,
    content_top: int,
    content_width: int,
    content_height: int,
    scroll_offset: int,
) -> PromptReorderOverlayPositionGeometryKey:
    """Return the projection-owned identity for overlay positioning inputs."""

    return PromptReorderOverlayPositionGeometryKey(
        viewport_left=viewport_left,
        viewport_top=viewport_top,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        content_left=content_left,
        content_top=content_top,
        content_width=content_width,
        content_height=content_height,
        scroll_offset=scroll_offset,
    )


def reorder_live_visual_geometry_key(
    *,
    source_text: str,
    segment_ranges: tuple[tuple[int, int, int], ...],
    content_left: int,
    content_top: int,
    content_width: int,
    scroll_offset: int,
) -> ReorderLiveVisualGeometryKey:
    """Return the projection-owned identity for live chip visual fragments."""

    return (
        reorder_source_fingerprint(source_text),
        segment_ranges,
        content_left,
        content_top,
        content_width,
        scroll_offset,
    )


def reorder_overlay_refresh_geometry_key(
    *,
    position_key: PromptReorderOverlayPositionGeometryKey,
    source_text: str,
    live_geometry_key: ReorderLiveVisualGeometryKey,
    current_layout_key: ReorderLayoutViewKey | None,
    preview_layout_key: ReorderLayoutViewKey | None,
    base_drag_layout_key: ReorderLayoutViewKey | None,
    preview_snapshot_key: ReorderPreviewSnapshotKey | None,
    base_drag_snapshot_key: ReorderPreviewSnapshotKey | None,
    dragged_segment_index: int | None,
    active_target: PromptReorderDropTarget | None,
) -> PromptReorderOverlayRefreshGeometryKey:
    """Return the projection-owned identity for broad overlay refresh work."""

    return PromptReorderOverlayRefreshGeometryKey(
        viewport_left=position_key.viewport_left,
        viewport_top=position_key.viewport_top,
        viewport_width=position_key.viewport_width,
        viewport_height=position_key.viewport_height,
        content_left=position_key.content_left,
        content_top=position_key.content_top,
        content_width=position_key.content_width,
        content_height=position_key.content_height,
        scroll_offset=position_key.scroll_offset,
        source_fingerprint=reorder_source_fingerprint(source_text),
        live_geometry_key=live_geometry_key,
        current_layout_key=current_layout_key,
        preview_layout_key=preview_layout_key,
        base_drag_layout_key=base_drag_layout_key,
        preview_snapshot_key=preview_snapshot_key,
        base_drag_snapshot_key=base_drag_snapshot_key,
        dragged_segment_index=dragged_segment_index,
        active_target=active_target,
    )


def reorder_chip_widget_geometry_key(
    *,
    dragged_segment_index: int | None,
    preview_mode_active: bool,
    preview_rects: tuple[ReorderChipWidgetVisualRectKey, ...],
    live_rects: tuple[ReorderChipWidgetVisualRectKey, ...],
) -> ReorderChipWidgetGeometryKey:
    """Return the projection-owned identity for transparent chip widget placement."""

    return (
        dragged_segment_index,
        preview_mode_active,
        tuple(sorted(preview_rects)),
        tuple(sorted(live_rects)),
    )


def reorder_base_drag_geometry_key(
    *,
    base_drag_layout_key: ReorderLayoutViewKey | None,
    base_drag_snapshot_key: ReorderPreviewSnapshotKey | None,
    viewport_identity: object,
    dragged_segment_index: int | None,
) -> ReorderBaseDragGeometryKey | None:
    """Return the projection-owned identity for reusable stable base-drag geometry."""

    if base_drag_layout_key is None or base_drag_snapshot_key is None:
        return None
    return (
        base_drag_layout_key,
        base_drag_snapshot_key,
        viewport_identity,
        dragged_segment_index,
    )


__all__ = [
    "PromptReorderAnimationGenerationState",
    "PromptReorderGeometryGenerationState",
    "PromptReorderKeyboardState",
    "PromptReorderOverlayPositionGeometryKey",
    "PromptReorderOverlayRefreshGeometryKey",
    "PromptReorderPointerState",
    "PromptReorderPreparedGeometryIdentity",
    "PromptReorderPreviewTargetIdentity",
    "PromptReorderPreviewTargetState",
    "ReorderBaseDragGeometryKey",
    "ReorderChipWidgetGeometryKey",
    "ReorderChipWidgetVisualRectKey",
    "ReorderLayoutViewKey",
    "ReorderLiveVisualGeometryKey",
    "ReorderPreviewSnapshotKey",
    "ReorderSourceFingerprint",
    "reorder_base_drag_geometry_key",
    "reorder_chip_widget_geometry_key",
    "reorder_live_visual_geometry_key",
    "reorder_overlay_position_geometry_key",
    "reorder_overlay_refresh_geometry_key",
    "reorder_source_fingerprint",
]
