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

"""Own installer window geometry handoff parsing and command projection."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRect


def parse_handoff_geometry(raw_value: str | None) -> QRect | None:
    """Parse an `x,y,width,height` handoff geometry string."""

    if not raw_value:
        return None
    parts = raw_value.split(",")
    if len(parts) != 4:
        return None
    try:
        x, y, width, height = (int(part) for part in parts)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return QRect(x, y, width, height)


def serialize_handoff_geometry(geometry: QRect) -> str:
    """Serialize one window frame geometry for a setup handoff."""

    return f"{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}"


def append_handoff_geometry(
    command: Sequence[str],
    geometry: QRect,
) -> list[str]:
    """Append serialized window geometry to an application launch command."""

    return [*command, f"--handoff-geometry={serialize_handoff_geometry(geometry)}"]
