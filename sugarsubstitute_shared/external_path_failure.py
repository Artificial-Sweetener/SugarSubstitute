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

"""Classify long-path failures emitted by external components."""

from __future__ import annotations

import errno
import ntpath
from pathlib import Path
import re
import sys

from sugarsubstitute_shared.windows_long_paths import (
    exceeds_windows_legacy_path_limit,
    logical_path,
)

_LONG_PATH_ERROR_MARKERS = (
    "filename too long",
    "file name too long",
    "path too long",
    "winerror 206",
    "error_filename_exced_range",
)
_MISSING_PATH_ERROR_MARKERS = (
    "errno 2",
    "no such file or directory",
    "winerror 2",
    "winerror 3",
)
_QUOTED_VALUE = re.compile(r"(?P<quote>['\"])(?P<value>[^'\"\r\n]+)(?P=quote)")


class ExternalLongPathCompatibilityError(RuntimeError):
    """Report a known long-path failure in an external component."""

    def __init__(
        self,
        *,
        component: str,
        path: Path,
        detail: str,
    ) -> None:
        """Retain structured evidence for localized presentation."""

        self.component = component
        self.path = Path(logical_path(path))
        self.detail = detail
        super().__init__(
            f"{component} could not access the long Windows path "
            f"'{self.path}'. {detail}"
        )


def external_long_path_error(
    *,
    component: str,
    path: Path,
    detail: BaseException | str,
) -> ExternalLongPathCompatibilityError | None:
    """Classify explicit and missing-file failures involving overlong paths."""

    if sys.platform != "win32":
        return None
    detail_text = str(detail).strip() or type(detail).__name__
    embedded_paths = _embedded_windows_paths(detail_text)
    supplied_path = Path(logical_path(path))
    long_embedded_paths = tuple(
        candidate
        for candidate in embedded_paths
        if exceeds_windows_legacy_path_limit(candidate)
    )
    supplied_path_is_long = exceeds_windows_legacy_path_limit(supplied_path)
    if not long_embedded_paths and not supplied_path_is_long:
        return None
    winerror = getattr(detail, "winerror", None)
    error_number = getattr(detail, "errno", None)
    normalized = detail_text.casefold()
    explicit_long_path_failure = (
        winerror == 206
        or error_number == errno.ENAMETOOLONG
        or any(marker in normalized for marker in _LONG_PATH_ERROR_MARKERS)
    )
    missing_embedded_path_failure = bool(long_embedded_paths) and any(
        marker in normalized for marker in _MISSING_PATH_ERROR_MARKERS
    )
    if not explicit_long_path_failure and not missing_embedded_path_failure:
        return None
    failing_path = long_embedded_paths[0] if long_embedded_paths else supplied_path
    return ExternalLongPathCompatibilityError(
        component=component,
        path=failing_path,
        detail=detail_text,
    )


def _embedded_windows_paths(detail: str) -> tuple[Path, ...]:
    """Return absolute Windows paths quoted in external process output."""

    return tuple(
        Path(value)
        for match in _QUOTED_VALUE.finditer(detail)
        for value in (logical_path(match.group("value")),)
        if ntpath.isabs(value)
    )


__all__ = ["ExternalLongPathCompatibilityError", "external_long_path_error"]
