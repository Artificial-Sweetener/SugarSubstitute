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

"""Own the reference desktop used by offscreen installer qualification."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication


@contextmanager
def reference_desktop(application: QApplication) -> Iterator[None]:
    """Keep full-size layout qualification independent of Qt's 800-pixel fallback."""
    if application.platformName() != "offscreen":
        yield
        return
    screen = application.primaryScreen()
    if screen is None:
        raise RuntimeError("Installer qualification requires a Qt screen.")
    with patch.object(
        screen, "availableGeometry", return_value=QRect(0, 0, 1920, 1080)
    ):
        yield
