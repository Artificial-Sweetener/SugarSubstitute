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

"""Provide Qt timer adapters for prompt undo coalescing."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget


class PromptQtUndoCoalescingTimer:
    """Adapt a single-shot QTimer to the undo coalescing controller."""

    def __init__(self, *, parent: QWidget, interval_ms: int) -> None:
        """Create a parented timer for one coalescing idle interval."""

        self._timeout_handler: Callable[[], None] | None = None
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._handle_timeout)

    def set_timeout_handler(self, handler: Callable[[], None]) -> None:
        """Set the callback invoked when the timer expires."""

        self._timeout_handler = handler

    def start(self) -> None:
        """Start or restart the underlying single-shot timer."""

        self._timer.start()

    def stop(self) -> None:
        """Stop the underlying timer if active."""

        self._timer.stop()

    def _handle_timeout(self) -> None:
        """Forward timer expiry to the configured coalescing owner."""

        if self._timeout_handler is not None:
            self._timeout_handler()


__all__ = ["PromptQtUndoCoalescingTimer"]
