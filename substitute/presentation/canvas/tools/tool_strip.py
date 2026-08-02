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

"""Host one live contextual canvas-tool projection as compact Qt chrome."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
)

from .model import CanvasToolPresentation
from .palette import CanvasToolPalette, CanvasToolPaletteSubscription
from .tool_button import (
    CANVAS_TOOL_BUTTON_SIZE,
    CANVAS_TOOL_ICON_SIZE,
    CanvasToolButton,
)
from .tool_strip_indicator import CanvasToolStripIndicator
from .tool_strip_projection import CanvasToolStripProjection


class CanvasToolStrip(QFrame):
    """Own palette observation, safe click dispatch, and compact chrome lifecycle."""

    toolRequested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        """Initialize an empty content-sized strip over its canvas parent."""

        super().__init__(parent)
        self.setObjectName("CanvasToolStrip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._palette: CanvasToolPalette | None = None
        self._subscription: CanvasToolPaletteSubscription | None = None
        self._request_in_progress = False
        self._pending_presentations: tuple[CanvasToolPresentation, ...] | None = None
        self._pending_rebuild_scheduled = False
        self._projection = CanvasToolStripProjection(
            strip=self,
            request_tool=self._request_tool,
        )
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.destroyed.connect(self._release_subscription)
        self.hide()

    @property
    def indicator(self) -> CanvasToolStripIndicator:
        """Return the active marker for rendering and lifecycle verification."""

        return self._projection.indicator

    def bind_palette(self, palette: CanvasToolPalette) -> None:
        """Project one palette and release any previous subscription."""

        if self._subscription is not None:
            self._subscription.close()
        self._palette = palette
        self._subscription = palette.subscribe(self._palette_changed)
        self._apply_presentations(palette.snapshot(), animate_selection=False)

    def button_for(self, tool_id: str) -> CanvasToolButton | None:
        """Return one current qfluent button by stable tool identity."""

        return self._projection.button_for(tool_id)

    def tool_buttons(self) -> tuple[CanvasToolButton, ...]:
        """Return current qfluent buttons in palette order."""

        return self._projection.tool_buttons()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release palette observation before closing the strip."""

        self._release_subscription()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the projection aligned after structural geometry changes."""

        super().resizeEvent(event)
        self._projection.sync_geometry()

    def showEvent(self, event: QShowEvent) -> None:
        """Restore projection and strip z-order when chrome becomes visible."""

        super().showEvent(event)
        self.raise_()
        self._projection.sync_geometry()

    def _release_subscription(self, *_args: object) -> None:
        """Release palette observation idempotently during close or destruction."""

        if self._subscription is not None:
            self._subscription.close()
            self._subscription = None

    def _palette_changed(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Apply state in place and defer reentrant structural replacement."""

        if self._request_in_progress and self._projection.requires_structure(
            presentations
        ):
            self._pending_presentations = presentations
            self._schedule_pending_rebuild()
            return
        self._apply_presentations(presentations, animate_selection=True)

    def _apply_presentations(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
        *,
        animate_selection: bool,
    ) -> None:
        """Delegate one authoritative palette snapshot to the projection owner."""

        self._projection.apply(
            presentations,
            animate_selection=animate_selection,
        )

    def _request_tool(self, tool_id: str) -> None:
        """Emit one intent without deleting the qfluent button that emitted it."""

        self._request_in_progress = True
        try:
            self.toolRequested.emit(tool_id)
        finally:
            self._request_in_progress = False
        if self._pending_presentations is not None:
            self._schedule_pending_rebuild()
            return
        self.raise_()
        self.indicator.raise_()

    def _schedule_pending_rebuild(self) -> None:
        """Queue structural churn until the emitting qfluent button returns."""

        if self._pending_rebuild_scheduled:
            return
        self._pending_rebuild_scheduled = True
        QTimer.singleShot(0, self._apply_pending_rebuild)

    def _apply_pending_rebuild(self) -> None:
        """Apply the latest deferred catalog after click dispatch is complete."""

        self._pending_rebuild_scheduled = False
        presentations = self._pending_presentations
        self._pending_presentations = None
        if presentations is not None:
            self._apply_presentations(presentations, animate_selection=False)

    def _apply_theme_style(self, *_args: object) -> None:
        """Apply the canonical floating canvas material to the compact strip."""

        self.setStyleSheet(floating_canvas_surface_stylesheet("QFrame#CanvasToolStrip"))
        self.indicator.update()


__all__ = [
    "CANVAS_TOOL_BUTTON_SIZE",
    "CANVAS_TOOL_ICON_SIZE",
    "CanvasToolButton",
    "CanvasToolStrip",
]
