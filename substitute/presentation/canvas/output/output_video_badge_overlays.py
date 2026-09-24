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

"""Draw semantic play badges on CuteCanvas video tiles."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QObject, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from cutecanvas import (
    CanvasOverlayState,
    CanvasPresentationKind,
    CanvasWorkspace,
    CuteCanvas,
)

from substitute.domain.output_media import OutputMediaKind
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.shared.types import OutputImageMeta

OUTPUT_VIDEO_BADGE_OVERLAY_NAME = "sugarsubstitute.output.video-play-badge"


class OutputVideoBadgeOverlays(QObject):
    """Attach a non-interactive play cue to each visible video grid tile."""

    def __init__(
        self,
        *,
        workspace: CanvasWorkspace,
        document: OutputCanvasDocument,
        metadata_for: Callable[[UUID], OutputImageMeta | None],
    ) -> None:
        """Observe CuteCanvas presentation changes and retain attached canvases."""

        super().__init__(workspace)
        self._workspace = workspace
        self._document = document
        self._metadata_for = metadata_for
        self._canvases: set[CuteCanvas] = set()
        workspace.presentationChanged.connect(self.synchronize)
        workspace.destroyed.connect(lambda _object=None: self.close())

    def synchronize(self, _presentation: object | None = None) -> None:
        """Match overlay ownership to the current CuteCanvas grid presentation."""

        self._clear()
        if self._workspace.session.presentation.kind is not CanvasPresentationKind.GRID:
            return
        for image_id in self._document.image_ids():
            metadata = self._metadata_for(image_id)
            if (
                metadata is None
                or getattr(metadata, "media_kind", OutputMediaKind.IMAGE)
                is not OutputMediaKind.VIDEO
            ):
                continue
            composition_id = self._document.composition_id_for(image_id)
            if composition_id is None:
                continue
            canvas = self._workspace.canvasFor(composition_id)
            if canvas is None:
                continue
            canvas.registerCanvasOverlay(
                OUTPUT_VIDEO_BADGE_OVERLAY_NAME, _draw_play_badge
            )
            self._canvases.add(canvas)

    def close(self) -> None:
        """Remove every play badge from its CuteCanvas owner."""

        self._clear()

    def _clear(self) -> None:
        """Unregister overlays before canvases are reused by another presentation."""

        for canvas in tuple(self._canvases):
            canvas.unregisterCanvasOverlay(OUTPUT_VIDEO_BADGE_OVERLAY_NAME)
        self._canvases.clear()


def _draw_play_badge(painter: QPainter, state: CanvasOverlayState) -> None:
    """Paint one compact centered play cue in viewport coordinates."""

    viewport = QRectF(state.viewport)
    diameter = min(48.0, max(28.0, min(viewport.width(), viewport.height()) * 0.18))
    center = viewport.center()
    circle = QRectF(
        center.x() - diameter / 2.0,
        center.y() - diameter / 2.0,
        diameter,
        diameter,
    )
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(255, 255, 255, 210), 1.5))
    painter.setBrush(QColor(0, 0, 0, 165))
    painter.drawEllipse(circle)
    radius = diameter * 0.22
    offset = diameter * 0.04
    triangle = QPainterPath()
    triangle.moveTo(QPointF(center.x() - radius * 0.55 + offset, center.y() - radius))
    triangle.lineTo(QPointF(center.x() + radius + offset, center.y()))
    triangle.lineTo(QPointF(center.x() - radius * 0.55 + offset, center.y() + radius))
    triangle.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 235))
    painter.drawPath(triangle)
    painter.restore()


__all__ = ["OUTPUT_VIDEO_BADGE_OVERLAY_NAME", "OutputVideoBadgeOverlays"]
