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

"""Verify prepared prompt-reorder preview visual publication ownership."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest
from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_geometry_transition import (
    PromptReorderGeometryRefresh,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    PromptReorderOverlayPositionGeometryKey,
)


class _FakePreviewGeometry:
    """Record preparation calls while publishing replaceable immutable state."""

    def __init__(self) -> None:
        """Initialize an empty interaction publication."""

        self.state = PromptReorderInteractionGeometryState()
        self.refresh_count = 0

    def refresh_preview_geometry(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderGeometryRefresh:
        """Return deterministic empty geometry and record the structural build."""

        _ = (
            dragged_segment_index,
            active_target,
            viewport_identity,
            gesture_id,
            event_id,
        )
        self.refresh_count += 1
        return PromptReorderGeometryRefresh(
            state=self.state,
            previous_preview_chip_snapshot=None,
            preview_chip_snapshot=None,
            base_drag_chip_snapshot=None,
            placement_snapshot=None,
            drop_target_visuals=(),
            drop_target_lanes=(),
            preview_geometry_identity=None,
            base_drag_geometry_reused=False,
            base_drag_geometry_rebuilt=False,
        )


def test_preview_visual_owner_reuses_exact_prepared_identity() -> None:
    """Repeated refresh requests should publish once and reuse by identity."""

    geometry = _FakePreviewGeometry()
    owner = _owner(geometry)
    viewport = _viewport()

    first = owner.prepare(
        dragged_segment_index=1,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        viewport_identity=viewport,
        gesture_id=7,
        event_id=9,
    )
    second = owner.prepare(
        dragged_segment_index=1,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        viewport_identity=viewport,
        gesture_id=7,
        event_id=10,
    )

    assert first.rebuilt is True
    assert second.rebuilt is False
    assert second.publication is first.publication
    assert geometry.refresh_count == 1
    assert owner.metrics.full_build_count == 1
    assert owner.metrics.unchanged_reuse_count == 1


def test_active_placement_publication_does_not_invalidate_prepared_visuals() -> None:
    """Pointer-only placement state must not add geometry work to pointer motion."""

    geometry = _FakePreviewGeometry()
    owner = _owner(geometry)
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    viewport = _viewport()
    first = owner.prepare(
        dragged_segment_index=1,
        active_target=target,
        viewport_identity=viewport,
        gesture_id=7,
        event_id=9,
    )
    geometry.state = replace(
        geometry.state,
        active_placement=_placement(),
    )
    second = owner.prepare(
        dragged_segment_index=1,
        active_target=target,
        viewport_identity=viewport,
        gesture_id=7,
        event_id=9,
    )

    assert second.rebuilt is False
    assert second.publication is first.publication
    assert geometry.refresh_count == 1


def test_geometry_free_height_change_rekeys_without_rebuilding() -> None:
    """Empty preview geometry should survive a queued height-only shell resize."""

    geometry = _FakePreviewGeometry()
    owner = _owner(geometry)
    first = owner.prepare(
        dragged_segment_index=None,
        active_target=None,
        viewport_identity=_viewport(),
        gesture_id=7,
        event_id=9,
    )
    resized_viewport = replace(
        _viewport(),
        viewport_height=164,
        content_height=156,
    )

    second = owner.prepare(
        dragged_segment_index=None,
        active_target=None,
        viewport_identity=resized_viewport,
        gesture_id=7,
        event_id=10,
    )

    assert second.rebuilt is False
    assert second.publication is not first.publication
    assert second.publication.geometry is first.publication.geometry
    assert second.publication.key.viewport_identity == resized_viewport
    assert geometry.refresh_count == 1
    assert owner.metrics.full_build_count == 1
    assert owner.metrics.geometry_free_height_reuse_count == 1


def test_geometry_free_width_change_still_rebuilds() -> None:
    """Width changes must retain geometry ownership even when output is empty."""

    geometry = _FakePreviewGeometry()
    owner = _owner(geometry)
    owner.prepare(
        dragged_segment_index=None,
        active_target=None,
        viewport_identity=_viewport(),
        gesture_id=7,
        event_id=9,
    )

    outcome = owner.prepare(
        dragged_segment_index=None,
        active_target=None,
        viewport_identity=replace(
            _viewport(),
            viewport_width=304,
            content_width=296,
        ),
        gesture_id=7,
        event_id=10,
    )

    assert outcome.rebuilt is True
    assert geometry.refresh_count == 2
    assert owner.metrics.geometry_free_height_reuse_count == 0


def test_preview_visual_publication_is_frozen_and_mapping_is_read_only() -> None:
    """Readers must not mutate a publication or its visual mapping."""

    owner = _owner(_FakePreviewGeometry())
    publication = owner.prepare(
        dragged_segment_index=None,
        active_target=None,
        viewport_identity=_viewport(),
        gesture_id=None,
        event_id=None,
    ).publication

    with pytest.raises(FrozenInstanceError):
        publication.key = publication.key  # type: ignore[misc]
    with pytest.raises(TypeError):
        publication.visuals_by_index[0] = None  # type: ignore[index]


def _owner(geometry: _FakePreviewGeometry) -> PromptReorderPreviewVisualOwner:
    """Build the preview visual owner over focused geometry callbacks."""

    return PromptReorderPreviewVisualOwner(
        geometry_state=lambda: geometry.state,
        refresh_preview_geometry=geometry.refresh_preview_geometry,
    )


def _viewport() -> PromptReorderOverlayPositionGeometryKey:
    """Return stable viewport identity for prepared visual tests."""

    return PromptReorderOverlayPositionGeometryKey(
        viewport_left=0,
        viewport_top=0,
        viewport_width=320,
        viewport_height=180,
        content_left=4,
        content_top=4,
        content_width=312,
        content_height=172,
        scroll_offset=0,
    )


def _placement() -> PromptReorderPlacementGeometry:
    """Return one pointer-only placement publication."""

    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    rect = QRectF(0.0, 0.0, 20.0, 20.0)
    return PromptReorderPlacementGeometry(
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
        hit_rect=rect,
        insertion_anchor_rect=rect,
        visual_line_rect=rect,
        expected_landing_rect=None,
        source_before=None,
        source_after=None,
    )
