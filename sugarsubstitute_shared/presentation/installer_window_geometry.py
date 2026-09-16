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

"""Own setup-window placement within the current desktop work area."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, QSize
from PySide6.QtGui import QGuiApplication, QScreen, QWindow
from PySide6.QtWidgets import QWidget

from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
)


class InstallerWindowGeometry(QObject):
    """Keep setup and its handoffs reachable when desktop geometry changes."""

    def __init__(
        self, window: QWidget, *, initial_geometry: QRect | None = None
    ) -> None:
        """Retain placement intent and observe this window's native screen owner."""
        super().__init__(window)
        self._window = window
        self._initial_geometry = initial_geometry
        self._screen: QScreen | None = None
        self._native_window: QWindow | None = None
        self._placing = False
        self._placed = False
        window.installEventFilter(self)
        self.place()

    def place(self) -> None:
        """Fit the preferred frame without moving an already reachable window."""
        if self._placing:
            return
        screen = self._window.screen()
        initial = self._initial_geometry if not self._placed else None
        if initial is not None:
            screen = QGuiApplication.screenAt(initial.center()) or screen
        if screen is None:
            return
        self._observe_screen(screen)
        available = screen.availableGeometry()
        if available.isEmpty():
            return
        self._placing = True
        try:
            frame_extra = (
                self._window.frameGeometry().size() - self._window.size()
            ).expandedTo(QSize(0, 0))
            preferred = QSize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
            size = preferred.boundedTo(available.size() - frame_extra)
            self._window.setFixedSize(size)
            frame = self._window.frameGeometry()
            if not self._placed:
                if initial is not None:
                    frame.moveTopLeft(initial.topLeft())
                else:
                    frame.moveCenter(available.center())
            frame.moveLeft(
                max(
                    available.left(),
                    min(frame.left(), available.right() - frame.width() + 1),
                )
            )
            frame.moveTop(
                max(
                    available.top(),
                    min(frame.top(), available.bottom() - frame.height() + 1),
                )
            )
            native = self._window.windowHandle()
            if native is not None and self._window.isVisible():
                native.setFramePosition(frame.topLeft())
            else:
                self._window.move(
                    self._window.pos()
                    + frame.topLeft()
                    - self._window.frameGeometry().topLeft()
                )
            self._placed = True
        finally:
            self._placing = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Attach native screen observation when Qt creates the platform window."""
        if watched is self._window and event.type() == QEvent.Type.Show:
            native = self._window.windowHandle()
            if native is not None and native is not self._native_window:
                if self._native_window is not None:
                    self._native_window.screenChanged.disconnect(self._screen_changed)
                self._native_window = native
                native.screenChanged.connect(self._screen_changed)
            self.place()
        return super().eventFilter(watched, event)

    def _observe_screen(self, screen: QScreen) -> None:
        """Follow only the work-area authority for this setup window."""
        if screen is self._screen:
            return
        if self._screen is not None:
            self._screen.availableGeometryChanged.disconnect(self._work_area_changed)
        self._screen = screen
        screen.availableGeometryChanged.connect(self._work_area_changed)

    def _screen_changed(self, screen: QScreen) -> None:
        """Refit after moving between monitors or replacing a remote desktop."""
        self._observe_screen(screen)
        self.place()

    def _work_area_changed(self, _geometry: QRect) -> None:
        """Reclaim an accessible frame after the active work area changes."""
        self.place()
