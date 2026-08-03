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

"""Translate pip output into structured path-compatibility failures."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.external_path_failure import external_long_path_error


def raise_pip_path_compatibility_error(
    *,
    fallback_path: Path,
    output: str,
) -> None:
    """Raise a structured failure when pip output identifies an overlong path."""

    compatibility_error = external_long_path_error(
        component="pip",
        path=fallback_path,
        detail=output,
    )
    if compatibility_error is not None:
        raise compatibility_error


__all__ = ["raise_pip_path_compatibility_error"]
