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

"""Cover projection-owned prompt reorder interaction geometry boundaries."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderGapView,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreparedStateView,
    PromptReorderPreviewSnapshot,
    PromptReorderRowView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry_owner import (
    PromptReorderGeometryEnvironment,
    PromptReorderGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drag_geometry_preparation import (
    PromptReorderDragGeometryPreparationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_geometry_publication import (
    PromptReorderDropGeometryPublisher,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_identity import (
    reorder_preview_geometry_matches_target,
    reorder_preview_target_identity,
    reorder_preview_target_identity_context,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection_owner import (
    PromptReorderPreviewProjectionOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.applicator import (
    PromptProjectionApplicator,
)
from substitute.presentation.editor.prompt_editor.projection.builder import (
    PromptProjectionBuilder,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)


class _FakeLayoutPolicy:
    """Provide deterministic reorder layouts for geometry-owner tests."""

    def build_base_drag_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        dragged_segment_index: int,
    ) -> PromptReorderPreparedStateView:
        """Return matching fake layout and state with the held chip removed."""

        _ = document_view
        remaining = tuple(
            index
            for index in state_view.ordered_chip_indices
            if index != dragged_segment_index
        )
        reorder_state = PromptReorderStateView(
            ordered_chip_indices=remaining,
            separator_slots=state_view.separator_slots[: max(0, len(remaining) - 1)],
            has_trailing_comma=state_view.has_trailing_comma,
        )
        return PromptReorderPreparedStateView(
            reorder_state=reorder_state,
            layout_view=PromptReorderLayoutView(
                rows=tuple(
                    replace(
                        row,
                        chip_indices=tuple(
                            index
                            for index in row.chip_indices
                            if index != dragged_segment_index
                        ),
                    )
                    for row in current_layout_view.rows
                    if row.chip_indices != (dragged_segment_index,)
                ),
                gaps=current_layout_view.gaps,
                partition_index_by_chip_index=(
                    current_layout_view.partition_index_by_chip_index
                ),
                prefix_text=current_layout_view.prefix_text,
                suffix_text=current_layout_view.suffix_text,
            ),
        )

    def build_preview_drop_state(
        self,
        document_view: PromptDocumentView,
        base_drag_state_view: PromptReorderPreparedStateView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderPreparedStateView:
        """Return matching fake state and layout for one target."""

        _ = document_view
        assert isinstance(drop_target, PromptLineDropTarget)
        ordered = list(base_drag_state_view.reorder_state.ordered_chip_indices)
        ordered.insert(drop_target.insertion_index, dragged_segment_index)
        reorder_state = PromptReorderStateView(
            ordered_chip_indices=tuple(ordered),
            separator_slots=tuple(", " for _ in ordered[:-1]),
            has_trailing_comma=base_drag_state_view.reorder_state.has_trailing_comma,
        )
        layout_view = PromptReorderLayoutView(
            rows=(
                PromptReorderRowView(
                    row_index=drop_target.row_index,
                    chip_indices=tuple(ordered),
                ),
            ),
            gaps=base_drag_state_view.layout_view.gaps,
        )
        return PromptReorderPreparedStateView(
            reorder_state=reorder_state,
            layout_view=layout_view,
        )

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the flattened layout order."""

        return tuple(index for row in layout_view.rows for index in row.chip_indices)


class _FakeDragGeometrySource:
    """Return exact live geometry publications selected by each test."""

    def __init__(
        self,
        *,
        chip_snapshot: PromptReorderChipGeometrySnapshot,
        placement_snapshot: PromptReorderPlacementSnapshot,
    ) -> None:
        """Store immutable geometry publications and query counters."""

        self.chip_snapshot = chip_snapshot
        self.placement_snapshot = placement_snapshot
        self.live_placement_query_count = 0

    def live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Return the prepared live placement publication."""

        _ = layout_view
        _ = chip_geometry_snapshot
        _ = gap_ranges_by_index
        self.live_placement_query_count += 1
        return self.placement_snapshot


def _unused_geometry_environment(reason: str) -> PromptReorderGeometryEnvironment:
    """Reject geometry work in an identity-only owner test."""

    raise AssertionError(f"geometry environment should not be requested: {reason}")


def _geometry_owner() -> PromptReorderGeometryOwner:
    """Build the real focused owner without a widget-host protocol."""

    preview_projection = PromptReorderPreviewProjectionOwner(
        projection_applicator=PromptProjectionApplicator(PromptProjectionBuilder()),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    return PromptReorderGeometryOwner(
        environment=_unused_geometry_environment,
        preview_projection=preview_projection,
    )


def _document_view(source_text: str) -> PromptDocumentView:
    """Return a minimal prompt document view for geometry identity tests."""

    return PromptDocumentView(
        source_text=source_text,
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(len(source_text)),
        has_trailing_comma=False,
    )


def _layout_view() -> PromptReorderLayoutView:
    """Return a minimal one-row reorder layout."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1, 2)),),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text=", ",
                blank_line_count=0,
            ),
        ),
    )


def _state_view() -> PromptReorderStateView:
    """Return a minimal authoritative reorder state."""

    return PromptReorderStateView(
        ordered_chip_indices=(0, 1, 2),
        separator_slots=(", ", ", "),
        has_trailing_comma=False,
    )


def _empty_chip_snapshot() -> PromptReorderChipGeometrySnapshot:
    """Return a stable live chip publication for preparation-owner tests."""

    return PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={},
        ordered_chip_indices=(0, 1, 2),
        visual_line_count=1,
        layout_width=320.0,
        content_height=40.0,
        scroll_offset=0.0,
    )


def _placement_snapshot(*, populated: bool) -> PromptReorderPlacementSnapshot:
    """Return an empty or single-row placement publication."""

    placements: tuple[PromptReorderPlacementGeometry, ...] = ()
    if populated:
        target = PromptLineDropTarget(row_index=0, insertion_index=0)
        placements = (
            PromptReorderPlacementGeometry(
                placement_id=PromptReorderPlacementId(
                    target_kind=type(target).__name__,
                    row_index=0,
                    insertion_index=0,
                    gap_index=None,
                    blank_line_index=None,
                    visual_line_index=0,
                    ordinal=0,
                ),
                target=target,
                hit_rect=QRectF(0.0, 0.0, 20.0, 20.0),
                insertion_anchor_rect=QRectF(0.0, 0.0, 2.0, 20.0),
                visual_line_rect=QRectF(0.0, 0.0, 320.0, 20.0),
                expected_landing_rect=None,
                source_before=0,
                source_after=0,
            ),
        )
    return PromptReorderPlacementSnapshot(
        placements=placements,
        visual_line_count=1,
        layout_width=320.0,
        content_height=40.0,
    )


def _session_geometry_state() -> PromptReorderInteractionGeometryState:
    """Return one coherent interaction state before drag preparation."""

    layout_view = _layout_view()
    reorder_state = _state_view()
    state = PromptReorderInteractionGeometryState(
        document_view=_document_view("alpha, beta, gamma"),
        original_layout_view=layout_view,
        current_layout_view=layout_view,
        original_reorder_state=reorder_state,
        current_reorder_state=reorder_state,
        initial_ordered_indices=(0, 1, 2),
        ordered_segment_indices=(0, 1, 2),
        preview_layout_view=layout_view,
        preview_reorder_state=reorder_state,
    )
    identity = reorder_preview_target_identity(
        state,
        dragged_segment_index=0,
        target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
        preview_layout_view=layout_view,
    )
    return replace(
        state,
        preview_layout_target_identity=identity,
        preview_geometry_target_identity=identity,
    )


def test_reorder_geometry_state_rejects_stale_preview_identity_atomically() -> None:
    """A new session should atomically retire every previous preview identity."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    layout_view = _layout_view()
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        layout_view,
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    assert (
        owner.begin_drag(
            dragged_segment_index=0,
            gesture_id=None,
            event_id=None,
        )
        is not None
    )
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=target,
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    preview_identity = owner.state.preview_layout_target_identity
    assert preview_identity is not None
    identity_context = reorder_preview_target_identity_context(
        preview_identity,
        prefix="preview_geometry_target",
    )
    assert "alpha, beta, gamma" not in repr(identity_context)
    assert preview_identity == reorder_preview_target_identity(
        owner.state,
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )

    owner.set_session(
        _document_view("alpha, beta, gamma, delta"),
        layout_view,
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    assert owner.state.preview_layout_target_identity is None
    assert owner.state.preview_geometry_target_identity is None
    assert not reorder_preview_geometry_matches_target(
        owner.state,
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )


def test_reorder_geometry_state_is_frozen_and_replaced_per_transition() -> None:
    """Callers should observe complete publications and cannot mutate them."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    initial_state = owner.state
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        _layout_view(),
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    session_state = owner.state

    assert session_state is not initial_state
    assert session_state.current_layout_view is session_state.original_layout_view
    assert session_state.current_reorder_state is session_state.original_reorder_state
    assert session_state.ordered_segment_indices == (0, 1, 2)
    with pytest.raises(FrozenInstanceError):
        setattr(session_state, "ordered_segment_indices", (2, 1, 0))
    assert owner.state is session_state


def test_reorder_geometry_commit_and_restore_publish_coherent_state() -> None:
    """Commit and cancel transitions should never expose mixed layout generations."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    original_layout = _layout_view()
    original_state = _state_view()
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        original_layout,
        original_state,
        ordered_indices=(0, 1, 2),
    )
    owner.begin_drag(dragged_segment_index=0, gesture_id=None, event_id=None)
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    preview_state = owner.state

    assert preview_state.preview_layout_view is not None
    assert preview_state.preview_reorder_state is not None
    assert preview_state.preview_layout_target_identity is not None
    assert preview_state.ordered_segment_indices == (1, 0, 2)
    assert owner.commit_preview_layout()
    committed_state = owner.state
    assert committed_state is not preview_state
    assert committed_state.current_layout_view is preview_state.preview_layout_view
    assert committed_state.current_reorder_state is preview_state.preview_reorder_state
    assert committed_state.ordered_segment_indices == (1, 0, 2)

    owner.clear_drag_context(preserve_preview=True)
    completed_state = owner.state
    assert completed_state.current_layout_view is committed_state.current_layout_view
    assert (
        completed_state.current_reorder_state is committed_state.current_reorder_state
    )
    assert completed_state.preview_layout_view is committed_state.preview_layout_view
    assert (
        completed_state.preview_reorder_state is committed_state.preview_reorder_state
    )
    assert completed_state.base_drag_layout_view is None
    assert completed_state.base_drag_reorder_state is None
    assert completed_state.placement_snapshot is None

    owner.restore_original_layout()
    restored_state = owner.state
    assert restored_state.current_layout_view is original_layout
    assert restored_state.current_reorder_state is original_state
    assert restored_state.preview_layout_view is None
    assert restored_state.preview_reorder_state is None
    assert restored_state.preview_layout_target_identity is None
    assert restored_state.preview_geometry_target_identity is None
    assert restored_state.ordered_segment_indices == (0, 1, 2)


def test_preview_snapshot_publication_adopts_identity_and_order_atomically() -> None:
    """A prepared preview should replace snapshot, identity, and order together."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        _layout_view(),
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    owner.begin_drag(dragged_segment_index=0, gesture_id=None, event_id=None)
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=target,
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    snapshot = PromptReorderPreviewSnapshot(
        text="beta, alpha, gamma",
        chip_ranges_by_index={},
        chip_rendered_ranges_by_index={},
        chip_owned_ranges_by_index={},
        gap_ranges_by_index={},
    )
    previous_state = owner.state

    owner.set_preview_snapshots(
        snapshot,
        base_drag_snapshot=snapshot,
        ordered_chip_indices=(1, 0, 2),
        dragged_segment_index=0,
        active_target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )

    result = owner.state
    assert result is not previous_state
    assert result.preview_snapshot is snapshot
    assert result.base_drag_snapshot is snapshot
    assert result.ordered_segment_indices == (1, 0, 2)
    assert result.preview_layout_target_identity == reorder_preview_target_identity(
        result,
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )


def test_preview_snapshot_clear_retires_only_stale_geometry_identity() -> None:
    """Clearing a frame should preserve layout truth while rejecting stale geometry."""

    state = _session_geometry_state()
    assert state.document_view is not None
    assert state.current_layout_view is not None
    assert state.current_reorder_state is not None
    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    owner.set_session(
        state.document_view,
        state.current_layout_view,
        state.current_reorder_state,
        ordered_indices=state.ordered_segment_indices,
    )
    owner.begin_drag(dragged_segment_index=0, gesture_id=None, event_id=None)
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    owner.set_preview_snapshots(
        None,
        base_drag_snapshot=None,
        ordered_chip_indices=(2, 1, 0),
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
    )

    result = owner.state
    assert result.preview_snapshot is None
    assert result.base_drag_snapshot is None
    assert result.ordered_segment_indices == (1, 0, 2)
    assert result.preview_layout_target_identity is not None
    assert result.preview_geometry_target_identity is None


def test_drag_geometry_preparation_begins_one_coherent_drag_generation() -> None:
    """Base layout, reorder state, and stale preview values should change atomically."""

    geometry_source = _FakeDragGeometrySource(
        chip_snapshot=_empty_chip_snapshot(),
        placement_snapshot=_placement_snapshot(populated=False),
    )
    owner = PromptReorderDragGeometryPreparationOwner(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=geometry_source,
        drop_geometry=PromptReorderDropGeometryPublisher(),
    )
    missing_session = PromptReorderInteractionGeometryState()

    assert (
        owner.begin_drag(
            missing_session,
            dragged_segment_index=0,
            gesture_id=None,
            event_id=None,
        )
        is missing_session
    )

    state = _session_geometry_state()
    next_state = owner.begin_drag(
        state,
        dragged_segment_index=0,
        gesture_id=3,
        event_id=5,
    )

    assert next_state is not state
    assert next_state.base_drag_layout_view is not None
    assert next_state.base_drag_layout_view.rows[0].chip_indices == (1, 2)
    assert next_state.base_drag_reorder_state is not None
    assert next_state.base_drag_reorder_state.ordered_chip_indices == (1, 2)
    assert next_state.preview_layout_view is None
    assert next_state.preview_reorder_state is None
    assert next_state.preview_layout_target_identity is None
    assert next_state.preview_geometry_target_identity is None
    assert next_state.placement_snapshot is None
    assert next_state.active_placement is None


def test_drag_geometry_preparation_primes_only_nonempty_painted_geometry() -> None:
    """Placement priming should be identity-safe and publish lanes atomically."""

    geometry_source = _FakeDragGeometrySource(
        chip_snapshot=_empty_chip_snapshot(),
        placement_snapshot=_placement_snapshot(populated=False),
    )
    owner = PromptReorderDragGeometryPreparationOwner(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=geometry_source,
        drop_geometry=PromptReorderDropGeometryPublisher(),
    )
    state = _session_geometry_state()
    chip_snapshot = geometry_source.chip_snapshot

    assert (
        owner.prime_from_painted_projection(
            state,
            chip_geometry_snapshot=chip_snapshot,
            gap_ranges_by_index={},
            gesture_id=None,
            event_id=None,
        )
        is state
    )
    assert geometry_source.live_placement_query_count == 0

    drag_state = owner.begin_drag(
        state,
        dragged_segment_index=0,
        gesture_id=None,
        event_id=None,
    )
    assert (
        owner.prime_from_painted_projection(
            drag_state,
            chip_geometry_snapshot=chip_snapshot,
            gap_ranges_by_index={},
            gesture_id=None,
            event_id=None,
        )
        is drag_state
    )
    assert geometry_source.live_placement_query_count == 1

    geometry_source.placement_snapshot = _placement_snapshot(populated=True)
    primed_state = owner.prime_from_painted_projection(
        drag_state,
        chip_geometry_snapshot=chip_snapshot,
        gap_ranges_by_index={},
        gesture_id=3,
        event_id=6,
    )

    assert primed_state is not drag_state
    assert primed_state.placement_snapshot is not None
    assert len(primed_state.placement_snapshot.placements) == 1
    assert len(primed_state.drop_target_visuals) == 1
    assert len(primed_state.drop_target_lanes) == 1
    assert geometry_source.live_placement_query_count == 2
