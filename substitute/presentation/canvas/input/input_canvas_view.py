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

"""Render the Input canvas widget and its focused interaction controllers."""

from __future__ import annotations

from collections.abc import Callable
from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    apply_application_text,
)
from substitute.presentation.localization import LocalizedLabel

from os import environ
from uuid import UUID

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QCloseEvent, QEnterEvent, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from cutecanvas import ExecutionRuntime

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
    create_canvas_session_boundary,
)
from substitute.presentation.canvas.input.input_document import (
    InputCanvasDocument,
)
from substitute.presentation.canvas.input.input_canvas_context_menu import (
    InputCanvasContextMenuController,
)
from substitute.presentation.canvas.input.input_contextual_toolbar_controller import (
    InputContextualToolbarController,
)
from substitute.presentation.canvas.input.input_edit_session_controller import (
    InputEditSessionController,
)
from substitute.presentation.canvas.input.input_canvas_tool_chrome import (
    InputCanvasToolChrome,
)
from substitute.presentation.canvas.input.input_canvas_cursor_theme import (
    InputCanvasCursorTheme,
)
from substitute.presentation.canvas.input.input_layer_coverage_edit_mode import (
    InputLayerCoverageEditMode,
)
from substitute.presentation.canvas.input.input_layer_coverage_editor import (
    InputLayerCoverageEditor,
)
from substitute.presentation.canvas.input.input_selection_authoring_observer import (
    InputSelectionAuthoringObserver,
)
from substitute.presentation.canvas.input.input_route_projector import (
    InputRouteProjector,
)
from substitute.presentation.canvas.shared.canvas_top_bar import CanvasTopBar
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
)
from substitute.presentation.canvas.tools import (
    CanvasToolLayout,
    CanvasToolOptionsHost,
    CanvasToolRuntime,
    CanvasToolStrip,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.shared.logging.logger import log_debug, get_logger
from substitute.shared.startup_trace import trace_mark

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


_LOGGER = get_logger("presentation.canvas.input.input_canvas_view")
_DEFAULT_CUTECANVAS_FEATURES = ("mask", "sam")
_HARNESS_CUTECANVAS_FEATURES = ("mask",)
_STARTUP_HARNESS_ENV_VAR = "SUGAR_SUBSTITUTE_STARTUP_HARNESS"
_DEFER_INPUT_SAM_ENV_VAR = "SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM"


class InputCanvas(QWidget):
    """Host CuteCanvas Input image/mask editing interactions for the active workflow."""

    inputImageLoaded = Signal(object, str)  # image_id, path
    toolRequested = Signal(str)
    dockActionRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        execution_runtime: ExecutionRuntime,
        route_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
    ) -> None:
        """Initialize the Input document host and context-menu wiring."""

        super().__init__(parent)
        self.setStyleSheet("border: none; background-color: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        features = _input_canvas_cutecanvas_features()
        if features != _DEFAULT_CUTECANVAS_FEATURES:
            trace_mark(
                "input_canvas.cutecanvas_features",
                features=",".join(features),
                reason="startup_harness_defer_sam",
            )
        self.document = InputCanvasDocument(
            features=features,
            execution_runtime=execution_runtime,
        )
        input_document = self.document
        self.destroyed.connect(
            lambda _object=None, document=input_document: document.close()
        )
        self.canvas = self.document.canvas
        self.canvas.setEditorCursorTheme(InputCanvasCursorTheme())
        self._route_session_boundary = (
            route_session_boundary or create_canvas_session_boundary()
        )
        self._route_projector = InputRouteProjector(
            self.document,
            session_boundary=self._route_session_boundary,
        )
        self._canvas_detached = False
        self._tool_chrome = InputCanvasToolChrome(
            canvas=self.canvas,
            tool_requested=self.toolRequested.emit,
        )
        self.contextual_toolbar = CanvasContextualToolbar(self.canvas)
        self.edit_sessions = InputEditSessionController(
            self.canvas,
            parent=self,
        )
        self._selection_authoring = InputSelectionAuthoringObserver(
            canvas=self.canvas,
            operation_provider=self.document.tool_options.current_canvas_operation,
            parent=self,
        )
        self._contextual_toolbar_controller = InputContextualToolbarController(
            document=self.document.tool_options,
            toolbar=self.contextual_toolbar,
            tool_chrome=self._tool_chrome,
            edit_sessions=self.edit_sessions,
            selection_authoring=self._selection_authoring,
            request_tool=self.toolRequested.emit,
            parent=self,
        )
        self._coverage_edit_mode = InputLayerCoverageEditMode(
            document=self.document.tool_options,
            input_root=self,
            canvas=self.canvas,
            tool_chrome=self._tool_chrome,
            contextual_toolbar=self.contextual_toolbar,
            parent=self,
        )
        self._context_menu_controller = InputCanvasContextMenuController(
            canvas=self.canvas,
            active_mask_id_provider=self.document.tool_options.active_mask_id,
            mask_layers_provider=self.document.tool_options.mask_layers,
            coverage_edit_requested=self._coverage_edit_mode.begin,
            detached_provider=lambda: self._canvas_detached,
            dock_requested=self.dockActionRequested.emit,
        )

        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(
            self._context_menu_controller.show_context_menu
        )
        self.document.imageMaterialized.connect(self._on_image_materialized)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)
        self._availability_overlay = LocalizedLabel(
            app_text("No input canvas nodes"), self
        )
        self._availability_overlay.setObjectName("InputCanvasAvailabilityOverlay")
        self._availability_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)
        self._availability_overlay.hide()

    def _current_image_id_for_event(self) -> UUID | None:
        """Return the current CuteCanvas image ID through the Input route owner."""

        return self._route_projector.current_image_id_for_event()

    def current_image_id_for_event(self) -> UUID | None:
        """Return the event current image ID through the Input route owner."""

        return self._current_image_id_for_event()

    @property
    def route_projector(self) -> InputRouteProjectorPort:
        """Return the single Input display route projector for this document."""

        return self._route_projector

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the availability overlay aligned with the canvas bounds."""

        self._resize_availability_overlay()
        self._tool_chrome.sync_geometry()
        self._contextual_toolbar_controller.refresh_placement()
        self._coverage_edit_mode.position_editor()
        super().resizeEvent(event)

    def set_available(
        self,
        available: bool,
        reason: ApplicationText = "",
    ) -> None:
        """Enable or disable input-canvas interaction and empty-state presentation."""

        if not available and self._coverage_edit_mode.active:
            self._coverage_edit_mode.cancel()
        if not available:
            self._contextual_toolbar_controller.cancel_active_edit()
        self.canvas.setEnabled(available)
        self._tool_chrome.set_enabled(available)
        self.contextual_toolbar.setEnabled(available)
        overlay = self._availability_overlay
        if available:
            overlay.hide()
            return
        if reason:
            apply_application_text(overlay, reason)
        else:
            apply_application_text(overlay, app_text("No input canvas nodes"))
        InputCanvas._resize_availability_overlay(self)
        overlay.raise_()
        overlay.show()

    def set_canvas_detached(self, detached: bool) -> None:
        """Store the host-owned attachment state for context-menu rendering."""

        self._canvas_detached = detached

    def set_host_chrome_obstacles(self, obstacles: tuple[QRect, ...]) -> None:
        """Arrange Input tool chrome around host-owned overlay surfaces."""

        self._tool_chrome.set_host_obstacles(obstacles)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Forward key presses to the underlying canvas control."""

        self.canvas.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Forward key releases to the underlying canvas control."""

        self.canvas.keyReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel transient layer coverage work before canvas teardown."""
        coverage_edit_mode = getattr(self, "_coverage_edit_mode", None)
        if coverage_edit_mode is not None:
            coverage_edit_mode.cancel()
        contextual_controller = getattr(
            self,
            "_contextual_toolbar_controller",
            None,
        )
        if contextual_controller is not None:
            contextual_controller.close()
        selection_authoring = getattr(self, "_selection_authoring", None)
        if selection_authoring is not None:
            selection_authoring.close()
        super().closeEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        """Grab keyboard focus when pointer enters the canvas area."""

        self.setFocus()
        super().enterEvent(event)

    @property
    def tool_strip(self) -> CanvasToolStrip:
        """Return the content-sized tool strip for lifecycle and rendering tests."""

        return self._tool_chrome.tool_strip

    @property
    def tool_options_host(self) -> CanvasToolOptionsHost:
        """Return the contextual top-bar options host."""

        return self._tool_chrome.options_host

    @property
    def canvas_top_bar(self) -> CanvasTopBar:
        """Return the ordered Input-owned top-bar flow."""

        return self._tool_chrome.top_bar

    @property
    def coverage_editor(self) -> InputLayerCoverageEditor:
        """Return the exclusive bottom coverage editor for interaction tests."""
        return self._coverage_edit_mode.editor

    @property
    def coverage_edit_active(self) -> bool:
        """Return whether layer coverage preview exclusively owns the canvas."""
        return self._coverage_edit_mode.active

    def bind_tool_runtime(
        self,
        runtime: CanvasToolRuntime,
        layout: CanvasToolLayout | None = None,
        *,
        restore_operation: Callable[[str], bool] | None = None,
    ) -> None:
        """Project one authoritative runtime into Input tool chrome."""

        self._tool_chrome.bind_runtime(runtime, layout)
        self._contextual_toolbar_controller.bind_runtime(runtime)
        if restore_operation is not None:
            self._contextual_toolbar_controller.bind_operation_restoration(
                restore_operation
            )

    def _resize_availability_overlay(self) -> None:
        """Resize the unavailable overlay to cover the full input canvas."""

        self._availability_overlay.setGeometry(self.rect())

    def _apply_theme_styles(self) -> None:
        """Reapply the canvas availability overlay after theme changes."""

        text_rgba = (
            "rgba(255, 255, 255, 190)" if isDarkTheme() else "rgba(24, 29, 34, 0.90)"
        )
        background_rgba = (
            "rgba(18, 18, 18, 150)" if isDarkTheme() else "rgba(255, 255, 255, 0.82)"
        )
        self._availability_overlay.setStyleSheet(
            f"""
            QLabel#InputCanvasAvailabilityOverlay {{
                color: {text_rgba};
                background-color: {background_rgba};
                border: none;
                font-size: 16px;
            }}
            """
        )

    def _on_image_materialized(self, image_id: object, path: str) -> None:
        """Relay host-owned document materialization for graph association."""

        log_debug(
            _LOGGER,
            "Input canvas materialized document image",
            image_id=str(image_id),
            image_path=path,
        )
        self.inputImageLoaded.emit(image_id, path)


def _input_canvas_cutecanvas_features() -> tuple[str, ...]:
    """Return CuteCanvas features for InputCanvas construction.

    Normal app startup keeps SAM enabled. The startup harness can explicitly defer
    SAM to measure first-shell cost without changing user-facing behavior.
    """

    if _truthy_env(_STARTUP_HARNESS_ENV_VAR) and _truthy_env(_DEFER_INPUT_SAM_ENV_VAR):
        return _HARNESS_CUTECANVAS_FEATURES
    return _DEFAULT_CUTECANVAS_FEATURES


def _truthy_env(name: str) -> bool:
    """Return whether an environment flag is set to a truthy value."""

    return environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "InputCanvas",
]
