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

"""Own ordered horizontal layout and intrinsic sizing for canvas top chrome."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLayout, QWidget

from substitute.presentation.canvas.shared.canvas_control_frame import (
    CanvasControlFrame,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
)


class CanvasTopBar(CanvasControlFrame):
    """Lay out canvas-owned top controls in one authoritative widget order."""

    geometryChanged = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create an initially empty transparent top-bar flow."""

        super().__init__(parent)
        self.setObjectName("CanvasTopBar")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self._synchronizing_geometry = False
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(CANVAS_CHROME_GAP)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.hide()

    def append_control(self, control: QWidget) -> None:
        """Append one control to the sole visual ordering authority."""

        control.installEventFilter(self)
        self._layout.addWidget(control, alignment=Qt.AlignmentFlag.AlignTop)
        self.synchronize_geometry()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Synchronize immediately when an ordered child's visibility changes."""

        handled = super().eventFilter(watched, event)
        if (
            isinstance(watched, QWidget)
            and watched.parentWidget() is self
            and (
                event.type()
                in {
                    QEvent.Type.Show,
                    QEvent.Type.Hide,
                    QEvent.Type.Resize,
                    QEvent.Type.LayoutRequest,
                }
            )
        ):
            self.synchronize_geometry()
        return handled

    def synchronize_geometry(self) -> None:
        """Publish one idempotent projection of explicit child geometry changes."""

        if self._synchronizing_geometry:
            return
        self._synchronizing_geometry = True
        previous_size = QSize(self.size())
        previously_hidden = self.isHidden()
        try:
            self.setVisible(self._has_visible_control())
            self._layout.activate()
        finally:
            self._synchronizing_geometry = False
        if previous_size != self.size() or previously_hidden != self.isHidden():
            self.geometryChanged.emit()

    def _has_visible_control(self) -> bool:
        """Derive surface visibility from the authoritative ordered layout."""

        for index in range(self._layout.count()):
            item = self._layout.itemAt(index)
            widget = None if item is None else item.widget()
            if widget is not None and not widget.isHidden():
                return True
        return False


__all__ = ["CanvasTopBar"]
