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

"""Render the application splash window used during Comfy startup readiness checks."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import QEvent, QRect, Qt, Signal, Slot
from PySide6.QtGui import QFontMetrics, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import FluentStyleSheet
from qframelesswindow import AcrylicWindow

from substitute.presentation.resources.app_icon import application_icon
from substitute.presentation.splash_animation import (
    SplashFlipSettings,
    SplashPaperFlipWidget,
    SplashPoseLibraryError,
    load_splash_pose_library,
)
from substitute.presentation.splash_animation.pose_selector import (
    RecencyWeightedPoseSelector,
)
from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
    apply_acrylic_effect,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    LocalizationBindings,
    render_application_text,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.output_style import (
    create_terminal_output_font,
)
from sugarsubstitute_shared.presentation.terminal.output_view import TerminalOutputView
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.splash_window")
_SPLASH_WINDOW_RECT = QRect(0, 0, 558, 558)
_SPLASH_MASCOT_RECT = QRect(83, 7, 387, 386)
_SPLASH_CONSOLE_RECT = QRect(6, 358, 546, 193)


class _SplashTitleBar(Protocol):
    """Describe qframeless titlebar controls used by the splash window."""

    minBtn: QAbstractButton
    maxBtn: QAbstractButton
    closeBtn: QAbstractButton

    def setDoubleClickEnabled(self, is_enabled: bool) -> None:
        """Set whether double-clicking the titlebar maximizes the window."""

    def raise_(self) -> None:
        """Raise the titlebar above sibling widgets."""


def build_splash_terminal_section_height() -> int:
    """Return the compact splash-owned height for the shared terminal surface."""

    _ = QFontMetrics(create_terminal_output_font())
    return _SPLASH_CONSOLE_RECT.height()


class SplashWindow(AcrylicWindow):
    """Frameless Mica splash window with animated mascot and a log panel.

    - Close button cancels startup loading
    - Mica backdrop
    - Whole window draggable except over the log
    - Single scroll (inside the log only)
    """

    logRequested = Signal(str)
    cancelRequested = Signal()

    def __init__(
        self,
        icon: QIcon | None = None,
        parent: QWidget | None = None,
        *,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA,
    ):
        """Build the splash window with one shared terminal output surface."""

        super().__init__(parent)
        self._localization = LocalizationBindings(self)
        window_icon = icon or application_icon()
        self.setWindowIcon(window_icon)
        self._backdrop_mode = backdrop_mode
        self._configure_titlebar_buttons()

        try:
            if self._backdrop_mode is ShellBackdropMode.ACRYLIC:
                apply_acrylic_effect(self)
            elif self._backdrop_mode is not None:
                self.windowEffect.setMicaEffect(
                    self.winId(),
                    isDarkMode=_is_dark_theme_enabled(),
                    isAlt=self._backdrop_mode is ShellBackdropMode.MICA_ALT,
                )
        except (AttributeError, RuntimeError) as error:
            log_warning(
                _LOGGER,
                "Failed to enable splash Mica effect",
                error=repr(error),
            )

        container = QWidget(self)
        self._container = container
        container.setObjectName("SplashFixedLayoutContainer")

        self._log_stream = TerminalOutputStream(max_lines=2000)
        visual = self._build_splash_visual(icon, container)
        self._visual = visual
        self._terminal_section = QWidget(container)
        self._terminal_section.setObjectName("SplashTerminalSection")
        self._terminal_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        section_layout = QVBoxLayout(self._terminal_section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        self._terminal_view = TerminalOutputView(self._terminal_section)
        self._terminal_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._terminal_view.set_stream(self._log_stream)
        self.log_view = self._terminal_view.log_view
        section_layout.addWidget(self._terminal_view)
        self._terminal_section.setFixedHeight(build_splash_terminal_section_height())

        self.setFixedSize(_SPLASH_WINDOW_RECT.size())
        self._apply_content_geometry()
        self._localization.bind_window_title(
            self,
            lambda: render_application_text(app_text("Loading...")),
        )

        self.logRequested.connect(self._do_append_log)

        container.installEventFilter(self)
        visual.installEventFilter(self)
        self._drag_widgets = {container, visual}

    def center_on_screen(self) -> None:
        """Center the splash window on the active screen."""

        screen = self.screen().availableGeometry()
        self.move(
            screen.left() + (screen.width() - self.width()) // 2,
            screen.top() + (screen.height() - self.height()) // 2,
        )

    def append_log(self, line: str) -> None:
        """Queue one terminal record into the shared splash output stream."""

        if not line:
            return
        self.logRequested.emit(line)

    @Slot(str)
    def _do_append_log(self, line: str) -> None:
        """Append one terminal record to the splash output stream."""

        if not line:
            return
        self._log_stream.append_line(line)

    def resizeEvent(self, event: object) -> None:
        """Keep the splash content pinned close to the window edges."""

        super().resizeEvent(event)
        self._apply_content_geometry()

    def _apply_content_geometry(self) -> None:
        """Place the splash content with the agreed minimal padding."""

        if not hasattr(self, "_container"):
            return
        self._container.setGeometry(_SPLASH_WINDOW_RECT)
        self._visual.setGeometry(_SPLASH_MASCOT_RECT)
        self._terminal_section.setGeometry(_SPLASH_CONSOLE_RECT)
        self._terminal_section.raise_()
        try:
            self.titleBar.raise_()
        except (AttributeError, RuntimeError) as error:
            log_warning(
                _LOGGER,
                "Failed to raise splash titlebar",
                error=repr(error),
            )

    def _configure_titlebar_buttons(self) -> None:
        """Expose qframeless' native close button as the startup cancel affordance."""

        try:
            titlebar = cast(_SplashTitleBar, self.titleBar)
            self._apply_titlebar_theme(titlebar)
            titlebar.minBtn.hide()
            titlebar.maxBtn.hide()
            titlebar.closeBtn.show()
            self._localization.bind_tooltip(
                titlebar.closeBtn,
                lambda: render_application_text(app_text("Cancel loading")),
            )
            titlebar.setDoubleClickEnabled(False)
            try:
                titlebar.closeBtn.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            titlebar.closeBtn.clicked.connect(self._request_cancel)
            titlebar.raise_()
        except (AttributeError, RuntimeError) as error:
            log_warning(
                _LOGGER,
                "Failed to configure splash titlebar buttons",
                error=repr(error),
            )

    def _apply_titlebar_theme(self, titlebar: QWidget) -> None:
        """Apply qfluent's current theme stylesheet to qframeless titlebar controls."""

        FluentStyleSheet.FLUENT_WINDOW.apply(titlebar)
        for button in (
            titlebar.minBtn,
            titlebar.maxBtn,
            titlebar.closeBtn,
        ):
            FluentStyleSheet.FLUENT_WINDOW.apply(button)

    @Slot()
    def _request_cancel(self) -> None:
        """Emit the user-requested startup cancellation and close the helper window."""

        self.cancelRequested.emit()
        self.close()

    def _build_splash_visual(self, icon: QIcon | None, parent: QWidget) -> QWidget:
        """Return the animated splash visual or a static icon fallback."""

        if icon is not None:
            return self._build_static_icon_label(icon, parent)
        try:
            poses = load_splash_pose_library()
            selector = RecencyWeightedPoseSelector(poses)
            return SplashPaperFlipWidget(
                poses,
                selector,
                parent,
                settings=SplashFlipSettings(),
            )
        except (SplashPoseLibraryError, RuntimeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Falling back to static splash icon after animation setup failed",
                error=repr(error),
            )
            return self._build_static_icon_label(application_icon(), parent)

    def _build_static_icon_label(self, icon: QIcon, parent: QWidget) -> QLabel:
        """Return the legacy static splash icon label."""

        icon_label = QLabel(parent)
        icon_label.setObjectName("SplashStaticIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        pm_size = 128
        pm = icon.pixmap(pm_size, pm_size)
        if pm.isNull():
            pm = QPixmap(pm_size, pm_size)
            pm.fill(Qt.transparent)
        icon_label.setPixmap(pm)
        return icon_label

    def eventFilter(self, obj: object, event: object) -> bool:
        """Start system drag only from passive splash chrome."""

        if obj in getattr(self, "_drag_widgets", set()):
            if (
                isinstance(event, QMouseEvent)
                and event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                wh = self.windowHandle()
                if wh is not None:
                    try:
                        wh.startSystemMove()
                        return True
                    except (AttributeError, RuntimeError) as error:
                        log_warning(
                            _LOGGER,
                            "Failed to start splash window drag move",
                            error=repr(error),
                        )
                        return False
        return super().eventFilter(obj, event)


def _is_dark_theme_enabled() -> bool:
    """Return whether splash-owned native effects should use dark treatment."""

    try:
        from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

        return bool(isDarkTheme())
    except ImportError:  # pragma: no cover - lightweight test stubs
        return True
