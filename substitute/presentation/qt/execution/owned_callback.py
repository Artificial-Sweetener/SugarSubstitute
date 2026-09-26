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

"""Schedule deferred Qt callbacks against explicit native lifetimes."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer


def schedule_on_next_turn(owner: object, callback: Callable[[], None]) -> None:
    """Queue one callback while rejecting owners outside the Qt lifecycle."""

    if not isinstance(owner, QObject):
        raise TypeError("Deferred Qt callback owner must be a QObject")
    QTimer.singleShot(0, owner, callback)


__all__ = ["schedule_on_next_turn"]
