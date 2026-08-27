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

"""Contract tests for token-aware projection layout geometry and hit testing."""

from __future__ import annotations


from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_geometry import (
    PromptProjectionReorderGeometry,
    reorder_geometry_state,
)
from tests.support.prompt_editor.projection_layout_support import (
    projection_layout_for as _layout_for,
)

from .support import (
    _reorder_geometry_inputs_for_text,
)

_REGION_TEXT_COLOR = QColor(222, 223, 224)


def test_projection_layout_builds_one_reorder_chip_geometry_for_escaped_weight_text() -> (
    None
):
    """Escaped numeric-looking chip text should not split semantic chip identity."""

    prompt_text = (
        r"see-through white dress, lace trim, center opening, sparkling dress, "
        r"black underbust \(ribbon:1.20\), see-through silhouette, short dress, "
        r"bare legs, sleeveless, bare arms, pink eyes,"
    )
    layout, _projection = _layout_for(prompt_text, text_width=170.0)
    layout_view, chips, rendered_ranges, owned_ranges = (
        _reorder_geometry_inputs_for_text(prompt_text)
    )
    target_chip = next(
        chip for chip in chips if "black underbust" in chip.serialized_text
    )

    snapshot = PromptProjectionReorderGeometry().reorder_chip_geometry_snapshot(
        state=reorder_geometry_state(layout.frame.geometry),
        layout_view=layout_view,
        chip_rendered_ranges_by_index=rendered_ranges,
        chip_owned_ranges_by_index=owned_ranges,
        viewport_rect=QRectF(0.0, 0.0, 180.0, 240.0),
        scroll_offset=0.0,
    )
    target_geometry = snapshot.geometries_by_chip_index[target_chip.index]

    assert target_geometry.chip_index == target_chip.index
    assert target_geometry.rendered_start == target_chip.selection_start
    assert target_geometry.rendered_end == target_chip.selection_end
    assert not target_geometry.chrome_path.isEmpty()
    assert tuple(
        chip_index
        for chip_index in snapshot.ordered_chip_indices
        if chip_index == target_chip.index
    ) == (target_chip.index,)


def test_projection_layout_builds_one_reorder_chip_geometry_for_emphasis_weight() -> (
    None
):
    """Projected emphasis suffix renderers should not create extra chip identities."""

    prompt_text = "alpha, black underbust (ribbon:1.20), gamma"
    layout, _projection = _layout_for(prompt_text, text_width=150.0)
    layout_view, chips, rendered_ranges, owned_ranges = (
        _reorder_geometry_inputs_for_text(prompt_text)
    )
    target_chip = next(
        chip for chip in chips if "black underbust" in chip.serialized_text
    )
    range_start, range_end = rendered_ranges[target_chip.index]
    fragments = layout.frame.geometry.selection.source_range_fragments(
        range_start,
        range_end,
        viewport_rect=QRectF(0.0, 0.0, 180.0, 240.0),
        scroll_offset=0.0,
    )

    snapshot = PromptProjectionReorderGeometry().reorder_chip_geometry_snapshot(
        state=reorder_geometry_state(layout.frame.geometry),
        layout_view=layout_view,
        chip_rendered_ranges_by_index=rendered_ranges,
        chip_owned_ranges_by_index=owned_ranges,
        viewport_rect=QRectF(0.0, 0.0, 180.0, 240.0),
        scroll_offset=0.0,
    )

    assert len(fragments) > 1
    assert target_chip.index in snapshot.geometries_by_chip_index
    assert snapshot.geometries_by_chip_index[target_chip.index].chip_index == (
        target_chip.index
    )


def test_projection_layout_reorder_placement_uses_chip_geometry_visual_lines() -> None:
    """Placement lanes should be derived from the same chip geometry as paint."""

    prompt_text = r"alpha, black underbust \(ribbon:1.20\), gamma"
    layout, _projection = _layout_for(prompt_text, text_width=115.0)
    layout_view, chips, rendered_ranges, owned_ranges = (
        _reorder_geometry_inputs_for_text(prompt_text)
    )
    target_chip = next(
        chip for chip in chips if "black underbust" in chip.serialized_text
    )
    viewport_rect = QRectF(0.0, 0.0, 180.0, 240.0)
    reorder_geometry = PromptProjectionReorderGeometry()
    geometry_state = reorder_geometry_state(layout.frame.geometry)
    chip_snapshot = reorder_geometry.reorder_chip_geometry_snapshot(
        state=geometry_state,
        layout_view=layout_view,
        chip_rendered_ranges_by_index=rendered_ranges,
        chip_owned_ranges_by_index=owned_ranges,
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    target_geometry = chip_snapshot.geometries_by_chip_index[target_chip.index]

    placement_snapshot = reorder_geometry.reorder_placement_snapshot(
        state=geometry_state,
        layout_view=layout_view,
        chip_geometry_snapshot=chip_snapshot,
        gap_ranges_by_index={},
        viewport_rect=viewport_rect,
        scroll_offset=0.0,
    )
    adjacent_line_indices = {
        placement.placement_id.visual_line_index
        for placement in placement_snapshot.placements
        if isinstance(placement.target, PromptLineDropTarget)
        and target_chip.index in placement.adjacent_chip_indices
    }

    assert len(target_geometry.visual_lines) > 1
    assert {
        line.visual_line_index for line in target_geometry.visual_lines
    } <= adjacent_line_indices
