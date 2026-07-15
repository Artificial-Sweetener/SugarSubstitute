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

"""Render the input canvas widget and mask-layer interaction controls."""

from __future__ import annotations

from os import environ
from uuid import UUID

from qpane import QPane
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import MenuAnimationType

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
    create_canvas_session_boundary,
)
from substitute.presentation.canvas.qpane.canvas_route_projector import (
    InputRouteProjector,
)
from substitute.presentation.canvas.qpane.input_pane_adapter import (
    InputQPaneRouteAdapter,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CanvasZoomIndicator,
)
from substitute.presentation.canvas.input.input_mask_tool_controller import (
    InputMaskToolMenuState,
    InputMaskToolMode,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from substitute.shared.logging.logger import log_debug, get_logger
from substitute.shared.startup_trace import trace_mark

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


_LOGGER = get_logger("presentation.canvas.input.input_canvas_view")
_DEFAULT_QPANE_FEATURES = ("mask", "sam")
_HARNESS_QPANE_FEATURES = ("mask",)
_STARTUP_HARNESS_ENV_VAR = "SUGAR_SUBSTITUTE_STARTUP_HARNESS"
_DEFER_INPUT_SAM_ENV_VAR = "SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM"


class InputCanvas(QWidget):
    """Host QPane input image/mask editing interactions for the active workflow."""

    inputMaskSaved = Signal(str, str)  # mask_id, path
    inputImageLoaded = Signal(object, str)  # image_id, path
    maskToolMenuStateRequested = Signal()
    maskToolModeRequested = Signal(str)
    dockActionRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        route_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
    ) -> None:
        """Initialize input pane and attach mask autosave/context-menu wiring."""

        super().__init__(parent)
        self.setStyleSheet("border: none; background-color: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        features = _input_canvas_qpane_features()
        if features != _DEFAULT_QPANE_FEATURES:
            trace_mark(
                "input_canvas.qpane_features",
                features=",".join(features),
                reason="startup_harness_defer_sam",
            )
        self.pane = QPane(features=features)
        self._zoom_indicator = CanvasZoomIndicator(self.pane)
        self._route_session_boundary = (
            route_session_boundary or create_canvas_session_boundary()
        )
        self._route_projector = InputRouteProjector(
            InputQPaneRouteAdapter(self.pane),
            session_boundary=self._route_session_boundary,
        )
        self._dock_action_text = "Undock canvas"
        self._mask_tool_menu_state = InputMaskToolMenuState()

        self.pane.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pane.customContextMenuRequested.connect(self._show_context_menu)
        self.pane.maskSaved.connect(self._on_pane_mask_saved)
        self.pane.imageLoaded.connect(self._on_pane_image_loaded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.pane)
        self._availability_overlay = QLabel("No input canvas nodes", self)
        self._availability_overlay.setObjectName("InputCanvasAvailabilityOverlay")
        self._availability_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)
        self._availability_overlay.hide()

    def _current_image_id_for_event(self) -> UUID | None:
        """Return the current QPane image ID through the Input route owner."""

        return self._route_projector.current_image_id_for_event()

    def current_image_id_for_event(self) -> UUID | None:
        """Return the event current image ID through the Input route owner."""

        return self._current_image_id_for_event()

    @property
    def route_projector(self) -> InputRouteProjectorPort:
        """Return the single Input display route projector for this QPane."""

        return self._route_projector

    def resizeEvent(self, event: object) -> None:
        """Keep the availability overlay aligned with the canvas bounds."""

        self._resize_availability_overlay()
        super().resizeEvent(event)

    def set_available(self, available: bool, reason: str = "") -> None:
        """Enable or disable input-canvas interaction and empty-state presentation."""

        self.pane.setEnabled(available)
        overlay = self._availability_overlay
        if available:
            overlay.hide()
            return
        overlay.setText(reason or "No input canvas nodes")
        InputCanvas._resize_availability_overlay(self)
        overlay.raise_()
        overlay.show()

    def set_dock_action_text(self, text: str) -> None:
        """Set the context-menu label for the manager-owned dock action."""

        self._dock_action_text = text

    def keyPressEvent(self, event: object) -> None:
        """Forward key presses to the underlying pane control."""

        self.pane.keyPressEvent(event)

    def keyReleaseEvent(self, event: object) -> None:
        """Forward key releases to the underlying pane control."""

        self.pane.keyReleaseEvent(event)

    def enterEvent(self, event: object) -> None:
        """Grab keyboard focus when pointer enters the canvas area."""

        self.setFocus()
        super().enterEvent(event)

    def set_mask_tool_menu_state(self, state: InputMaskToolMenuState) -> None:
        """Store the latest presenter-owned mask tool menu state."""

        self._mask_tool_menu_state = state

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

    def _show_context_menu(self, pos: object) -> None:
        """Show context menu for pane tool selection intents."""

        self.maskToolMenuStateRequested.emit()
        tool_state = self._mask_tool_menu_state
        menu = QFluentMenuRenderer(parent=self.pane).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "input_canvas.tool.pan_zoom",
                        "Pan & Zoom",
                        callback=lambda: self.maskToolModeRequested.emit(
                            InputMaskToolMode.PAN_ZOOM
                        ),
                    ),
                    MenuItem(
                        "input_canvas.tool.brush",
                        "Brush",
                        callback=lambda: self.maskToolModeRequested.emit(
                            InputMaskToolMode.BRUSH
                        ),
                        enabled=tool_state.brush_enabled,
                    ),
                    MenuItem(
                        "input_canvas.tool.smart_select",
                        "Smart Select",
                        callback=lambda: self.maskToolModeRequested.emit(
                            InputMaskToolMode.SMART_SELECT
                        ),
                        enabled=tool_state.smart_select_enabled,
                    ),
                    MenuSeparator(),
                    MenuItem(
                        "input_canvas.dock_action",
                        self._dock_action_text,
                        callback=self.dockActionRequested.emit,
                    ),
                )
            )
        )
        menu.exec(self.pane.mapToGlobal(pos), aniType=MenuAnimationType.DROP_DOWN)

    def _on_pane_mask_saved(self, mask_id: str, path: str) -> None:
        """Relay pane maskSaved signal for controller-level buffer synchronization."""

        log_debug(
            _LOGGER,
            "Input canvas received QPane maskSaved signal",
            mask_id=mask_id,
            path=path,
        )
        self.inputMaskSaved.emit(mask_id, path)

    def _on_pane_image_loaded(self, path: object) -> None:
        """Relay pane imageLoaded with the active image id for graph association."""

        image_path = str(path) if path is not None else ""
        image_id = self._route_projector.loaded_image_id_for_event()
        log_debug(
            _LOGGER,
            "Input canvas received QPane imageLoaded signal",
            image_id=str(image_id),
            image_path=image_path,
        )
        self.inputImageLoaded.emit(image_id, image_path)


def _input_canvas_qpane_features() -> tuple[str, ...]:
    """Return QPane features for InputCanvas construction.

    Normal app startup keeps SAM enabled. The startup harness can explicitly defer
    SAM to measure first-shell cost without changing user-facing behavior.
    """

    if _truthy_env(_STARTUP_HARNESS_ENV_VAR) and _truthy_env(_DEFER_INPUT_SAM_ENV_VAR):
        return _HARNESS_QPANE_FEATURES
    return _DEFAULT_QPANE_FEATURES


def _truthy_env(name: str) -> bool:
    """Return whether an environment flag is set to a truthy value."""

    return environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "InputCanvas",
]
