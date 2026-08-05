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

"""Host one active contextual options control in the ordered canvas top bar."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from substitute.presentation.canvas.shared.canvas_control_frame import (
    CanvasControlFrame,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_SURFACE_BORDER_WIDTH,
    CANVAS_CHROME_SURFACE_HEIGHT,
    CANVAS_CHROME_SURFACE_PADDING,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh

from .model import CanvasToolPresentation
from .palette import CanvasToolPaletteSubscription
from .runtime import CanvasToolRuntime
from .tool_options_control import CanvasToolOptionsControl


class CanvasToolOptionsHost(CanvasControlFrame):
    """Project active runtime options and own transient outside-click capture."""

    surfaceChanged = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create an initially empty canonical canvas surface."""

        super().__init__(parent)
        self.setObjectName("CanvasToolOptionsHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(CANVAS_CHROME_SURFACE_HEIGHT)
        self._runtime: CanvasToolRuntime | None = None
        self._subscription: CanvasToolPaletteSubscription | None = None
        self._options_id: str | None = None
        self._options_control: CanvasToolOptionsControl | None = None
        self._outside_filter_installed = False
        self._layout = QHBoxLayout(self)
        content_inset = (
            CANVAS_CHROME_SURFACE_PADDING - CANVAS_CHROME_SURFACE_BORDER_WIDTH
        )
        self._layout.setContentsMargins(
            content_inset,
            content_inset,
            content_inset,
            content_inset,
        )
        self._layout.setSpacing(0)
        self._layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.destroyed.connect(self._release)
        self.hide()

    @property
    def options_control(self) -> CanvasToolOptionsControl | None:
        """Return the currently mounted contextual options control."""

        return self._options_control

    def bind_runtime(self, runtime: CanvasToolRuntime) -> None:
        """Observe one runtime palette and resolve its active options control."""

        self._release_subscription()
        self._runtime = runtime
        self._subscription = runtime.palette.subscribe(self._palette_changed)
        self._palette_changed(runtime.palette.snapshot())

    def set_contextual_options(
        self,
        options_id: str | None,
        factory: Callable[[QWidget], CanvasToolOptionsControl] | None,
    ) -> None:
        """Mount an options control whose visibility is not owned by a tool mode."""
        if options_id == self._options_id:
            return
        self._replace_options(options_id, factory=factory)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Collapse on an outside press without consuming the destination click."""

        del watched
        control = self._options_control
        if (
            control is not None
            and control.expanded
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
        ):
            global_position = event.globalPosition().toPoint()
            global_bounds = QRect(self.mapToGlobal(QPoint()), self.size())
            if not global_bounds.contains(global_position):
                control.collapse()
        return False

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release runtime and application observation during teardown."""

        self._release()
        super().closeEvent(event)

    def _palette_changed(
        self,
        presentations: tuple[CanvasToolPresentation, ...],
    ) -> None:
        """Replace options only when authoritative active identity changes."""

        active = next(
            (presentation for presentation in presentations if presentation.active),
            None,
        )
        options_id = None if active is None else active.options_id
        if options_id == self._options_id:
            return
        self._replace_options(options_id)

    def _replace_options(
        self,
        options_id: str | None,
        *,
        factory: Callable[[QWidget], CanvasToolOptionsControl] | None = None,
    ) -> None:
        """Dispose the previous control before mounting the requested identity."""

        self._remove_outside_filter()
        previous = self._options_control
        self._options_control = None
        self._options_id = options_id
        if previous is not None:
            previous.collapse()
            self._layout.removeWidget(previous)
            previous.close()
            previous.deleteLater()
        runtime = self._runtime
        if options_id is None or (factory is None and runtime is None):
            self.hide()
            self.surfaceChanged.emit()
            return
        control = (
            factory(self)
            if factory is not None
            else runtime.create_options_control(options_id, self)  # type: ignore[union-attr]
        )
        if control is None:
            self.hide()
            self.surfaceChanged.emit()
            return
        self._options_control = control
        self._layout.addWidget(control)
        control.expandedChanged.connect(self._expansion_changed)
        control.show()
        self.show()
        self.raise_()
        self._synchronize_size()

    def _expansion_changed(self, expanded: bool) -> None:
        """Capture outside clicks only for the live expanded control."""

        if expanded:
            self._install_outside_filter()
        else:
            self._remove_outside_filter()
        self._synchronize_size()

    def _synchronize_size(self) -> None:
        """Apply current content size before notifying the top-bar layout."""

        self._layout.activate()
        self.adjustSize()
        self.updateGeometry()
        self.surfaceChanged.emit()

    def _install_outside_filter(self) -> None:
        """Observe application pointer presses for one expanded lifetime."""

        if self._outside_filter_installed:
            return
        application = QApplication.instance()
        if application is None:
            return
        application.installEventFilter(self)
        self._outside_filter_installed = True

    def _remove_outside_filter(self) -> None:
        """Stop observing application events idempotently."""

        if not self._outside_filter_installed:
            return
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self._outside_filter_installed = False

    def _release_subscription(self) -> None:
        """Release the current palette listener idempotently."""

        if self._subscription is not None:
            self._subscription.close()
            self._subscription = None

    def _release(self, *_args: object) -> None:
        """Release every process-wide or runtime-owned subscription."""

        self._remove_outside_filter()
        self._release_subscription()

    def _apply_theme_style(self, *_args: object) -> None:
        """Apply the canonical floating canvas material."""

        self.setStyleSheet(
            floating_canvas_surface_stylesheet("QFrame#CanvasToolOptionsHost")
        )


__all__ = ["CanvasToolOptionsHost"]
