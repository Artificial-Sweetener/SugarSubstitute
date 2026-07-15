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

"""Create hidden Qt harness surfaces for editor projection replay."""

from __future__ import annotations

import os
from typing import cast

from PySide6.QtWidgets import QApplication, QWidget


def ensure_qapplication() -> QApplication:
    """Return a QApplication configured for hidden/offscreen execution."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def create_hidden_host(*, show_window: bool = False) -> QWidget:
    """Create a realistically sized top-level host for replay checks."""

    ensure_qapplication()
    host = QWidget()
    host.resize(1440, 1000)
    if show_window:
        host.show()
    return host
