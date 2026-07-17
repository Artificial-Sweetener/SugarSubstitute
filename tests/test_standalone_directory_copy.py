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

"""Verify concurrent standalone package-tree hydration."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.standalone_environment.directory_copy import (
    ConcurrentDirectoryCopier,
    DirectoryCopyProgress,
)


def test_concurrent_directory_copier_preserves_tree_and_reports_progress(
    tmp_path: Path,
) -> None:
    """Large package trees should copy completely with monotonic progress."""

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    for index in range(125):
        path = source / f"package_{index % 5}" / f"module_{index}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"VALUE = {index}\n", encoding="utf-8")
    (source / "empty-package").mkdir()
    progress: list[DirectoryCopyProgress] = []

    ConcurrentDirectoryCopier(parallelism=8).copy(
        source,
        destination,
        on_progress=progress.append,
    )

    assert (destination / "package_4" / "module_124.py").read_text(
        encoding="utf-8"
    ) == "VALUE = 124\n"
    assert (destination / "empty-package").is_dir()
    assert progress
    assert progress[-1].copied_entries == 125
    assert progress[-1].total_entries == 125
    assert [item.copied_entries for item in progress] == sorted(
        item.copied_entries for item in progress
    )


@pytest.mark.platforms("linux", "macos")
def test_concurrent_directory_copier_rewrites_internal_absolute_symlink(
    tmp_path: Path,
) -> None:
    """Relocated environments should not retain absolute links into the master."""

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    target = source / "package" / "data.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"data")
    link = source / "package" / "current.bin"
    link.symlink_to(target)

    ConcurrentDirectoryCopier(parallelism=2).copy(source, destination)

    copied_link = destination / "package" / "current.bin"
    assert copied_link.is_symlink()
    assert copied_link.resolve() == destination / "package" / "data.bin"
