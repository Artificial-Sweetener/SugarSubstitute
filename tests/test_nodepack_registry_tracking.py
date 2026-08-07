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

"""Tests for Comfy Registry source-ownership metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.nodepack_registry_tracking import (
    read_registry_tracking_file,
    write_registry_tracking_file,
)


def test_tracking_round_trips_portable_relative_paths(tmp_path: Path) -> None:
    """Persist Manager-readable ownership without platform-specific separators."""

    tracked_files = (Path("package") / "module.py", Path("pyproject.toml"))

    write_registry_tracking_file(
        target_path=tmp_path,
        tracked_files=tracked_files,
    )

    assert (tmp_path / ".tracking").read_text(encoding="utf-8") == (
        "package/module.py\npyproject.toml"
    )
    assert read_registry_tracking_file(tmp_path) == tracked_files


def test_tracking_rejects_paths_outside_the_nodepack(tmp_path: Path) -> None:
    """Prevent malformed ownership metadata from mutating adjacent files."""

    (tmp_path / ".tracking").write_text("../outside.py", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unsafe path"):
        read_registry_tracking_file(tmp_path)
