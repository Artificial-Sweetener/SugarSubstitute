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

"""Render actionable launcher failure details for presentation surfaces."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.external_path_failure import (
    ExternalLongPathCompatibilityError,
)
from sugarsubstitute_shared.windows_long_paths import WindowsPathComponentTooLongError


def launcher_failure_detail(error: Exception) -> str:
    """Render structured Windows path failures as actionable launcher text."""

    if isinstance(error, WindowsPathComponentTooLongError):
        return launcher_text(
            "Windows limits each file or folder name to 255 characters. Shorten "
            "the name in %1, then try again.",
            error.path,
        )
    if isinstance(error, ExternalLongPathCompatibilityError):
        return launcher_text(
            "%1 could not use this long Windows path even though SugarSubstitute "
            "can: %2. Choose a shorter folder for this operation, or enable Win32 "
            "long paths in Windows, then try again.",
            error.component,
            error.path,
        )
    return str(error)


__all__ = ["launcher_failure_detail"]
