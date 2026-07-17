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

"""Provide deterministic ZIP primitives shared by release builders."""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath


ZIP_TIMESTAMP = (2024, 1, 1, 0, 0, 0)


def iter_directory_files(root_path: Path) -> Iterable[Path]:
    """Yield files below one directory in deterministic path order."""

    if not root_path.exists():
        raise FileNotFoundError(f"Required directory does not exist: {root_path}")
    if not root_path.is_dir():
        raise ValueError(f"Required path is not a directory: {root_path}")
    yield from (
        path
        for path in sorted(root_path.rglob("*"), key=_portable_sort_key)
        if path.is_file()
    )


def write_file_to_zip(
    *,
    archive: zipfile.ZipFile,
    source_path: Path,
    archive_name: str,
    permissions: int | None = None,
) -> None:
    """Add one file with stable metadata and preserved executable permissions."""

    zip_info = zipfile.ZipInfo(
        filename=PurePosixPath(archive_name).as_posix(),
        date_time=ZIP_TIMESTAMP,
    )
    zip_info.compress_type = zipfile.ZIP_DEFLATED
    archived_permissions = permissions or (source_path.stat().st_mode & 0o777) or 0o644
    zip_info.external_attr = archived_permissions << 16
    with source_path.open("rb") as source_file:
        archive.writestr(
            zip_info,
            source_file.read(),
            compress_type=zipfile.ZIP_DEFLATED,
        )


def _portable_sort_key(path: Path) -> str:
    """Return a case-insensitive portable path key."""

    return path.as_posix().lower()
