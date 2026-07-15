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

"""Tests for compact generation duration formatting."""

from __future__ import annotations

import pytest

from substitute.application.generation.duration_formatting import (
    format_generation_duration,
)


@pytest.mark.parametrize(
    ("duration_ms", "expected"),
    (
        (None, ""),
        (-1.0, ""),
        (850.0, "0.8s"),
        (3200.0, "3.2s"),
        (3000.0, "3s"),
        (42300.0, "42.3s"),
        (188000.0, "3m8s"),
        (4320000.0, "1h12m"),
    ),
)
def test_format_generation_duration_returns_compact_text(
    duration_ms: float | None,
    expected: str,
) -> None:
    """Duration formatting should match queue row and tooltip display rules."""

    assert format_generation_duration(duration_ms) == expected
