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

"""Compute tamper-evident identities for staged repair directory trees."""

from __future__ import annotations

import hashlib
from pathlib import Path


class RepairArtifactIntegrityError(RuntimeError):
    """Report an unsafe or changed staged repair artifact."""


def directory_tree_sha256(root: Path) -> str:
    """Hash a staged tree while accepting only non-escaping symbolic links."""

    if root.is_symlink() or _is_junction(root):
        raise RepairArtifactIntegrityError(
            f"Repair artifact root cannot be a link: {root}"
        )
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        raise RepairArtifactIntegrityError(
            f"Repair artifact directory is missing: {resolved_root}"
        )
    digest = hashlib.sha256()
    for path in _tree_entries(root):
        if path.is_symlink():
            target = _safe_symbolic_link_target(
                path,
                root=resolved_root,
            )
            relative = path.relative_to(root).as_posix().encode("utf-8")
            digest.update(
                b"L\0" + relative + b"\0" + target.as_posix().encode("utf-8") + b"\0"
            )
            continue
        if _is_junction(path):
            raise RepairArtifactIntegrityError(
                f"Repair artifact contains a junction or reparse directory: {path}"
            )
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_dir():
            digest.update(b"D\0" + relative + b"\0")
            continue
        if not path.is_file():
            raise RepairArtifactIntegrityError(
                f"Repair artifact contains an unsupported entry: {path}"
            )
        digest.update(b"F\0" + relative + b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _tree_entries(root: Path) -> tuple[Path, ...]:
    """Enumerate entries deterministically without traversing links."""

    entries: list[Path] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            children = tuple(directory.iterdir())
        except OSError as error:
            raise RepairArtifactIntegrityError(
                f"Repair artifact directory is unreadable: {directory}"
            ) from error
        for child in children:
            entries.append(child)
            if child.is_dir() and not child.is_symlink() and not _is_junction(child):
                pending.append(child)
    return tuple(sorted(entries, key=lambda entry: entry.relative_to(root).as_posix()))


def _safe_symbolic_link_target(path: Path, *, root: Path) -> Path:
    """Return a normalized internal link target or reject an escape."""

    try:
        raw_target = path.readlink()
    except OSError as error:
        raise RepairArtifactIntegrityError(
            f"Repair artifact symbolic link is unreadable: {path}"
        ) from error
    if raw_target.is_absolute():
        raise RepairArtifactIntegrityError(
            f"Repair artifact symbolic link escapes staging: {path}"
        )
    resolved_target = (path.parent / raw_target).resolve(strict=False)
    if not resolved_target.is_relative_to(root):
        raise RepairArtifactIntegrityError(
            f"Repair artifact symbolic link escapes staging: {path}"
        )
    return raw_target


def _is_junction(path: Path) -> bool:
    """Return whether a path is a Windows junction without platform branching."""

    checker = getattr(path, "is_junction", None)
    return bool(checker()) if callable(checker) else False


def verify_directory_tree_sha256(root: Path, *, expected: str) -> None:
    """Reject a staged directory whose complete identity has changed."""

    actual = directory_tree_sha256(root)
    if actual != expected.lower():
        raise RepairArtifactIntegrityError(
            f"Repair artifact integrity mismatch: {root}"
        )


__all__ = [
    "RepairArtifactIntegrityError",
    "directory_tree_sha256",
    "verify_directory_tree_sha256",
]
