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

"""Inspect Comfy nodepack workspace folders without mutating them."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack


def core_nodepack_installed(workspace: Path, nodepack: CoreComfyNodepack) -> bool:
    """Return whether a required core nodepack has all sentinel files."""

    root = workspace / nodepack.expected_folder
    return root.is_dir() and all(
        (root / sentinel).exists() for sentinel in nodepack.sentinel_files
    )


def source_contains_sentinels(
    source_path: Path,
    nodepack: CoreComfyNodepack,
) -> bool:
    """Return whether a source checkout contains the nodepack's sentinel files."""

    return source_path.is_dir() and all(
        (source_path / sentinel).exists() for sentinel in nodepack.sentinel_files
    )


def path_is_relative_to(path: Path, parent: Path) -> bool:
    """Return whether `path` is syntactically inside `parent`."""

    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def nodepack_has_git_metadata(target_path: Path) -> bool:
    """Return whether the custom node folder is git-managed."""

    return (target_path / ".git").exists()


def nodepack_has_registry_metadata(target_path: Path) -> bool:
    """Return whether the custom node folder is Comfy Registry-managed."""

    return (target_path / "pyproject.toml").is_file() and (
        target_path / ".tracking"
    ).is_file()


def tracked_source_files(source_path: Path) -> tuple[Path, ...]:
    """Return files that should be recorded as Registry-managed archive contents."""

    ignored_directory_names = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
        "tests",
    }
    ignored_file_names = {".tracking"}
    tracked_files: list[Path] = []
    for file_path in sorted(source_path.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(source_path)
        if relative_path.name in ignored_file_names:
            continue
        if any(part in ignored_directory_names for part in relative_path.parts[:-1]):
            continue
        tracked_files.append(relative_path)
    return tuple(tracked_files)


__all__ = [
    "core_nodepack_installed",
    "nodepack_has_git_metadata",
    "nodepack_has_registry_metadata",
    "path_is_relative_to",
    "source_contains_sentinels",
    "tracked_source_files",
]
