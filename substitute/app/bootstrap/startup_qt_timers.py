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

"""Qt timer adapters for startup orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6 import QtCore


@dataclass(frozen=True, slots=True)
class StartupQtSchedulerPorts:
    """Group Qt scheduler adapters used by startup orchestration."""

    single_shot: Callable[[int, Callable[[], None]], None]
    visible_summary: Callable[[Callable[[], None]], None]


def create_startup_qtimer() -> Any:
    """Create one Qt timer for startup polling."""

    return QtCore.QTimer()


def startup_single_shot(delay_ms: int, callback: Callable[[], None]) -> None:
    """Schedule one startup callback on the Qt event loop."""

    QtCore.QTimer.singleShot(delay_ms, callback)


def schedule_visible_startup_summary(callback: Callable[[], None]) -> None:
    """Schedule visible startup summary logging after current GUI work drains."""

    startup_single_shot(0, callback)


def create_startup_qt_scheduler_ports() -> StartupQtSchedulerPorts:
    """Create Qt scheduler ports for startup controllers."""

    return StartupQtSchedulerPorts(
        single_shot=startup_single_shot,
        visible_summary=schedule_visible_startup_summary,
    )


__all__ = [
    "StartupQtSchedulerPorts",
    "create_startup_qt_scheduler_ports",
    "create_startup_qtimer",
    "schedule_visible_startup_summary",
    "startup_single_shot",
]
