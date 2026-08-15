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

"""Exchange checksum-verified standalone artifacts with installer qualification."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from uuid import uuid4

from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


@contextmanager
def qualification_standalone_artifact_cache(
    *,
    install_root: Path,
    external_cache_root: Path | None,
) -> Iterator[None]:
    """Stage CI artifacts after the empty-root proof and retain verified results."""

    if external_cache_root is None:
        yield
        return
    resolved_install_root = install_root.resolve()
    resolved_external_root = external_cache_root.resolve()
    if (
        resolved_external_root == resolved_install_root
        or resolved_external_root.is_relative_to(resolved_install_root)
    ):
        raise InstallerLifecycleError(
            "Qualification standalone cache must be outside the clean install root."
        )
    installed_cache_root = (
        resolved_install_root / ".sugarsubstitute-cache" / "standalone"
    )
    _mirror_complete_files(
        source_root=resolved_external_root,
        destination_root=installed_cache_root,
    )
    try:
        yield
    except BaseException:
        raise
    else:
        _mirror_complete_files(
            source_root=installed_cache_root,
            destination_root=resolved_external_root,
        )


def _mirror_complete_files(*, source_root: Path, destination_root: Path) -> None:
    """Mirror complete cache files atomically, preferring same-volume hard links."""

    if not source_root.is_dir():
        return
    for source in source_root.rglob("*"):
        if not source.is_file() or source.name.endswith(".part"):
            continue
        if source.is_symlink():
            raise InstallerLifecycleError(
                f"Qualification standalone cache contains a symlink: {source}"
            )
        relative = source.relative_to(source_root)
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and os.path.samefile(source, destination):
            continue
        temporary = destination.with_name(
            f".{destination.name}.qualification-{os.getpid()}-{uuid4().hex}.tmp"
        )
        try:
            try:
                os.link(source, temporary)
            except OSError:
                shutil.copy2(source, temporary)
            temporary.replace(destination)
        except OSError as error:
            raise InstallerLifecycleError(
                "Could not stage the standalone artifact cache for qualification: "
                f"{source} -> {destination}: {error}"
            ) from error
        finally:
            temporary.unlink(missing_ok=True)


__all__ = ["qualification_standalone_artifact_cache"]
