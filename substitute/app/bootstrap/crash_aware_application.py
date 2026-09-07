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

"""Own Qt application event delivery and lifecycle boundaries."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QMetaObject, QObject, Qt
from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.crash_reporting.runtime import (
    active_process_crash_runtime,
)


class CrashAwareApplication(QApplication):
    """Own crash-aware event delivery and phase-safe application exit."""

    def __init__(self, argv: Sequence[str]) -> None:
        """Create the application with a stable copied argument list."""

        super().__init__(list(argv))

    def notify(self, receiver: QObject, event: QEvent) -> bool:
        """Deliver one event or terminate through the installed crash runtime."""

        try:
            return super().notify(receiver, event)
        except BaseException as error:
            runtime = active_process_crash_runtime()
            if runtime is None:
                raise
            runtime.record_qt_exception(error)
            return False

    def request_quit(self) -> None:
        """Queue shutdown so an exit request made before ``exec`` is preserved."""

        invoked = QMetaObject.invokeMethod(
            self,
            "quit",
            Qt.ConnectionType.QueuedConnection,
        )
        if not invoked:
            raise RuntimeError("Qt rejected the queued application exit request")


__all__ = ["CrashAwareApplication"]
