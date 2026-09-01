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

"""Own the fatal boundary around Qt event delivery."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.crash_reporting.runtime import (
    active_process_crash_runtime,
)


class CrashAwareApplication(QApplication):
    """Route exceptions escaping Qt event dispatch into crash supervision."""

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


__all__ = ["CrashAwareApplication"]
