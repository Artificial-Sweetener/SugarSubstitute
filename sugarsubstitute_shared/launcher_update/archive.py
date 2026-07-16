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

"""Extract launcher ZIP archives without accepting filesystem escapes."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path, PurePosixPath
import zipfile


class SecureArchiveError(RuntimeError):
    """Report an unsafe or malformed launcher bundle archive."""


def safe_extract_zip(*, zip_path: Path, destination_dir: Path) -> None:
    """Extract a ZIP while rejecting traversal and symbolic-link entries."""

    destination_root = destination_dir.resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            archive_name = _validated_archive_name(member)
            target_path = (destination_root / archive_name).resolve()
            if not target_path.is_relative_to(destination_root):
                raise SecureArchiveError(
                    f"Archive entry escapes destination: {member.filename}"
                )
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            archived_permissions = (member.external_attr >> 16) & 0o777
            if archived_permissions:
                target_path.chmod(archived_permissions)


def _validated_archive_name(member: zipfile.ZipInfo) -> PurePosixPath:
    """Return a normalized archive name or reject an unsafe entry."""

    if stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
        raise SecureArchiveError(
            f"Archive entry must not be a symlink: {member.filename}"
        )
    archive_path = PurePosixPath(member.filename.replace("\\", "/"))
    if archive_path.is_absolute() or ".." in archive_path.parts:
        raise SecureArchiveError(f"Archive entry has unsafe path: {member.filename}")
    if not archive_path.parts:
        raise SecureArchiveError("Archive entry has an empty path.")
    return archive_path


__all__ = ["SecureArchiveError", "safe_extract_zip"]
