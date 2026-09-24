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

"""Describe the runtime that produced an editor-panel baseline."""

from __future__ import annotations

import platform
import sys
from importlib.metadata import version

import PySide6
from PySide6.QtCore import qVersion


def runtime_environment() -> dict[str, str]:
    """Return exact tool and platform versions relevant to baseline rendering."""

    return {
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "pyside6": PySide6.__version__,
        "qt": qVersion(),
        "pytest": version("pytest"),
        "ruff": version("ruff"),
        "mypy": version("mypy"),
    }
