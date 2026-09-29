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

"""Make native Qt text legible in offscreen rendering qualifications."""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import sys

from PySide6.QtGui import QFontDatabase
import pytest


@pytest.fixture
def offscreen_rendering_font() -> Iterator[None]:
    """Scope offscreen font registration to one rendered Qt test."""

    font_id = -1
    if not QFontDatabase.families() and sys.platform == "win32":
        windows_directory = os.environ.get("WINDIR")
        if windows_directory:
            font_path = Path(windows_directory) / "Fonts" / "segoeui.ttf"
            if font_path.is_file():
                font_id = QFontDatabase.addApplicationFont(str(font_path))
    try:
        yield
    finally:
        if font_id >= 0:
            QFontDatabase.removeApplicationFont(font_id)


__all__ = ["offscreen_rendering_font"]
