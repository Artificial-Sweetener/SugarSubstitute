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

"""Run application handoff work only after a concrete Qt surface paints."""

from __future__ import annotations

from collections.abc import Callable
import logging

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QWidget


_LOGGER = logging.getLogger(__name__)
_GATE_ATTRIBUTE = "_sugarsubstitute_surface_presentation_gates"


class _SurfacePresentationGate(QObject):
    """Retain one callback until its exact top-level surface first paints."""

    def __init__(self, window: QWidget, callback: Callable[[], None]) -> None:
        """Install the paint observer and retain its completion callback."""

        super().__init__(window)
        self._window = window
        self._callback: Callable[[], None] | None = callback
        self._scheduled = False
        window.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Schedule completion after the first paint or abandon on destruction."""

        if watched is self._window and event.type() == QEvent.Type.Paint:
            self._schedule_completion()
        elif watched is self._window and event.type() == QEvent.Type.Destroy:
            self._abandon()
        return False

    def _schedule_completion(self) -> None:
        """Run completion after Qt finishes the paint event currently in flight."""

        if self._scheduled:
            return
        self._scheduled = True
        QTimer.singleShot(0, self._complete)

    def _complete(self) -> None:
        """Run the handoff callback once and release this gate."""

        callback = self._callback
        if callback is None:
            return
        self._callback = None
        self._release()
        try:
            callback()
        except Exception:
            _LOGGER.exception("Visible surface handoff callback failed")

    def _release(self) -> None:
        """Detach this observer and its Python retention from the surface."""

        self._window.removeEventFilter(self)
        gates = getattr(self._window, _GATE_ATTRIBUTE, None)
        if isinstance(gates, list) and self in gates:
            gates.remove(self)
        self.deleteLater()

    def _abandon(self) -> None:
        """Discard a queued callback when its promised surface is destroyed."""

        self._callback = None
        self._release()


def run_after_surface_paint(window: object, callback: Callable[[], None]) -> None:
    """Retain and run one callback after the exact QWidget paints."""

    if not isinstance(window, QWidget):
        raise TypeError("Surface presentation requires a QWidget.")
    gate = _SurfacePresentationGate(window, callback)
    gates = getattr(window, _GATE_ATTRIBUTE, None)
    if not isinstance(gates, list):
        gates = []
        setattr(window, _GATE_ATTRIBUTE, gates)
    gates.append(gate)


__all__ = ["run_after_surface_paint"]
