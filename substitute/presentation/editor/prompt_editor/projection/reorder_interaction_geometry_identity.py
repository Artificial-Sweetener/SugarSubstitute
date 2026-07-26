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

"""Build immutable identities for prompt reorder interaction geometry."""

from __future__ import annotations

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
)

from .observability import reorder_drag_target_kind
from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_state import (
    PromptReorderGeometryGenerationState,
    PromptReorderPreparedGeometryIdentity,
    PromptReorderPreviewTargetIdentity,
    PromptReorderPreviewTargetState,
    ReorderBaseDragGeometryKey,
    ReorderLayoutViewKey,
    ReorderPreviewSnapshotKey,
    ReorderSourceFingerprint,
    reorder_base_drag_geometry_key,
    reorder_source_fingerprint,
)


def reorder_preview_target_identity(
    state: PromptReorderInteractionGeometryState,
    *,
    dragged_segment_index: int | None,
    target: PromptReorderDropTarget | None,
    viewport_identity: object | None,
    preview_layout_view: PromptReorderLayoutView | None = None,
) -> PromptReorderPreviewTargetIdentity | None:
    """Build target identity from one coherent interaction publication."""

    if dragged_segment_index is None or target is None:
        return None
    preview_layout = (
        state.preview_layout_view
        if preview_layout_view is None
        else preview_layout_view
    )
    return PromptReorderPreviewTargetIdentity(
        source_fingerprint=reorder_interaction_source_fingerprint(state),
        projection_identity=reorder_layout_view_key(state.current_layout_view),
        dragged_segment_index=dragged_segment_index,
        target=target,
        preview_layout_key=reorder_layout_view_key(preview_layout),
        base_drag_layout_key=reorder_layout_view_key(state.base_drag_layout_view),
        viewport_identity=viewport_identity,
    )


def reorder_preview_geometry_matches_target(
    state: PromptReorderInteractionGeometryState,
    *,
    dragged_segment_index: int | None,
    target: PromptReorderDropTarget | None,
    viewport_identity: object | None,
) -> bool:
    """Return whether published preview geometry belongs to one active target."""

    expected_identity = reorder_preview_target_identity(
        state,
        dragged_segment_index=dragged_segment_index,
        target=target,
        viewport_identity=viewport_identity,
    )
    return (
        expected_identity is not None
        and state.preview_geometry_target_identity == expected_identity
    )


def reorder_preview_target_identity_context(
    identity: PromptReorderPreviewTargetIdentity | None,
    *,
    prefix: str,
) -> dict[str, object]:
    """Return prompt-safe structured context for one preview target identity."""

    if identity is None:
        return {
            f"{prefix}_dragged_segment_index": None,
            f"{prefix}_target_kind": "none",
            f"{prefix}_source_layout_key": "none",
        }
    return {
        f"{prefix}_dragged_segment_index": identity.dragged_segment_index,
        f"{prefix}_target_kind": reorder_drag_target_kind(identity.target),
        f"{prefix}_source_layout_key": repr(identity.source_fingerprint),
        f"{prefix}_preview_layout_key": repr(identity.preview_layout_key),
        f"{prefix}_base_drag_layout_key": repr(identity.base_drag_layout_key),
        f"{prefix}_viewport_identity": repr(identity.viewport_identity),
    }


def reorder_prepared_geometry_identity(
    state: PromptReorderInteractionGeometryState,
    *,
    dragged_segment_index: int | None,
    active_target: PromptReorderDropTarget | None,
    viewport_identity: object | None,
) -> PromptReorderPreparedGeometryIdentity:
    """Return complete prepared-geometry identity for stale-safe refresh."""

    return PromptReorderPreparedGeometryIdentity(
        source_fingerprint=reorder_interaction_source_fingerprint(state),
        projection_identity=reorder_layout_view_key(state.current_layout_view),
        dragged_segment_index=dragged_segment_index,
        active_target=active_target,
        preview_layout_key=reorder_layout_view_key(state.preview_layout_view),
        base_drag_layout_key=reorder_layout_view_key(state.base_drag_layout_view),
        preview_snapshot_key=reorder_preview_snapshot_key(state.preview_snapshot),
        base_drag_snapshot_key=reorder_preview_snapshot_key(state.base_drag_snapshot),
        viewport_identity=viewport_identity,
    )


def reorder_preview_target_state(
    state: PromptReorderInteractionGeometryState,
    *,
    dragged_segment_index: int | None,
    active_target: PromptReorderDropTarget | None,
) -> PromptReorderPreviewTargetState:
    """Return display-only target state derived from one publication."""

    return PromptReorderPreviewTargetState(
        dragged_segment_index=dragged_segment_index,
        active_target=active_target,
        ordered_segment_indices=state.ordered_segment_indices,
        preview_layout_target_identity=state.preview_layout_target_identity,
        preview_geometry_target_identity=state.preview_geometry_target_identity,
        has_preview_layout=state.preview_layout_view is not None,
        has_base_drag_layout=state.base_drag_layout_view is not None,
    )


def reorder_geometry_generation_state(
    state: PromptReorderInteractionGeometryState,
    *,
    generation_id: int,
    dragged_segment_index: int | None,
    active_target: PromptReorderDropTarget | None,
    viewport_identity: object,
) -> PromptReorderGeometryGenerationState:
    """Return the prepared-geometry generation visible to non-widget readers."""

    return PromptReorderGeometryGenerationState(
        generation_id=generation_id,
        prepared_geometry_identity=reorder_prepared_geometry_identity(
            state,
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            viewport_identity=viewport_identity,
        ),
        base_drag_geometry_key=reorder_interaction_base_drag_geometry_key(
            state,
            viewport_identity=viewport_identity,
            dragged_segment_index=dragged_segment_index,
        ),
    )


def reorder_interaction_base_drag_geometry_key(
    state: PromptReorderInteractionGeometryState,
    *,
    viewport_identity: object,
    dragged_segment_index: int | None,
) -> ReorderBaseDragGeometryKey | None:
    """Return complete identity for reusable stable base-drag geometry."""

    if state.base_drag_layout_view is None or state.base_drag_snapshot is None:
        return None
    return reorder_base_drag_geometry_key(
        base_drag_layout_key=reorder_layout_view_key(state.base_drag_layout_view),
        base_drag_snapshot_key=reorder_preview_snapshot_key(state.base_drag_snapshot),
        viewport_identity=viewport_identity,
        dragged_segment_index=dragged_segment_index,
    )


def reorder_layout_view_key(
    layout_view: PromptReorderLayoutView | None,
) -> ReorderLayoutViewKey | None:
    """Return a prompt-safe key for one reorder layout view."""

    if layout_view is None:
        return None
    return (
        tuple((row.row_index, tuple(row.chip_indices)) for row in layout_view.rows),
        tuple(
            (
                gap.gap_index,
                gap.separator_text,
                gap.blank_line_count,
                gap.placement.value,
            )
            for gap in layout_view.gaps
        ),
    )


def reorder_preview_snapshot_key(
    snapshot: PromptReorderPreviewSnapshot | None,
) -> ReorderPreviewSnapshotKey | None:
    """Return a prompt-safe key for one preview snapshot."""

    if snapshot is None:
        return None
    return (
        reorder_source_fingerprint(snapshot.text),
        tuple(
            sorted(
                (chip_index, start, end)
                for chip_index, (
                    start,
                    end,
                ) in snapshot.chip_rendered_ranges_by_index.items()
            )
        ),
        tuple(
            sorted(
                (gap_index, start, end)
                for gap_index, (start, end) in snapshot.gap_ranges_by_index.items()
            )
        ),
    )


def reorder_interaction_source_fingerprint(
    state: PromptReorderInteractionGeometryState,
) -> ReorderSourceFingerprint:
    """Return prompt-safe source identity for one immutable publication."""

    if state.document_view is None:
        return reorder_source_fingerprint("")
    return reorder_source_fingerprint(state.document_view.source_text)


__all__ = [
    "reorder_geometry_generation_state",
    "reorder_interaction_base_drag_geometry_key",
    "reorder_interaction_source_fingerprint",
    "reorder_layout_view_key",
    "reorder_prepared_geometry_identity",
    "reorder_preview_geometry_matches_target",
    "reorder_preview_snapshot_key",
    "reorder_preview_target_identity",
    "reorder_preview_target_identity_context",
    "reorder_preview_target_state",
]
