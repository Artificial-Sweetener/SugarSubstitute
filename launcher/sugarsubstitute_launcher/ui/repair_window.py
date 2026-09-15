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

"""Host repair progress in the shared native Fluent installer shell."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QVBoxLayout
from qframelesswindow import AcrylicWindow  # type: ignore[import-untyped]
from qframelesswindow.titlebar import TitleBar  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.resources import launcher_icon
from launcher.sugarsubstitute_launcher.ui.installer_style import apply_installer_style
from launcher.sugarsubstitute_launcher.ui.launcher_theme import configure_launcher_theme
from launcher.sugarsubstitute_launcher.ui.repair_progress_view import RepairProgressView
from launcher.sugarsubstitute_launcher.ui.window_effects import (
    apply_launcher_window_effects,
)
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_CONTENT_MAX_WIDTH,
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
    InstallerBodyMaterialSurface,
    InstallerBrandBar,
    configure_installer_title_bar,
)


class RepairWindow(AcrylicWindow):  # type: ignore[misc]
    """Keep the repair window available until its controller reaches a safe close."""

    close_requested = Signal()
    primary_requested = Signal()

    def __init__(self) -> None:
        """Compose the existing installer chrome around the dedicated progress view."""
        super().__init__()
        self._running = False
        configure_launcher_theme()
        self.setObjectName("LauncherWindow")
        self.setWindowTitle(launcher_text("SugarSubstitute Setup"))
        self.setWindowIcon(launcher_icon())
        self.setFixedSize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
        title_bar = TitleBar(self)
        configure_installer_title_bar(title_bar)
        self.setTitleBar(title_bar)
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(InstallerBrandBar(self, show_progress=False))
        body = InstallerBodyMaterialSurface(
            object_name="RepairBodySurface", parent=self
        )
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_view = RepairProgressView(body)
        self.progress_view.setFixedWidth(INSTALLER_CONTENT_MAX_WIDTH)
        body_layout.addWidget(self.progress_view, 1, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(body, 1)
        self.progress_view.close_requested.connect(self.close)
        self.progress_view.primary_requested.connect(self.primary_requested)
        apply_installer_style(self, self.progress_view)
        apply_launcher_window_effects(self)
        self.titleBar.raise_()

    def set_running(self, running: bool) -> None:
        """Let the execution controller own when closing is safe."""
        self._running = running

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Defer an active repair close without discarding the user's request."""
        if self._running:
            event.ignore()
            self.progress_view.set_close_pending()
            self.close_requested.emit()
            return
        super().closeEvent(event)
