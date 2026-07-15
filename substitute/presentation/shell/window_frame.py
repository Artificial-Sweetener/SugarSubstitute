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

"""Provide the shared frameless shell window used by Substitute surfaces."""

from __future__ import annotations

import ctypes
from enum import Enum
import sys
from typing import Any, Protocol, cast

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPalette, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qframelesswindow import AcrylicWindow  # type: ignore[import-untyped]
from qframelesswindow.titlebar import TitleBar  # type: ignore[import-untyped]

from substitute.presentation.shell.chrome_style import (
    APP_ORB_DIAMETER,
    APP_ORB_LEFT_MARGIN,
    APP_ORB_TAB_RESERVED_WIDTH,
    APP_ORB_TOP,
    BODY_MATERIAL_SURFACE_OBJECT_NAME,
    WORKFLOW_TITLEBAR_HEIGHT,
    WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT,
    acrylic_titlebar_wash_rgba,
    body_material_wash_style,
    connect_theme_refresh,
)
from substitute.presentation.shell.app_orb_menu import AppOrbMenuButton
from substitute.presentation.shell.titlebar_buttons import (
    ComfyOutputToggleButton,
    GenerationTitleBarRunControl,
    StartupDiagnosticsTitleBarButton,
)
from substitute.shared.logging.logger import get_logger, log_warning

try:
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        FluentStyleSheet,
        isDarkTheme,
    )
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True

    class _FallbackFluentWindowStyle:
        """Provide a no-op Fluent window stylesheet for lightweight stubs."""

        def apply(self, _widget: object) -> None:
            """Ignore stylesheet application when qfluentwidgets is stubbed."""

    class _FallbackFluentStyleSheet:
        """Provide the qfluent stylesheet enum shape used at runtime."""

        FLUENT_WINDOW = _FallbackFluentWindowStyle()

    FluentStyleSheet = _FallbackFluentStyleSheet()


_LOGGER = get_logger("presentation.shell.window_frame")
ACRYLIC_BLEND_COLOR = "A0A0A044"
APP_ORB_TITLEBAR_SPACER_OBJECT_NAME = "AppOrbTitlebarSpacer"
_PLATFORM = sys.platform

if _PLATFORM == "win32":
    import win32con  # type: ignore[import-untyped]
    import win32gui  # type: ignore[import-untyped]

    _DWMAPI: Any | None = ctypes.WinDLL("dwmapi")
    _WINDOW_CORNER_ATTRIBUTE = 33
    _WINDOW_CORNER_ROUND = 2
    _WINDOWS_BUILD = int(sys.getwindowsversion().build)
else:  # pragma: no cover - non-Windows runtime guard
    win32con = None
    win32gui = None
    _DWMAPI = None
    _WINDOW_CORNER_ATTRIBUTE = 0
    _WINDOW_CORNER_ROUND = 0
    _WINDOWS_BUILD = 0


class ShellBackdropMode(Enum):
    """Identify the native backdrop material requested for a shell window."""

    MICA = "mica"
    MICA_ALT = "mica_alt"
    ACRYLIC = "acrylic"


class WorkflowTabDragOwner(Protocol):
    """Describe workflow-tab gesture state needed by the shell titlebar."""

    def workflow_tab_gesture_is_idle(self) -> bool:
        """Return whether no workflow-tab pointer gesture owns the mouse."""


class WorkflowAwareTitleBar(TitleBar):  # type: ignore[misc]
    """Respect qframeless dragging while excluding workflow-tab gestures."""

    def __init__(self, parent: QWidget) -> None:
        """Create a qframeless titlebar with workflow-tab drag suppression."""

        super().__init__(parent)
        self._workflow_tab_drag_owner: WorkflowTabDragOwner | None = None

    def set_workflow_tab_drag_owner(
        self,
        owner: WorkflowTabDragOwner | None,
    ) -> None:
        """Set the workflow tabbar whose gesture state can veto window moves."""

        self._workflow_tab_drag_owner = owner

    def canDrag(self, pos: Any) -> bool:  # noqa: N802
        """Return whether qframeless may start native window movement."""

        if self._workflow_tab_drag_is_active():
            return False
        return bool(super().canDrag(pos))

    def _workflow_tab_drag_is_active(self) -> bool:
        """Return whether a workflow-tab press or drag currently owns input."""

        owner = self._workflow_tab_drag_owner
        if owner is None:
            return False
        try:
            return not owner.workflow_tab_gesture_is_idle()
        except RuntimeError:
            self._workflow_tab_drag_owner = None
            return False


def apply_shell_titlebar_button_theme(title_bar: Any) -> None:
    """Apply qfluent's theme-aware titlebar styling to qframeless buttons."""

    for button in (title_bar.minBtn, title_bar.maxBtn, title_bar.closeBtn):
        FluentStyleSheet.FLUENT_WINDOW.apply(button)


def titlebar_menu_content_insert_index(menu_container: QWidget) -> int:
    """Return the insertion index after shell-owned leading titlebar spacers."""

    layout = menu_container.layout()
    if layout is None:
        return 0
    index = 0
    while index < layout.count():
        item = layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is None or widget.objectName() != APP_ORB_TITLEBAR_SPACER_OBJECT_NAME:
            break
        index += 1
    return index


def restore_rounded_window_corners(window_id: object) -> None:
    """Request Windows 11 rounded corners for a frameless acrylic top-level window."""

    if _PLATFORM != "win32" or _DWMAPI is None or _WINDOWS_BUILD < 22000:
        return

    try:
        hwnd = int(cast(Any, window_id))
        corner_preference = ctypes.c_int(_WINDOW_CORNER_ROUND)
        _DWMAPI.DwmSetWindowAttribute(
            hwnd,
            _WINDOW_CORNER_ATTRIBUTE,
            ctypes.byref(corner_preference),
            4,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        log_warning(
            _LOGGER,
            "Failed to restore rounded acrylic window corners",
            window_id=repr(window_id),
            error=repr(error),
        )


def normalize_acrylic_frameless_chrome(window: Any) -> None:
    """Restore frameless acrylic chrome after the toolkit reapplies window chrome.

    On Qt 6.10+, ``AcrylicWindow`` switches to ``Qt.Window`` and its acrylic path
    reintroduces native caption visuals while the window is inactive or being
    captured. Reasserting ``Qt.FramelessWindowHint`` removes the ghost caption,
    and restoring the resize/minimize/maximize bits preserves the native behavior
    that qframelesswindow expects.
    """

    if _PLATFORM != "win32" or win32con is None or win32gui is None:
        return

    try:
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        hwnd = int(cast(Any, window.winId()))
        style = int(win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE))
        updated_style = style | int(win32con.WS_THICKFRAME)
        updated_style |= int(win32con.WS_MINIMIZEBOX)
        updated_style |= int(win32con.WS_MAXIMIZEBOX)
        updated_style &= ~int(win32con.WS_CAPTION)

        if updated_style != style:
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, updated_style)
        win32gui.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_FRAMECHANGED,
        )
        restore_rounded_window_corners(hwnd)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        log_warning(
            _LOGGER,
            "Failed to normalize acrylic frameless chrome",
            window_id=repr(getattr(window, "winId", lambda: None)()),
            error=repr(error),
        )


def apply_acrylic_effect(window: Any) -> None:
    """Apply the configured acrylic blend and normalize frameless chrome."""

    window.windowEffect.setAcrylicEffect(window.winId(), ACRYLIC_BLEND_COLOR)
    normalize_acrylic_frameless_chrome(window)


class SubstituteWindowFrame(AcrylicWindow):  # type: ignore[misc]
    """Render the standard Substitute frameless window shell and title bar."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        create_menu_container: bool = False,
        create_comfy_output_toggle: bool = False,
        create_generation_action_cluster: bool = False,
        create_startup_diagnostics_button: bool = False,
        create_app_orb_menu: bool = False,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA,
        create_body_material_surface: bool = False,
    ) -> None:
        """Build the shared frameless shell and optional leading titlebar slot."""

        super().__init__(parent)
        self._backdrop_mode = backdrop_mode
        self.menuContainer: QWidget | None = None
        self.comfyOutputToggleButton: ComfyOutputToggleButton | None = None
        self.generationActionCluster: GenerationTitleBarRunControl | None = None
        self.startupDiagnosticsButton: StartupDiagnosticsTitleBarButton | None = None
        self.appOrbMenuButton: AppOrbMenuButton | None = None
        self._bodyLayout: QVBoxLayout | None = None
        self.bodyMaterialSurface: QWidget | None = None
        self.bodyMaterialLayout: QVBoxLayout | None = None
        self._titleBar = title_bar = WorkflowAwareTitleBar(self)

        title_bar.setFixedHeight(WORKFLOW_TITLEBAR_HEIGHT)

        if create_menu_container:
            self.menuContainer = QWidget(title_bar)
            menu_layout = QHBoxLayout(self.menuContainer)
            menu_layout.setContentsMargins(
                0,
                WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT,
                0,
                0,
            )
            menu_layout.setSpacing(0)
            if create_app_orb_menu:
                orb_spacer = QWidget(self.menuContainer)
                orb_spacer.setObjectName(APP_ORB_TITLEBAR_SPACER_OBJECT_NAME)
                orb_spacer.setFixedWidth(APP_ORB_TAB_RESERVED_WIDTH)
                menu_layout.addWidget(orb_spacer)
            self.menuContainer.setLayout(menu_layout)
            self.menuContainer.setStyleSheet("background: transparent; border: none;")
            title_bar.layout().insertWidget(0, self.menuContainer)
            title_bar.layout().setStretch(0, 8)

        if create_comfy_output_toggle:
            self.comfyOutputToggleButton = ComfyOutputToggleButton(title_bar)
            min_button_index = title_bar.layout().indexOf(title_bar.minBtn)
            title_bar.layout().insertWidget(
                min_button_index,
                self.comfyOutputToggleButton,
            )

        if create_generation_action_cluster:
            self.generationActionCluster = GenerationTitleBarRunControl(
                title_bar,
                acrylic_style_enabled=backdrop_mode is ShellBackdropMode.ACRYLIC,
            )
            if self.comfyOutputToggleButton is not None:
                cluster_index = title_bar.layout().indexOf(self.comfyOutputToggleButton)
            else:
                cluster_index = title_bar.layout().indexOf(title_bar.minBtn)
            title_bar.layout().insertWidget(
                cluster_index,
                self.generationActionCluster,
            )

        if create_startup_diagnostics_button:
            self.startupDiagnosticsButton = StartupDiagnosticsTitleBarButton(title_bar)
            if self.comfyOutputToggleButton is not None:
                diagnostics_index = title_bar.layout().indexOf(
                    self.comfyOutputToggleButton
                )
            else:
                diagnostics_index = title_bar.layout().indexOf(title_bar.minBtn)
            title_bar.layout().insertWidget(
                diagnostics_index,
                self.startupDiagnosticsButton,
            )

        self.setTitleBar(title_bar)

        if create_app_orb_menu:
            self.appOrbMenuButton = AppOrbMenuButton(self)
            self._sync_app_orb_geometry()

        if create_body_material_surface:
            self._create_body_material_surface()

        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)
        self._apply_backdrop()
        QTimer.singleShot(0, self._apply_backdrop)

    def set_workflow_tab_drag_owner(
        self,
        owner: WorkflowTabDragOwner | None,
    ) -> None:
        """Connect workflow-tab gesture state to the qframeless titlebar gate."""

        self._titleBar.set_workflow_tab_drag_owner(owner)

    def _create_body_material_surface(self) -> None:
        """Create the shell-owned body wash surface below the transparent titlebar."""

        body_layout = self._ensure_body_layout()
        self.bodyMaterialSurface = QWidget(self)
        self.bodyMaterialSurface.setObjectName(BODY_MATERIAL_SURFACE_OBJECT_NAME)
        self.bodyMaterialLayout = QVBoxLayout(self.bodyMaterialSurface)
        self.bodyMaterialLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyMaterialLayout.setSpacing(0)
        body_layout.addWidget(self.bodyMaterialSurface)

    def _ensure_body_layout(self) -> QVBoxLayout:
        """Return the shell body layout, creating it below the titlebar when needed."""

        if self._bodyLayout is None:
            self._bodyLayout = QVBoxLayout(self)
            self._bodyLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)
            self._bodyLayout.setSpacing(0)
        return self._bodyLayout

    def _apply_backdrop(self) -> None:
        """Apply the configured native shell backdrop to the top-level window."""

        try:
            if self._backdrop_mode is None:
                return
            if self._backdrop_mode is ShellBackdropMode.ACRYLIC:
                apply_acrylic_effect(self)
                return
            self.windowEffect.setMicaEffect(
                self.winId(),
                isDarkMode=self._is_dark_backdrop_enabled(),
                isAlt=self._backdrop_mode is ShellBackdropMode.MICA_ALT,
            )
        except (AttributeError, RuntimeError) as error:
            backdrop_mode = (
                "none" if self._backdrop_mode is None else self._backdrop_mode.value
            )
            log_warning(
                _LOGGER,
                "Failed to apply shell backdrop",
                backdrop_mode=backdrop_mode,
                error=repr(error),
            )

    def add_body_widget(self, widget: QWidget) -> None:
        """Add one widget to the shell body, using the material surface when present."""

        if self.bodyMaterialLayout is not None:
            self.bodyMaterialLayout.addWidget(widget)
            return
        self._ensure_body_layout().addWidget(widget)

    def sync_app_orb_overlay(self) -> None:
        """Keep the frame-owned app orb above titlebar and body children."""

        self._sync_app_orb_geometry()

    def _sync_app_orb_geometry(self) -> None:
        """Position the app orb across the titlebar and toolbar boundary."""

        app_orb_menu_button = getattr(self, "appOrbMenuButton", None)
        if app_orb_menu_button is None:
            return
        app_orb_menu_button.setGeometry(
            APP_ORB_LEFT_MARGIN,
            APP_ORB_TOP,
            APP_ORB_DIAMETER,
            APP_ORB_DIAMETER,
        )
        app_orb_menu_button.raise_()

    def set_comfy_output_toggle_checked(self, checked: bool) -> None:
        """Update the shell output toggle state when the shell changes it directly."""

        if self.comfyOutputToggleButton is None:
            return
        self.comfyOutputToggleButton.setChecked(checked)

    def closeEvent(self, event: Any) -> None:
        """Accept close events by default for derived shell surfaces."""

        event.accept()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep frame-owned overlays aligned after shell geometry changes."""

        super().resizeEvent(event)
        self._sync_app_orb_geometry()

    def showEvent(self, event: QShowEvent) -> None:
        """Raise frame-owned overlays after Qt completes show-time stacking."""

        super().showEvent(event)
        self._sync_app_orb_geometry()

    def _is_dark_backdrop_enabled(self) -> bool:
        """Return whether native window effects should use their dark treatment."""

        return bool(isDarkTheme())

    def _apply_theme_styles(self) -> None:
        """Reapply titlebar and body-material styles after theme changes."""

        self._apply_non_material_surface()
        apply_shell_titlebar_button_theme(self._titleBar)
        if self.comfyOutputToggleButton is not None:
            icon_color = QColor("#ffffff") if isDarkTheme() else QColor("#000000")
            normal_bg = QColor(self._titleBar.minBtn.getNormalBackgroundColor())
            hover_bg = QColor(self._titleBar.minBtn.getHoverBackgroundColor())
            pressed_bg = QColor(self._titleBar.minBtn.getPressedBackgroundColor())
            self.comfyOutputToggleButton.setNormalColor(icon_color)
            self.comfyOutputToggleButton.setHoverColor(icon_color)
            self.comfyOutputToggleButton.setPressedColor(icon_color)
            self.comfyOutputToggleButton.setNormalBackgroundColor(normal_bg)
            self.comfyOutputToggleButton.setHoverBackgroundColor(hover_bg)
            self.comfyOutputToggleButton.setPressedBackgroundColor(pressed_bg)
        if self.bodyMaterialSurface is not None:
            self.bodyMaterialSurface.setStyleSheet(
                body_material_wash_style(self._backdrop_mode)
            )
        if self.generationActionCluster is not None:
            self.generationActionCluster.set_acrylic_style_enabled(
                self._backdrop_mode is ShellBackdropMode.ACRYLIC
            )
        if self.startupDiagnosticsButton is not None:
            self.startupDiagnosticsButton._apply_theme_palette()
        titlebar_background = (
            acrylic_titlebar_wash_rgba()
            if self._backdrop_mode is ShellBackdropMode.ACRYLIC
            else "transparent"
        )
        self._titleBar.setStyleSheet(
            f"background-color: {titlebar_background}; border: none;"
        )

    def _apply_non_material_surface(self) -> None:
        """Paint an opaque theme surface when no native material owns the shell."""

        if self._backdrop_mode is not None:
            self.setAutoFillBackground(False)
            return
        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.Window,
            QColor("#202020") if isDarkTheme() else QColor("#F8F8F8"),
        )
        self.setPalette(palette)
        self.setAutoFillBackground(True)
