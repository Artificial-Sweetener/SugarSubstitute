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

"""Apply SugarSubstitute's established material seam through CuteCanvas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from cutecanvas import CanvasComparisonOverlayState, CanvasWorkspace

from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
    resolved_backdrop_mode,
)

_OVERLAY_NAME = "substitute-output-compare-material-gap"


class OutputCompareMaterialGapCoordinator:
    """Own the Output comparison seam without receiving a native renderer."""

    def __init__(self, workspace: CanvasWorkspace) -> None:
        """Register the one persistent host overlay for this Output workspace."""

        self._workspace = workspace
        self._closed = False
        workspace.registerComparisonOverlay(_OVERLAY_NAME, self.draw)
        workspace.destroyed.connect(lambda _object=None: self.close())

    def close(self) -> None:
        """Remove the seam from current and future comparison presentations."""

        if self._closed:
            return
        self._closed = True
        try:
            self._workspace.unregisterComparisonOverlay(_OVERLAY_NAME)
        except RuntimeError:
            return

    def draw(self, painter: QPainter, state: CanvasComparisonOverlayState) -> None:
        """Replace only the native divider line with the shell body material."""

        divider = state.divider
        if not divider.enabled or divider.visible_segment is None:
            return
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.setPen(self._pen(Qt.GlobalColor.transparent))
            painter.drawLine(divider.visible_segment)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setPen(self._pen(self._material_color()))
            painter.drawLine(divider.visible_segment)
        finally:
            painter.restore()

    def _pen(self, color: QColor | Qt.GlobalColor) -> QPen:
        """Return the original square-capped two-pixel seam pen."""

        pen = QPen(color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        return pen

    def _material_color(self) -> QColor:
        """Resolve the current shell material through the host workspace."""

        return QColor(
            *body_material_wash_color(resolved_backdrop_mode(self._workspace))
        )


__all__ = ["OutputCompareMaterialGapCoordinator"]
