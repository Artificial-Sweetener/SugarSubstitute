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

"""Read and write Comfy Registry source-ownership metadata safely."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    path_is_relative_to,
)


def read_registry_tracking_file(target_path: Path) -> tuple[Path, ...] | None:
    """Return validated CNR-owned paths or `None` for a non-CNR folder."""

    tracking_path = target_path / ".tracking"
    if not tracking_path.is_file():
        return None
    tracked_files = tuple(
        Path(line.strip())
        for line in tracking_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    validate_registry_tracking_paths(target_path, tracked_files)
    return tracked_files


def write_registry_tracking_file(
    *,
    target_path: Path,
    tracked_files: tuple[Path, ...],
) -> None:
    """Atomically write Comfy Registry ownership metadata using portable paths."""

    validate_registry_tracking_paths(target_path, tracked_files)
    target_path.mkdir(parents=True, exist_ok=True)
    tracking_path = target_path / ".tracking"
    temporary_path = target_path / ".tracking.tmp"
    temporary_path.write_text(
        "\n".join(path.as_posix() for path in tracked_files),
        encoding="utf-8",
    )
    temporary_path.replace(tracking_path)


def validate_registry_tracking_paths(
    root: Path,
    paths: tuple[Path, ...],
) -> None:
    """Reject absolute and escaping ownership paths before mutation."""

    resolved_root = root.resolve()
    for relative_path in paths:
        if relative_path.is_absolute() or not path_is_relative_to(
            (root / relative_path).resolve(),
            resolved_root,
        ):
            raise RuntimeError(
                f"Nodepack ownership contains an unsafe path: {relative_path}"
            )


__all__ = [
    "read_registry_tracking_file",
    "validate_registry_tracking_paths",
    "write_registry_tracking_file",
]
