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

"""Test portable Windows path representation policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from sugarsubstitute_shared.windows_long_paths import (
    extended_length_path,
    logical_path,
)


def test_extended_length_path_maps_drive_and_unc_paths() -> None:
    """Windows drive and UNC roots should use their required namespace forms."""

    assert extended_length_path(r"C:\deep\file.txt") == r"\\?\C:\deep\file.txt"
    assert (
        extended_length_path(r"\\server\share\deep\file.txt")
        == r"\\?\UNC\server\share\deep\file.txt"
    )


def test_extended_length_path_rejects_relative_paths() -> None:
    """Relative paths should fail before entering the minimally parsed namespace."""

    with pytest.raises(ValueError, match="must be absolute"):
        extended_length_path(Path("relative") / "file.txt")


def test_logical_path_removes_drive_and_unc_transport_prefixes() -> None:
    """Transport prefixes should never leak into user-visible path strings."""

    assert logical_path(r"\\?\C:\deep\file.txt") == r"C:\deep\file.txt"
    assert (
        logical_path(r"\\?\UNC\server\share\deep\file.txt")
        == r"\\server\share\deep\file.txt"
    )
