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

"""Start bounded-lifetime Qt runnables through the Qt execution adapter."""

from __future__ import annotations

from PySide6.QtCore import QRunnable, QThreadPool


def start_qt_runnable(job: QRunnable) -> None:
    """Submit one owner-managed job to Qt's process-wide thread pool."""

    QThreadPool.globalInstance().start(job)


__all__ = ["start_qt_runnable"]
