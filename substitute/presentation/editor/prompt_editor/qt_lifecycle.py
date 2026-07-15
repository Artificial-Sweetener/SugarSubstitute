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

"""Provide narrow Qt wrapper lifecycle checks for prompt editor owners."""

from __future__ import annotations

from PySide6.QtCore import QObject
from shiboken6 import isValid


def qt_object_is_alive(obj: QObject) -> bool:
    """Return whether a Python Qt wrapper still references a live C++ object."""

    try:
        return bool(isValid(obj))
    except RuntimeError as error:
        if "Internal C++ object" not in str(error):
            raise
        return False


__all__ = ["qt_object_is_alive"]
