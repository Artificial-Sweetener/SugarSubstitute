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

"""Draw Substitute's output-compare material gap over QPane."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen

from substitute.presentation.shell.chrome_style import (
    body_material_wash_color,
    resolved_backdrop_mode,
)

OUTPUT_COMPARE_MATERIAL_GAP_OVERLAY_NAME = "substitute-output-compare-material-gap"


class OutputCompareMaterialGapOverlay:
    """Register and draw the output compare material gap on a QPane widget."""

    def __init__(
        self,
        *,
        pane: object,
        compare_enabled: Callable[[], bool],
        material_color: Callable[[], QColor] | None = None,
        width_px: int = 2,
    ) -> None:
        """Create an overlay backed only by QPane's public overlay APIs."""

        self._pane = pane
        self._compare_enabled = compare_enabled
        self._material_color = material_color or self._resolved_material_color
        self._width_px = max(1, int(width_px))
        register_overlay = getattr(pane, "registerOverlay", None)
        if callable(register_overlay):
            register_overlay(OUTPUT_COMPARE_MATERIAL_GAP_OVERLAY_NAME, self.draw)

    def close(self) -> None:
        """Unregister the material-gap overlay when the owning widget is closing."""

        unregister_overlay = getattr(self._pane, "unregisterOverlay", None)
        if callable(unregister_overlay):
            unregister_overlay(OUTPUT_COMPARE_MATERIAL_GAP_OVERLAY_NAME)

    def draw(self, painter: object, _state: object) -> None:
        """Replace the compare seam with the shell body material wash."""

        _ = _state
        if not self._compare_enabled():
            return
        divider_state = self._divider_state()
        if divider_state is None or not bool(getattr(divider_state, "enabled", False)):
            return
        visible_segment = getattr(divider_state, "visible_segment", None)
        if visible_segment is None:
            return

        save = getattr(painter, "save", None)
        restore = getattr(painter, "restore", None)
        set_render_hint = getattr(painter, "setRenderHint", None)
        set_composition_mode = getattr(painter, "setCompositionMode", None)
        set_pen = getattr(painter, "setPen", None)
        draw_line = getattr(painter, "drawLine", None)
        if not (
            callable(save)
            and callable(restore)
            and callable(set_render_hint)
            and callable(set_composition_mode)
            and callable(set_pen)
            and callable(draw_line)
        ):
            return

        save()
        try:
            set_render_hint(QPainter.RenderHint.Antialiasing, False)
            set_composition_mode(QPainter.CompositionMode.CompositionMode_Clear)
            set_pen(self._line_pen(Qt.GlobalColor.transparent))
            draw_line(visible_segment)
            set_composition_mode(QPainter.CompositionMode.CompositionMode_SourceOver)
            set_pen(self._line_pen(self._material_color()))
            draw_line(visible_segment)
        finally:
            restore()

    def _line_pen(self, color: QColor | Qt.GlobalColor) -> QPen:
        """Return the fixed-width square-cap pen used for material-gap strokes."""

        pen = QPen(color)
        pen.setWidth(self._width_px)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        return pen

    def _divider_state(self) -> object | None:
        """Return QPane's public comparison divider state when available."""

        comparison_divider_state = getattr(self._pane, "comparisonDividerState", None)
        if not callable(comparison_divider_state):
            return None
        return cast(object, comparison_divider_state())

    def _resolved_material_color(self) -> QColor:
        """Return the workspace body wash color for the pane's owning window."""

        return QColor(*body_material_wash_color(resolved_backdrop_mode(self._pane)))


__all__ = [
    "OUTPUT_COMPARE_MATERIAL_GAP_OVERLAY_NAME",
    "OutputCompareMaterialGapOverlay",
]
