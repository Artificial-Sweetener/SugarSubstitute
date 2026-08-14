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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal
import zipfile


class SecureArchiveError(RuntimeError):
    """Report an unsafe or malformed launcher bundle archive."""


@dataclass(frozen=True, slots=True)
class _ArchiveMember:
    """Describe one validated archive member before filesystem mutation."""

    info: zipfile.ZipInfo
    path: PurePosixPath
    kind: Literal["directory", "file", "symlink"]
    link_target: str | None = None


def safe_extract_zip(*, zip_path: Path, destination_dir: Path) -> None:
    """Extract a ZIP while preserving only contained relative symlinks."""

    destination_root = destination_dir.resolve()
    if destination_dir.exists() and any(destination_dir.iterdir()):
        raise SecureArchiveError(
            f"Archive destination must be empty: {destination_dir}"
        )
    destination_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members = _validated_members(archive)
        for member in members:
            if member.kind == "symlink":
                continue
            target_path = destination_root.joinpath(*member.path.parts)
            if member.kind == "directory":
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with (
                archive.open(member.info) as source,
                target_path.open("wb") as destination,
            ):
                shutil.copyfileobj(source, destination)
            archived_permissions = (member.info.external_attr >> 16) & 0o777
            if archived_permissions:
                target_path.chmod(archived_permissions)
        for member in members:
            if member.kind != "symlink" or member.link_target is None:
                continue
            target_path = destination_root.joinpath(*member.path.parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.symlink_to(
                member.link_target,
                target_is_directory=_symlink_targets_directory(member, members),
            )


def _validated_members(archive: zipfile.ZipFile) -> tuple[_ArchiveMember, ...]:
    """Validate every member and cross-member symlink relationship first."""

    members = tuple(_validated_member(archive, info) for info in archive.infolist())
    paths = [member.path for member in members]
    if len(paths) != len(set(paths)):
        raise SecureArchiveError("Archive contains duplicate member paths.")
    symlink_paths = {member.path for member in members if member.kind == "symlink"}
    for member in members:
        for parent in member.path.parents:
            if parent in symlink_paths:
                raise SecureArchiveError(
                    f"Archive entry traverses symlink prefix: {member.info.filename}"
                )
    return members


def _validated_member(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
) -> _ArchiveMember:
    """Return one normalized archive member or reject it before extraction."""

    archive_path = _validated_archive_name(member)
    mode = member.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if member.is_dir():
        return _ArchiveMember(member, archive_path, "directory")
    if file_type == stat.S_IFLNK:
        try:
            link_target = archive.read(member).decode("utf-8")
        except UnicodeDecodeError as error:
            raise SecureArchiveError(
                f"Archive symlink target is not UTF-8: {member.filename}"
            ) from error
        _validate_symlink_target(archive_path, link_target)
        return _ArchiveMember(member, archive_path, "symlink", link_target)
    if file_type not in {0, stat.S_IFREG}:
        raise SecureArchiveError(
            f"Archive entry has unsupported type: {member.filename}"
        )
    return _ArchiveMember(member, archive_path, "file")


def _validated_archive_name(member: zipfile.ZipInfo) -> PurePosixPath:
    """Return a normalized archive name or reject an unsafe entry."""

    archive_path = PurePosixPath(member.filename.replace("\\", "/"))
    if (
        archive_path.is_absolute()
        or PureWindowsPath(member.filename).drive
        or ".." in archive_path.parts
    ):
        raise SecureArchiveError(f"Archive entry has unsafe path: {member.filename}")
    if not archive_path.parts:
        raise SecureArchiveError("Archive entry has an empty path.")
    return archive_path


def _validate_symlink_target(link_path: PurePosixPath, link_target: str) -> None:
    """Require one UTF-8 relative target that stays inside the bundle."""

    normalized_target = link_target.replace("\\", "/")
    target_path = PurePosixPath(normalized_target)
    if (
        not normalized_target
        or "\x00" in normalized_target
        or target_path.is_absolute()
        or PureWindowsPath(link_target).drive
    ):
        raise SecureArchiveError(f"Archive symlink has unsafe target: {link_path}")
    depth = len(link_path.parent.parts)
    for part in target_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                raise SecureArchiveError(
                    f"Archive symlink target escapes bundle: {link_path}"
                )
            continue
        depth += 1


def _symlink_targets_directory(
    link: _ArchiveMember,
    members: tuple[_ArchiveMember, ...],
) -> bool:
    """Infer the Windows symlink kind from another validated archive member."""

    assert link.link_target is not None
    target_parts = _normalized_target_parts(link.path, link.link_target)
    target = PurePosixPath(*target_parts)
    return any(
        member.path == target and member.kind == "directory" for member in members
    ) or any(target in member.path.parents for member in members)


def _normalized_target_parts(
    link_path: PurePosixPath,
    link_target: str,
) -> tuple[str, ...]:
    """Return normalized contained target components for one validated link."""

    parts = list(link_path.parent.parts)
    for part in PurePosixPath(link_target.replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            parts.pop()
        else:
            parts.append(part)
    return tuple(parts)


__all__ = ["SecureArchiveError", "safe_extract_zip"]
