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

"""Tests for Settings cache size formatting."""

from __future__ import annotations

import pytest

from substitute.presentation.settings.settings_cache_size import format_cache_size


@pytest.mark.parametrize(
    ("byte_count", "expected"),
    (
        (0, "0 bytes"),
        (1, "1 byte"),
        (1023, "1023 bytes"),
        (1024, "1.00 KB"),
        (1536, "1.50 KB"),
        (1024 * 1024, "1.00 MB"),
        (1536 * 1024, "1.50 MB"),
        (1024 * 1024 * 1024, "1.00 GB"),
        (1024 * 1024 * 1024 * 1024, "1.00 TB"),
    ),
)
def test_format_cache_size_progresses_through_readable_units(
    byte_count: int,
    expected: str,
) -> None:
    """Cache size formatting should progress from bytes through terabytes."""

    assert format_cache_size(byte_count) == expected
