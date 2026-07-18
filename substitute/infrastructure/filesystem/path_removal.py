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

"""Remove application-owned paths without assuming one permission model."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
import os
from pathlib import Path
import shutil
import stat

PathRemovalOperation = Callable[[str], object]


def remove_app_owned_path(path: Path) -> None:
    """Remove one app-owned file, link, or directory tree when present."""

    owned_path = path.expanduser().absolute()
    if owned_path.is_symlink():
        _unlink_owned_path(owned_path, is_symlink=True)
        return
    if owned_path.is_dir():
        shutil.rmtree(
            owned_path,
            onexc=partial(_repair_permissions_and_retry, owned_root=owned_path),
        )
        return
    _unlink_owned_path(owned_path, is_symlink=False)


def _unlink_owned_path(path: Path, *, is_symlink: bool) -> None:
    """Unlink one owned file or link and repair only its own read-only mode."""

    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        if not is_symlink:
            _add_owner_permissions(path, stat.S_IWUSR)
        path.unlink(missing_ok=True)


def _repair_permissions_and_retry(
    operation: PathRemovalOperation,
    failed_path: str,
    error: BaseException,
    *,
    owned_root: Path,
) -> None:
    """Repair an owned path after a permission failure and retry once."""

    if not isinstance(error, PermissionError):
        raise error
    failed = Path(failed_path).absolute()
    mode = failed.lstat().st_mode
    if not stat.S_ISLNK(mode):
        permissions = stat.S_IWUSR
        if stat.S_ISDIR(mode):
            permissions |= stat.S_IXUSR
        _add_owner_permissions(failed, permissions, current_mode=mode)
    parent = failed.parent
    if _is_within(parent, owned_root):
        _add_owner_permissions(parent, stat.S_IWUSR | stat.S_IXUSR)
    operation(failed_path)


def _add_owner_permissions(
    path: Path,
    permissions: int,
    *,
    current_mode: int | None = None,
) -> None:
    """Add owner permissions while preserving every existing mode bit."""

    mode = path.lstat().st_mode if current_mode is None else current_mode
    os.chmod(path, mode | permissions)


def _is_within(candidate: Path, root: Path) -> bool:
    """Return whether a lexical path remains inside the owned removal root."""

    return candidate == root or candidate.is_relative_to(root)


__all__ = ["remove_app_owned_path"]
