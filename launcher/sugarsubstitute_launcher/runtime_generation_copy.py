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

"""Copy reusable runtime assets without retaining generation-bound paths."""

from __future__ import annotations

from pathlib import Path
import re
import shutil

_UV_PYTHON_MINOR_ALIAS = re.compile(r"^cpython-\d+\.\d+-")


def copy_reusable_runtime(*, source: Path, destination: Path) -> None:
    """Copy immutable runtime assets while forcing path-bound state to rebuild."""

    shutil.copytree(source, destination, ignore=_path_bound_runtime_entries)


def _path_bound_runtime_entries(directory: str, names: list[str]) -> tuple[str, ...]:
    """Exclude uv aliases and partial downloads tied to the old generation."""

    current = Path(directory)
    if current.name != "python":
        return ()
    return tuple(
        name
        for name in names
        if name == ".temp" or _UV_PYTHON_MINOR_ALIAS.match(name) is not None
    )


__all__ = ["copy_reusable_runtime"]
