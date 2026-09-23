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

"""Own deferred warming of projection geometry reuse indexes."""

from __future__ import annotations

from collections.abc import Callable
from PySide6.QtCore import QObject, QTimer


class PromptProjectionGeometryReuseWarmer(QObject):
    """Coalesce projection index warming behind the Qt event boundary."""

    def __init__(
        self,
        *,
        is_available: Callable[[], bool],
        is_projected: Callable[[], bool],
        prewarm: Callable[[], None],
        parent: QObject,
    ) -> None:
        """Bind lifecycle, display eligibility, and the current index producer."""

        super().__init__(parent)
        self._is_available = is_available
        self._is_projected = is_projected
        self._prewarm = prewarm
        self._requested = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._warm)

    def schedule(self, *, reason: str) -> None:
        """Queue a single warmup when projected geometry can consume it."""

        _ = reason
        if not self._is_available() or not self._is_projected() or self._requested:
            return
        self._requested = True
        self._timer.start(0)

    def _warm(self) -> None:
        """Warm the current projection index if its owner remains available."""

        self._requested = False
        if self._is_available():
            self._prewarm()


__all__ = [
    "PromptProjectionGeometryReuseWarmer",
]
