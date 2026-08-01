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

"""Project one active tool's runtime-provided contextual options surface."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget
from qfluentwidgets.common.config import qconfig  # type: ignore[import-untyped]
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
)

from .model import CanvasToolPresentation
from .palette import CanvasToolPaletteSubscription
from .runtime import CanvasToolRuntime


class CanvasToolOptionsPanel(QFrame):
    """Own active-tool options replacement without retaining stale tool state."""

    surfaceChanged = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create an initially hidden, content-sized floating surface."""

        super().__init__(parent)
        self.setObjectName("CanvasToolOptionsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._runtime: CanvasToolRuntime | None = None
        self._subscription: CanvasToolPaletteSubscription | None = None
        self._options_id: str | None = None
        self._options_widget: QWidget | None = None
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)
        self._apply_theme_style()
        qconfig.themeChangedFinished.connect(self._apply_theme_style)
        qconfig.themeColorChanged.connect(self._apply_theme_style)
        self.destroyed.connect(self._release)
        self.hide()

    @property
    def options_widget(self) -> QWidget | None:
        """Return the currently mounted contextual surface."""

        return self._options_widget

    def bind_runtime(self, runtime: CanvasToolRuntime) -> None:
        """Observe one runtime palette and resolve its registered factories."""

        self._release()
        self._runtime = runtime
        self._subscription = runtime.palette.subscribe(self._palette_changed)
        self._palette_changed(runtime.palette.snapshot())

    def _palette_changed(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Replace options only when the active options identity changes."""

        active = next(
            (presentation for presentation in presentations if presentation.active),
            None,
        )
        options_id = None if active is None else active.options_id
        if options_id == self._options_id:
            return
        self._replace_options(options_id)

    def _replace_options(self, options_id: str | None) -> None:
        """Dispose stale state before mounting the requested options surface."""

        previous = self._options_widget
        self._options_widget = None
        self._options_id = options_id
        if previous is not None:
            self._layout.removeWidget(previous)
            previous.close()
            previous.deleteLater()
        runtime = self._runtime
        if options_id is None or runtime is None:
            self.hide()
            self.surfaceChanged.emit()
            return
        widget = runtime.create_options_widget(options_id, self)
        if widget is None:
            self.hide()
            self.surfaceChanged.emit()
            return
        self._options_widget = widget
        self._layout.addWidget(widget)
        widget.show()
        self.adjustSize()
        self.show()
        self.raise_()
        self.surfaceChanged.emit()

    def _release(self, *_args: object) -> None:
        """Release palette observation idempotently."""

        if self._subscription is not None:
            self._subscription.close()
            self._subscription = None

    def _apply_theme_style(self, *_args: object) -> None:
        """Match the compact tool strip's Fluent surface treatment."""

        if isDarkTheme():
            surface = "rgba(35, 35, 35, 232)"
            border = "rgba(255, 255, 255, 40)"
        else:
            surface = "rgba(246, 246, 246, 232)"
            border = "rgba(0, 0, 0, 34)"
        self.setStyleSheet(
            f"""
            QFrame#CanvasToolOptionsPanel {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 3px;
            }}
            """
        )


__all__ = ["CanvasToolOptionsPanel"]
