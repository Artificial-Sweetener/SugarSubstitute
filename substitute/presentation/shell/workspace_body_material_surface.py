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

"""Paint the workspace body material with a faded cube-stack aperture."""

from __future__ import annotations

from collections.abc import Callable
from weakref import ReferenceType, ref

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QRegion
from PySide6.QtWidgets import QWidget

from substitute.presentation.shell.chrome_style import (
    BODY_MATERIAL_SURFACE_OBJECT_NAME,
    body_material_wash_color,
    connect_theme_refresh,
)
from substitute.presentation.shell.window_frame import ShellBackdropMode

_is_valid_qt_object: Callable[[object], bool]
try:
    from shiboken6 import isValid as _imported_is_valid_qt_object

    _is_valid_qt_object = _imported_is_valid_qt_object
except ImportError:  # pragma: no cover - PySide supplies this in production

    def _is_valid_qt_object(_target: object) -> bool:
        """Return a valid-object fallback outside a full PySide runtime."""

        return True


def _clamp_unit_interval(value: float) -> float:
    """Return ``value`` constrained to the inclusive unit interval."""

    return max(0.0, min(1.0, float(value)))


class WorkspaceBodyMaterialSurface(QWidget):
    """Paint workspace body material with an independently faded cube-stack region."""

    def __init__(
        self,
        *,
        backdrop_mode: ShellBackdropMode | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the shell-owned workspace material surface."""

        super().__init__(parent)
        self._backdrop_mode = backdrop_mode
        self._cube_stack_widget_ref: ReferenceType[QWidget] | None = None
        self._cube_stack_wash_opacity = 1.0
        self.setObjectName(BODY_MATERIAL_SURFACE_OBJECT_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        connect_theme_refresh(self, self._refresh_material)

    def set_backdrop_mode(self, backdrop_mode: ShellBackdropMode | None) -> None:
        """Update the native backdrop mode used for material wash opacity."""

        if self._backdrop_mode is backdrop_mode:
            return
        self._backdrop_mode = backdrop_mode
        self.update()

    def set_cube_stack_region_widget(self, widget: QWidget | None) -> None:
        """Track the widget whose geometry defines the cube-stack material region."""

        self._cube_stack_widget_ref = ref(widget) if widget is not None else None
        self.update()

    def set_cube_stack_wash_opacity(self, opacity: float) -> None:
        """Set cube-stack wash opacity from transparent to full body wash."""

        clamped_opacity = _clamp_unit_interval(opacity)
        if abs(self._cube_stack_wash_opacity - clamped_opacity) < 0.0001:
            return
        self._cube_stack_wash_opacity = clamped_opacity
        self.update()

    def cube_stack_wash_opacity(self) -> float:
        """Return the current cube-stack wash opacity."""

        return self._cube_stack_wash_opacity

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the body wash while independently fading the cube-stack region."""

        _ = event
        painter = QPainter(self)
        base_color = QColor(*body_material_wash_color(self._backdrop_mode))
        cube_stack_rect = self._cube_stack_region()
        if cube_stack_rect is None:
            painter.fillRect(self.rect(), base_color)
            return

        body_region = QRegion(self.rect()).subtracted(QRegion(cube_stack_rect))
        painter.setClipRegion(body_region)
        painter.fillRect(self.rect(), base_color)
        painter.setClipping(False)

        cube_stack_color = QColor(base_color)
        cube_stack_color.setAlpha(
            round(base_color.alpha() * self._cube_stack_wash_opacity)
        )
        if cube_stack_color.alpha() > 0:
            painter.fillRect(cube_stack_rect, cube_stack_color)

    def _cube_stack_region(self) -> QRect | None:
        """Return the current cube-stack material region in surface coordinates."""

        widget_ref = self._cube_stack_widget_ref
        if widget_ref is None:
            return None
        widget = widget_ref()
        if widget is None or not _is_valid_qt_object(widget):
            self._cube_stack_widget_ref = None
            return None
        try:
            top_left = widget.mapTo(self, QPoint(0, 0))
            region = QRect(top_left, widget.size()).intersected(self.rect())
        except RuntimeError:
            self._cube_stack_widget_ref = None
            return None
        if region.isEmpty():
            return None
        return region

    def _refresh_material(self) -> None:
        """Refresh material painting after theme or accent changes."""

        self.update()


__all__ = ["WorkspaceBodyMaterialSurface"]
