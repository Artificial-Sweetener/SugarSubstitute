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

"""Present the launcher window for supervisor-routed secondary invocations."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QWidget

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocation,
)
from sugarsubstitute_shared.qt_window_presentation import request_window_presentation


_PRESENTATION_TIMEOUT_SECONDS = 2.0


@dataclass(slots=True)
class _PresentationRequest:
    """Carry one cross-thread activation request and paint acknowledgement."""

    completed: Event = field(default_factory=Event)
    surface: str | None = None


class LauncherInstancePresenter(QObject):
    """Bridge broker threads to one launcher-owned Qt surface."""

    presentation_requested = Signal(object)

    def __init__(self, window: QWidget) -> None:
        """Bind presentation requests to the exact launcher top-level window."""

        super().__init__(window)
        self._window = window
        self._pending: list[_PresentationRequest] = []
        window.installEventFilter(self)
        self.presentation_requested.connect(
            self._request_presentation,
            Qt.ConnectionType.QueuedConnection,
        )

    def present(self, _invocation: ApplicationInvocation) -> str | None:
        """Wait until the launcher surface paints after an activation request."""

        request = _PresentationRequest()
        self.presentation_requested.emit(request)
        if not request.completed.wait(_PRESENTATION_TIMEOUT_SECONDS):
            return None
        return request.surface

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Complete pending activation only after the exact window paints."""

        if watched is self._window and event.type() == QEvent.Type.Paint:
            pending = tuple(self._pending)
            self._pending.clear()
            surface = type(self._window).__name__
            for request in pending:
                request.surface = surface
                request.completed.set()
        elif watched is self._window and event.type() == QEvent.Type.Destroy:
            pending = tuple(self._pending)
            self._pending.clear()
            for request in pending:
                request.completed.set()
        return False

    def _request_presentation(self, request: object) -> None:
        """Reveal the launcher and schedule the paint used as acknowledgement."""

        if not isinstance(request, _PresentationRequest):
            return
        self._pending.append(request)
        request_window_presentation(self._window)
        self._window.update()


__all__ = ["LauncherInstancePresenter"]
