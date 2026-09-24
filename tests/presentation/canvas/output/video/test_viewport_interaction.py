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

"""Verify bounded cursor-centered video viewport transformations."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.output.video_playback_controller import (
    VideoViewportState,
)
from substitute.presentation.canvas.output.video_viewport_interaction import (
    panned_viewport,
    zoomed_viewport,
)
from tests.support.qt.lifecycle import ensure_qt_application


def test_zoom_anchors_cursor_and_reset_scale_prevents_pan() -> None:
    """Zoom should retain the cursor point and fitted video should remain centered."""

    ensure_qt_application()
    surface = QWidget()
    surface.resize(400, 200)

    zoomed = zoomed_viewport(
        VideoViewportState(),
        steps=2.0,
        cursor=QPointF(300.0, 50.0),
        surface=surface,
    )
    fitted_pan = panned_viewport(
        VideoViewportState(),
        delta=QPointF(100.0, 100.0),
        surface=surface,
    )

    assert zoomed.zoom > 1.0
    assert zoomed.pan_x < 0.0
    assert zoomed.pan_y > 0.0
    assert fitted_pan == VideoViewportState()


def test_pan_is_bounded_by_visible_scaled_extent() -> None:
    """Pointer drags should never move scaled video fully outside the viewport."""

    ensure_qt_application()
    surface = QWidget()
    surface.resize(100, 100)

    panned = panned_viewport(
        VideoViewportState(zoom=2.0),
        delta=QPointF(1000.0, -1000.0),
        surface=surface,
    )

    assert panned == VideoViewportState(zoom=2.0, pan_x=0.5, pan_y=-0.5)
