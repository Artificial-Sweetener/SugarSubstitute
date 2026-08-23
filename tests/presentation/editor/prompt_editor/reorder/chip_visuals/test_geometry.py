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

"""Contract tests for shared prompt chip visual geometry and painting."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF

from substitute.presentation.editor.prompt_editor.overlays import (
    PromptChipPainter,
    PromptChipVisual,
    PromptChipVisualBuilder,
)


def test_chip_visual_builder_coalesces_same_line_projection_pieces() -> None:
    """Inline renderer fragments inside one chip should not become separate bubbles."""

    visual = PromptChipVisualBuilder().build_editor_visual(
        fragments=(
            QRectF(10.0, 10.0, 40.0, 14.0),
            QRectF(56.0, 10.0, 30.0, 14.0),
        ),
        content_rect=QRect(0, 0, 200, 80),
    )

    assert len(visual.bubble_rects) == 1
    assert visual.bubble_rects[0].left() <= 6.0
    assert visual.bubble_rects[0].right() >= 90.0


def test_chip_visual_builder_keeps_wrapped_line_fragments_separate() -> None:
    """Line-wrap fragments remain distinct geometry inputs for placement."""

    visual = PromptChipVisualBuilder().build_editor_visual(
        fragments=(
            QRectF(120.0, 10.0, 40.0, 14.0),
            QRectF(10.0, 30.0, 120.0, 14.0),
        ),
        content_rect=QRect(0, 0, 200, 80),
    )

    assert len(visual.bubble_rects) == 2


def test_chip_painter_unites_overlapping_wrapped_bubbles_into_one_chrome_path() -> None:
    """Wrapped chip rows should not paint internal seams that read as separate chips."""

    visual = PromptChipVisual(
        bubble_rects=(
            QRectF(238.0, 50.0, 92.0, 20.0),
            QRectF(4.0, 66.0, 326.0, 20.0),
        ),
        fragment_union_rect=QRectF(4.0, 50.0, 326.0, 36.0),
        hotspot_rect=QRect(0, 47, 335, 42),
        slot_before=QPointF(238.0, 60.0),
        slot_after=QPointF(330.0, 76.0),
        marker_height=20.0,
    )

    path = PromptChipPainter()._chrome_path(visual)

    assert len(path.toFillPolygons()) == 1


def test_chip_painter_keeps_disconnected_bubbles_disconnected() -> None:
    """The chrome path should only connect fragments that geometrically touch."""

    visual = PromptChipVisual(
        bubble_rects=(
            QRectF(10.0, 10.0, 20.0, 18.0),
            QRectF(80.0, 10.0, 20.0, 18.0),
        ),
        fragment_union_rect=QRectF(10.0, 10.0, 90.0, 18.0),
        hotspot_rect=QRect(0, 0, 100, 30),
        slot_before=QPointF(10.0, 19.0),
        slot_after=QPointF(100.0, 19.0),
        marker_height=18.0,
    )

    path = PromptChipPainter()._chrome_path(visual)

    assert len(path.toFillPolygons()) == 2
