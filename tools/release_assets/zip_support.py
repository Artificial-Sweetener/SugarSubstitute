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

import os
import stat
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath, PureWindowsPath


ZIP_TIMESTAMP = (2024, 1, 1, 0, 0, 0)


def iter_directory_entries(root_path: Path) -> Iterable[Path]:
    """Yield regular files and symbolic links in deterministic path order."""

    if not root_path.exists():
        raise FileNotFoundError(f"Required directory does not exist: {root_path}")
    if not root_path.is_dir():
        raise ValueError(f"Required path is not a directory: {root_path}")
    entries: list[Path] = []
    for current_root, directory_names, file_names in os.walk(
        root_path,
        followlinks=False,
    ):
        current_path = Path(current_root)
        linked_directories = [
            directory_name
            for directory_name in directory_names
            if (current_path / directory_name).is_symlink()
        ]
        directory_names[:] = [
            directory_name
            for directory_name in directory_names
            if directory_name not in linked_directories
        ]
        entries.extend(current_path / name for name in linked_directories)
        entries.extend(current_path / name for name in file_names)
    yield from sorted(entries, key=_portable_sort_key)


def write_path_to_zip(
    *,
    archive: zipfile.ZipFile,
    source_path: Path,
    archive_name: str,
    permissions: int | None = None,
) -> None:
    """Add one regular file or validated relative symlink to a ZIP."""

    zip_info = zipfile.ZipInfo(
        filename=PurePosixPath(archive_name).as_posix(),
        date_time=ZIP_TIMESTAMP,
    )
    zip_info.create_system = 3
    zip_info.compress_type = zipfile.ZIP_DEFLATED
    if source_path.is_symlink():
        link_target = os.readlink(source_path)
        _validate_relative_symlink(
            archive_name=PurePosixPath(archive_name),
            link_target=link_target,
        )
        zip_info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(
            zip_info,
            link_target.encode("utf-8"),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        return
    archived_permissions = (
        permissions
        if permissions is not None
        else (source_path.stat().st_mode & 0o777) or 0o644
    )
    zip_info.external_attr = (stat.S_IFREG | archived_permissions) << 16
    with source_path.open("rb") as source_file:
        archive.writestr(
            zip_info,
            source_file.read(),
            compress_type=zipfile.ZIP_DEFLATED,
        )


def _portable_sort_key(path: Path) -> str:
    """Return a case-insensitive portable path key."""

    return path.as_posix().lower()


def _validate_relative_symlink(
    *,
    archive_name: PurePosixPath,
    link_target: str,
) -> None:
    """Reject symlink targets that are absolute or escape the archive root."""

    normalized_target = link_target.replace("\\", "/")
    target_path = PurePosixPath(normalized_target)
    if (
        not normalized_target
        or "\x00" in normalized_target
        or target_path.is_absolute()
        or PureWindowsPath(link_target).drive
    ):
        raise ValueError(f"Archive symlink has unsafe target: {archive_name}")
    depth = len(archive_name.parent.parts)
    for part in target_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                raise ValueError(
                    f"Archive symlink target escapes archive: {archive_name}"
                )
            continue
        depth += 1
