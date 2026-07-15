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

"""Create shared vertical layouts for editor and shell widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget


def create_vbox(
    parent: QWidget | None = None,
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    spacing: int = 8,
) -> QVBoxLayout:
    """Build one `QVBoxLayout` with the standard margin and spacing defaults."""

    layout = QVBoxLayout(parent) if parent is not None else QVBoxLayout()
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout
