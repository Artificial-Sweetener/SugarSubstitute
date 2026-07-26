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

"""Cover authoritative live reorder geometry and visual publication."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptReorderChipView,
)
from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_live_visual_owner import (
    PromptReorderLiveVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
    PromptReorderChipLineGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    ReorderLiveVisualGeometryKey,
    reorder_live_visual_geometry_key,
)


class _FakeLiveGeometry:
    """Publish deterministic layout state and count structural geometry builds."""

    def __init__(self) -> None:
        """Initialize one source/layout publication and no builds."""

        self.state = PromptReorderInteractionGeometryState(
            document_view=cast(
                PromptDocumentView,
                SimpleNamespace(source_text="alpha"),
            ),
            current_layout_view=cast(PromptReorderLayoutView, object()),
        )
        self.build_count = 0

    def build_live_chip_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Return one prepared chip and record exact range ownership."""

        _ = layout_view
        assert chip_rendered_ranges_by_index == {0: (0, 5)}
        assert chip_owned_ranges_by_index == {0: ((0, 5),)}
        self.build_count += 1
        geometry = _chip_geometry()
        return PromptReorderChipGeometrySnapshot(
            geometries_by_chip_index={0: geometry},
            ordered_chip_indices=(0,),
            visual_line_count=1,
            layout_width=200.0,
            content_height=24.0,
            scroll_offset=0.0,
        )


def test_live_visual_owner_reuses_one_complete_geometry_identity() -> None:
    """Repeated preparation must not rebuild projection-owned chip geometry."""

    geometry = _FakeLiveGeometry()
    owner = _owner(geometry)
    segments = {0: _segment()}
    key = _geometry_key(scroll_offset=0)

    first = owner.prepare(
        geometry_key=key,
        segments_by_index=segments,
        reason="owner_test",
    )
    second = owner.prepare(
        geometry_key=key,
        segments_by_index=segments,
        reason="owner_test",
    )

    assert first.rebuilt is True
    assert second.rebuilt is False
    assert second.publication is first.publication
    assert owner.chip_geometry is first.publication.chip_geometry
    assert geometry.build_count == 1
    with pytest.raises(TypeError):
        owner.visuals_by_index[1] = owner.visuals_by_index[0]  # type: ignore[index]


def test_live_visual_owner_invalidates_without_discarding_painted_publication() -> None:
    """Invalidation must preserve the frame until the next bounded rebuild."""

    geometry = _FakeLiveGeometry()
    owner = _owner(geometry)
    segments = {0: _segment()}
    key = _geometry_key(scroll_offset=0)
    first = owner.prepare(
        geometry_key=key,
        segments_by_index=segments,
        reason="owner_test",
    ).publication

    owner.invalidate()

    assert owner.publication.revision == first.revision
    assert owner.visuals_by_index is first.visuals_by_index
    rebuilt = owner.prepare(
        geometry_key=key,
        segments_by_index=segments,
        reason="owner_test",
    )
    assert rebuilt.rebuilt is True
    assert rebuilt.publication.revision == first.revision + 1
    assert geometry.build_count == 2


def test_live_visual_owner_key_changes_only_for_owned_geometry_inputs() -> None:
    """Viewport scroll and source ranges must participate in bounded identity."""

    geometry = _FakeLiveGeometry()
    owner = _owner(geometry)
    base = _geometry_key(scroll_offset=0)
    scrolled = _geometry_key(scroll_offset=12)

    assert scrolled != base
    owner.clear()
    assert owner.chip_geometry is None
    assert owner.visuals_by_index == {}


def _owner(geometry: _FakeLiveGeometry) -> PromptReorderLiveVisualOwner:
    """Return one owner with production metrics and prompt-safe diagnostics."""

    metrics = PromptReorderInteractionMetricsOwner()
    return PromptReorderLiveVisualOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        metrics=metrics,
        diagnostics=PromptReorderInteractionDiagnosticsOwner(
            telemetry=PromptReorderTelemetry(),
            metrics=metrics,
        ),
    )


def _geometry_key(*, scroll_offset: int) -> ReorderLiveVisualGeometryKey:
    """Return one explicit owner input identity."""

    return reorder_live_visual_geometry_key(
        source_text="alpha",
        segment_ranges=((0, 0, 5),),
        content_left=4,
        content_top=6,
        content_width=300,
        scroll_offset=scroll_offset,
    )


def _segment() -> PromptReorderChipView:
    """Return one semantic chip with stable source ownership."""

    return PromptReorderChipView(
        index=0,
        partition_index=0,
        text="alpha",
        serialized_text="alpha",
        display_text="alpha",
        display_source_start=0,
        display_source_end=5,
        selection_start=0,
        selection_end=5,
        separator_text_after="",
        has_separator_after=False,
    )


def _chip_geometry() -> PromptReorderChipGeometry:
    """Return one deterministic projection-owned chip geometry."""

    content_rect = QRectF(8.0, 8.0, 60.0, 18.0)
    line = PromptReorderChipLineGeometry(
        visual_line_index=0,
        line_rect=QRectF(4.0, 6.0, 300.0, 22.0),
        content_rect=content_rect,
        leading_anchor=content_rect.center(),
        trailing_anchor=content_rect.center(),
    )
    hotspot = QRect(4, 4, 68, 26)
    path = QPainterPath()
    path.addRect(content_rect)
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=0,
            visual_revision=1,
        ),
        chip_index=0,
        source_start=0,
        source_end=5,
        rendered_start=0,
        rendered_end=5,
        visual_lines=(line,),
        hotspot_rect=hotspot,
        chrome_path=path,
        outline_bounds=QRectF(content_rect),
        slot_before=QPointF(content_rect.left(), content_rect.center().y()),
        slot_after=QPointF(content_rect.right(), content_rect.center().y()),
        marker_height=content_rect.height(),
    )
