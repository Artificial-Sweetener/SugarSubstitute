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

"""Verify atomic reorder preview-geometry transition ownership."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_geometry_builder import (
    PromptReorderDropGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_geometry_publication import (
    PromptReorderDropGeometryPublisher,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry_owner import (
    PromptReorderGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_identity import (
    reorder_interaction_base_drag_geometry_key,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_geometry_transition import (
    PromptReorderPreviewGeometryTransitionOwner,
)


class _GeometryOwner:
    """Return configured preview and base-drag geometry while counting work."""

    def __init__(self) -> None:
        """Initialize stable outputs and call counters."""

        self.preview_snapshot = _chip_snapshot((1,))
        self.base_snapshot = _chip_snapshot((0,))
        self.placement_snapshot = _placement_snapshot()
        self.preview_calls = 0
        self.base_calls = 0
        self.placement_calls = 0

    def preview_chip_snapshot(
        self, **_facts: object
    ) -> PromptReorderChipGeometrySnapshot:
        """Return the configured preview snapshot."""

        self.preview_calls += 1
        return self.preview_snapshot

    def base_drag_chip_snapshot(
        self,
        **_facts: object,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return the configured base-drag snapshot."""

        self.base_calls += 1
        return self.base_snapshot

    def base_drag_placement_snapshot(
        self,
        **_facts: object,
    ) -> PromptReorderPlacementSnapshot:
        """Return the configured placement snapshot."""

        self.placement_calls += 1
        return self.placement_snapshot


class _DropPublisher:
    """Return synchronized drop geometry while counting publication work."""

    def __init__(self) -> None:
        """Initialize a zero-call publisher."""

        self.calls = 0

    def publish(
        self,
        snapshot: PromptReorderPlacementSnapshot,
        **_facts: object,
    ) -> PromptReorderDropGeometry:
        """Return the supplied placement snapshot as one empty-lane publication."""

        self.calls += 1
        return PromptReorderDropGeometry(
            placement_snapshot=snapshot,
            target_visuals=(),
            lanes=(),
        )


def test_preview_geometry_transition_reuses_exact_base_generation() -> None:
    """An equal revision key should reuse every prepared base-drag value."""

    geometry = _GeometryOwner()
    drops = _DropPublisher()
    viewport_identity = ("viewport", 320, 180)
    base_snapshot = _preview_snapshot("alpha")
    state = PromptReorderInteractionGeometryState(
        base_drag_layout_view=_layout(),
        base_drag_snapshot=base_snapshot,
        base_drag_chip_geometry_snapshot=geometry.base_snapshot,
        placement_snapshot=geometry.placement_snapshot,
    )
    base_key = reorder_interaction_base_drag_geometry_key(
        state,
        viewport_identity=viewport_identity,
        dragged_segment_index=0,
    )
    assert base_key is not None
    state = PromptReorderInteractionGeometryState(
        base_drag_layout_view=state.base_drag_layout_view,
        base_drag_snapshot=base_snapshot,
        base_drag_chip_geometry_snapshot=geometry.base_snapshot,
        placement_snapshot=geometry.placement_snapshot,
        last_base_drag_geometry_key=base_key,
    )

    transition = _owner(geometry, drops).build(
        state,
        dragged_segment_index=0,
        active_target=None,
        viewport_identity=viewport_identity,
        gesture_id=4,
        event_id=7,
    )

    assert transition.base_drag_geometry_reused is True
    assert transition.base_drag_geometry_rebuilt is False
    assert transition.state.base_drag_chip_geometry_snapshot is geometry.base_snapshot
    assert transition.state.placement_snapshot is geometry.placement_snapshot
    assert geometry.base_calls == 0
    assert geometry.placement_calls == 0
    assert drops.calls == 0


def test_preview_geometry_transition_rebuilds_base_generation_atomically() -> None:
    """Changed base inputs should publish chips, placements, and lanes together."""

    geometry = _GeometryOwner()
    drops = _DropPublisher()
    state = PromptReorderInteractionGeometryState(
        base_drag_layout_view=_layout(),
        base_drag_snapshot=_preview_snapshot("alpha"),
    )

    transition = _owner(geometry, drops).build(
        state,
        dragged_segment_index=0,
        active_target=None,
        viewport_identity=("viewport", 320, 180),
        gesture_id=4,
        event_id=7,
    )

    assert transition.base_drag_geometry_reused is False
    assert transition.base_drag_geometry_rebuilt is True
    assert transition.state.base_drag_chip_geometry_snapshot is geometry.base_snapshot
    assert transition.state.placement_snapshot is geometry.placement_snapshot
    assert transition.state.last_base_drag_geometry_key is not None
    assert geometry.base_calls == 1
    assert geometry.placement_calls == 1
    assert drops.calls == 1


def test_preview_geometry_transition_clears_stale_values_without_inputs() -> None:
    """Retired snapshots should clear every derived preview and placement value."""

    geometry = _GeometryOwner()
    drops = _DropPublisher()
    stale_preview = _chip_snapshot((3,))
    state = PromptReorderInteractionGeometryState(
        preview_chip_geometry_snapshot=stale_preview,
        base_drag_chip_geometry_snapshot=geometry.base_snapshot,
        placement_snapshot=geometry.placement_snapshot,
    )

    transition = _owner(geometry, drops).build(
        state,
        dragged_segment_index=None,
        active_target=None,
        viewport_identity=("viewport", 320, 180),
        gesture_id=None,
        event_id=None,
    )

    assert transition.previous_preview_chip_snapshot is stale_preview
    assert transition.state.preview_chip_geometry_snapshot is None
    assert transition.state.base_drag_chip_geometry_snapshot is None
    assert transition.state.placement_snapshot is None
    assert transition.state.last_base_drag_geometry_key is None
    assert geometry.preview_calls == 0
    assert geometry.base_calls == 0
    assert drops.calls == 0


def test_drop_geometry_publisher_reports_prepared_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drop publication should report the exact synchronized lane structure."""

    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "substitute.presentation.editor.prompt_editor.projection."
        "reorder_drop_geometry_publication.log_reorder_drag_event",
        lambda event, **context: events.append((event, context)),
    )

    publication = PromptReorderDropGeometryPublisher().publish(
        _placement_snapshot(),
        gesture_id=4,
        event_id=7,
    )

    assert len(publication.placement_snapshot.placements) == 1
    assert len(publication.target_visuals) == 1
    assert len(publication.lanes) == 1
    assert events == [
        (
            "placement_geometry.snapshot",
            {
                "gesture_id": 4,
                "event_id": 7,
                "placement_count": 1,
                "row_lane_count": 1,
                "blank_lane_count": 0,
                "visual_line_count": 1,
                "layout_width": "120.00",
                "content_height": "24.00",
            },
        )
    ]


def _owner(
    geometry: _GeometryOwner,
    drops: _DropPublisher,
) -> PromptReorderPreviewGeometryTransitionOwner:
    """Return the transition owner over focused test doubles."""

    return PromptReorderPreviewGeometryTransitionOwner(
        geometry_owner=cast(PromptReorderGeometryOwner, geometry),
        drop_geometry=cast(PromptReorderDropGeometryPublisher, drops),
    )


def _layout() -> PromptReorderLayoutView:
    """Return one deterministic row layout."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0,)),),
        gaps=(),
    )


def _preview_snapshot(text: str) -> PromptReorderPreviewSnapshot:
    """Return one minimal semantic snapshot."""

    return PromptReorderPreviewSnapshot(
        text=text,
        chip_ranges_by_index={0: (0, len(text))},
        chip_rendered_ranges_by_index={0: (0, len(text))},
        chip_owned_ranges_by_index={0: ((0, len(text)),)},
        gap_ranges_by_index={},
    )


def _chip_snapshot(indices: tuple[int, ...]) -> PromptReorderChipGeometrySnapshot:
    """Return one empty but identity-bearing chip geometry snapshot."""

    return PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={},
        ordered_chip_indices=indices,
        visual_line_count=1,
        layout_width=120.0,
        content_height=24.0,
        scroll_offset=0.0,
    )


def _placement_snapshot() -> PromptReorderPlacementSnapshot:
    """Return one row placement for publication tests."""

    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = PromptReorderPlacementGeometry(
        placement_id=PromptReorderPlacementId(
            target_kind="line",
            row_index=0,
            insertion_index=0,
            gap_index=None,
            blank_line_index=None,
            visual_line_index=0,
            ordinal=0,
        ),
        target=target,
        hit_rect=QRectF(0.0, 0.0, 20.0, 24.0),
        insertion_anchor_rect=QRectF(10.0, 0.0, 1.0, 24.0),
        visual_line_rect=QRectF(0.0, 0.0, 120.0, 24.0),
        expected_landing_rect=None,
        source_before=None,
        source_after=None,
    )
    return PromptReorderPlacementSnapshot(
        placements=(placement,),
        visual_line_count=1,
        layout_width=120.0,
        content_height=24.0,
    )
