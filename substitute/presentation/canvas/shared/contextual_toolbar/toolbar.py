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

"""Compose the shared draggable Contextual Toolbar viewport overlay."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_GAP,
    CANVAS_CHROME_OVERLAY_INSET,
    CANVAS_CHROME_SURFACE_BORDER_WIDTH,
    CANVAS_CHROME_SURFACE_PADDING,
)
from substitute.presentation.canvas.shared.canvas_control_frame import (
    CanvasControlFrame,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh

from .content_host import ContextualToolbarContentHost, ContextualToolbarPageFactory
from .drag_handle import ContextualToolbarDragHandle
from .page import ContextualToolbarPage
from .placement import (
    ContextualToolbarPlacement,
    ContextualToolbarPlacementUpdate,
)
from .surface_motion import ContextualToolbarSurfaceMotion


class CanvasContextualToolbar(CanvasControlFrame):
    """Own shared chrome, page mounting, suppression, and draggable placement."""

    geometryChanged = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create an initially empty toolbar over one viewport widget."""
        super().__init__(parent)
        self.setObjectName("CanvasContextualToolbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._placement = ContextualToolbarPlacement()
        self._context_visible = False
        self._suppressed = False
        self.drag_handle = ContextualToolbarDragHandle(self)
        self.content_host = ContextualToolbarContentHost(self)
        self._surface_motion = ContextualToolbarSurfaceMotion(self)

        inset = CANVAS_CHROME_SURFACE_PADDING - CANVAS_CHROME_SURFACE_BORDER_WIDTH
        layout = QHBoxLayout(self)
        layout.setContentsMargins(inset, inset, inset, inset)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)
        layout.addWidget(self.drag_handle)
        layout.addWidget(self.content_host)

        self.drag_handle.dragged.connect(self._move_by)
        self.content_host.geometryChanged.connect(self._synchronize_geometry)
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.hide()

    @property
    def page(self) -> ContextualToolbarPage | None:
        """Return the mounted content page for focused integration tests."""
        return self.content_host.page

    def set_content(
        self,
        content_id: str,
        factory: ContextualToolbarPageFactory,
    ) -> ContextualToolbarPage:
        """Show one stable context page unless an exclusive mode suppresses it."""
        if self.content_host.page is not None:
            if self._surface_motion.target_visible:
                self._surface_motion.settle_visible()
            else:
                self.content_host.clear()
        page = self.content_host.set_content(content_id, factory)
        self._context_visible = True
        self._synchronize_geometry()
        return page

    def clear_content(self) -> None:
        """Hide derived context and release its mounted page."""
        self._return_owned_focus_to_viewport()
        self._context_visible = False
        self.content_host.settle_content_motion()
        self._surface_motion.set_visible(
            False,
            finished=self._clear_hidden_content,
        )

    def set_suppressed(self, suppressed: bool) -> None:
        """Temporarily hide the toolbar without discarding context or placement."""
        self._suppressed = bool(suppressed)
        if self._suppressed:
            self.content_host.settle_content_motion()
        self._synchronize_visibility()

    def set_context_rect(
        self,
        bounds: QRect | None,
        *,
        update: ContextualToolbarPlacementUpdate,
    ) -> None:
        """Position automatic placement against one panel-space context."""
        self._placement.set_context_rect(bounds, update=update)
        if self._context_visible and self.content_host.page is not None:
            self.position_in_viewport()

    def position_in_viewport(self) -> None:
        """Project retained placement into the current viewport safe rectangle."""
        self.move(
            self._placement.position(
                self.size(),
                self._safe_rect(),
                device_pixel_ratio=self.devicePixelRatioF(),
            )
        )
        if self.isVisible():
            self.raise_()

    def _move_by(self, delta: object) -> None:
        """Apply one incremental handle drag through the placement owner."""
        if not isinstance(delta, QPoint):
            return
        self.move(
            self._placement.move_by(
                delta,
                self.size(),
                self._safe_rect(),
                device_pixel_ratio=self.devicePixelRatioF(),
            )
        )
        self.raise_()

    def _safe_rect(self) -> QRect:
        """Return the inset viewport rectangle available to floating chrome."""
        parent = self.parentWidget()
        if parent is None:
            return QRect()
        return parent.rect().adjusted(
            CANVAS_CHROME_OVERLAY_INSET,
            CANVAS_CHROME_OVERLAY_INSET,
            -CANVAS_CHROME_OVERLAY_INSET,
            -CANVAS_CHROME_OVERLAY_INSET,
        )

    def _synchronize_geometry(self) -> None:
        """Settle page size while preserving the retained center anchor."""
        layout = self.layout()
        if layout is not None:
            layout.activate()
        self.adjustSize()
        self.updateGeometry()
        self.position_in_viewport()
        self._synchronize_visibility()
        self.geometryChanged.emit()

    def _synchronize_visibility(self) -> None:
        """Project derived context and exclusive suppression into visibility."""
        visible = self._context_visible and not self._suppressed
        self._surface_motion.set_visible(visible)
        if visible:
            self.raise_()

    def _clear_hidden_content(self) -> None:
        """Release page geometry only after the complete shell is hidden."""

        if not self._context_visible:
            self.content_host.clear()

    def _return_owned_focus_to_viewport(self) -> None:
        """Return keyboard ownership before dismissing a focused toolbar page."""

        focused = QApplication.focusWidget()
        owns_focus = focused is self or (
            focused is not None and self.isAncestorOf(focused)
        )
        if not owns_focus:
            return
        viewport = self.parentWidget()
        if viewport is not None:
            viewport.setFocus(Qt.FocusReason.OtherFocusReason)

    def _apply_theme_style(self, *_args: object) -> None:
        """Apply the canonical floating canvas material."""
        self.setStyleSheet(
            floating_canvas_surface_stylesheet("QFrame#CanvasContextualToolbar")
        )


__all__ = ["CanvasContextualToolbar"]
