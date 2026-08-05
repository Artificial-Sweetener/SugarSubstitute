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

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]
from substitute.presentation.canvas.shared.canvas_control_frame import (
    CanvasControlFrame,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

from .group_menu import create_canvas_tool_group_menu
from .layout import (
    CanvasToolLayout,
    CanvasToolLayoutSnapshot,
    CanvasToolLayoutSubscription,
)
from .layout_projection import (
    CanvasToolSlotPresentation,
    resolve_canvas_tool_slots,
)
from .model import CanvasToolPresentation, CanvasToolSurface
from .palette import CanvasToolPalette, CanvasToolPaletteSubscription
from .tool_button import (
    CANVAS_TOOL_BUTTON_SIZE,
    CANVAS_TOOL_ICON_SIZE,
    CanvasToolButton,
)
from .tool_strip_indicator import CanvasToolStripIndicator
from .tool_strip_projection import CanvasToolStripProjection


class CanvasToolStrip(CanvasControlFrame):
    """Own palette observation, safe click dispatch, and compact chrome lifecycle."""

    toolRequested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        """Initialize an empty content-sized strip over its canvas parent."""

        super().__init__(parent)
        self.setObjectName("CanvasToolStrip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._palette: CanvasToolPalette | None = None
        self._subscription: CanvasToolPaletteSubscription | None = None
        self._layout_owner: CanvasToolLayout | None = None
        self._layout_subscription: CanvasToolLayoutSubscription | None = None
        self._layout_snapshot: CanvasToolLayoutSnapshot | None = None
        self._palette_presentations: tuple[CanvasToolPresentation, ...] = ()
        self._slot_presentations: tuple[CanvasToolSlotPresentation, ...] = ()
        self._request_in_progress = False
        self._pending_presentations: tuple[CanvasToolSlotPresentation, ...] | None = (
            None
        )
        self._pending_rebuild_scheduled = False
        self._projection = CanvasToolStripProjection(
            strip=self,
            request_tool=self._request_tool,
            request_group_menu=self._show_group_menu,
        )
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.destroyed.connect(self._release_subscription)
        self.hide()

    @property
    def indicator(self) -> CanvasToolStripIndicator:
        """Return the active marker for rendering and lifecycle verification."""

        return self._projection.indicator

    def bind_palette(
        self,
        palette: CanvasToolPalette,
        layout: CanvasToolLayout | None = None,
    ) -> None:
        """Project one palette and release any previous subscription."""

        self._release_subscription()
        self._palette = palette
        self._layout_owner = layout
        self._layout_snapshot = None if layout is None else layout.snapshot()
        self._subscription = palette.subscribe(
            self._palette_changed,
            surface=CanvasToolSurface.TOOL_STRIP,
        )
        if layout is not None:
            self._layout_subscription = layout.subscribe(self._layout_changed)
        self._palette_presentations = palette.snapshot(CanvasToolSurface.TOOL_STRIP)
        self._project(animate_selection=False)

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
        if self._layout_subscription is not None:
            self._layout_subscription.close()
            self._layout_subscription = None

    def _palette_changed(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Resolve palette state and defer reentrant structural replacement."""

        self._palette_presentations = presentations
        self._project(animate_selection=True)

    def _layout_changed(self, snapshot: CanvasToolLayoutSnapshot) -> None:
        """Resolve one changed grouping arrangement against current tool state."""

        self._layout_snapshot = snapshot
        self._project(animate_selection=False)

    def _project(self, *, animate_selection: bool) -> None:
        """Resolve inventory and arrangement into one authoritative slot snapshot."""

        presentations = resolve_canvas_tool_slots(
            self._palette_presentations,
            self._layout_snapshot,
        )
        self._slot_presentations = presentations

        if self._request_in_progress and self._projection.requires_structure(
            presentations
        ):
            self._pending_presentations = presentations
            self._schedule_pending_rebuild()
            return
        self._apply_presentations(
            presentations,
            animate_selection=animate_selection,
        )

    def _apply_presentations(
        self,
        presentations: tuple[CanvasToolSlotPresentation, ...],
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

    def _show_group_menu(self, slot_id: str, global_position: QPoint) -> None:
        """Render one grouped-slot picker at the requested global position."""

        slot = next(
            (
                presentation
                for presentation in self._slot_presentations
                if presentation.slot_id == slot_id and presentation.grouped
            ),
            None,
        )
        if slot is None:
            return
        model = create_canvas_tool_group_menu(
            slot,
            member_requested=lambda tool_id: self._request_group_member(
                slot_id,
                tool_id,
            ),
        )
        menu = QFluentMenuRenderer(parent=self).render(model)
        menu.exec(global_position, aniType=MenuAnimationType.DROP_DOWN)

    def _request_group_member(self, slot_id: str, tool_id: str) -> None:
        """Remember and activate a member through its existing tool request path."""

        layout = self._layout_owner
        if layout is None or not layout.select_group_tool(slot_id, tool_id):
            return
        self._request_tool(tool_id)

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
