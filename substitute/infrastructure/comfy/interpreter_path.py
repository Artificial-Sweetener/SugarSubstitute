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

"""Normalize interpreter paths without escaping virtual environments."""

from __future__ import annotations

import os
from pathlib import Path

from sugarsubstitute_shared.windows_long_paths import operational_path


def absolute_interpreter_path(path: Path) -> Path:
    """Return an operational absolute path without dereferencing venv symlinks."""

    return operational_path(Path(os.path.abspath(path)))


__all__ = ["absolute_interpreter_path"]
