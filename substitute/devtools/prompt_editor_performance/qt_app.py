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

"""Qt application bootstrap for prompt editor performance benchmarks."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


def configure_offscreen_platform() -> None:
    """Default benchmark Qt rendering to the offscreen platform."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def prompt_performance_application() -> QApplication:
    """Return the QApplication used by the prompt performance benchmark."""

    configure_offscreen_platform()
    from PySide6.QtWidgets import QApplication

    return cast(QApplication, QApplication.instance() or QApplication([]))


configure_offscreen_platform()
