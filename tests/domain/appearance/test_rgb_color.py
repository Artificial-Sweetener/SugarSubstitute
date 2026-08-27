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

"""Test normalized sRGB domain value invariants."""

from __future__ import annotations

import pytest

from substitute.domain.appearance import RgbColor


def test_rgb_color_rejects_invalid_hex_and_channels() -> None:
    """Reject malformed hexadecimal values and out-of-range channels."""

    with pytest.raises(ValueError, match="#RRGGBB"):
        RgbColor.from_hex("E91E63")
    with pytest.raises(ValueError, match="red"):
        RgbColor(red=-1, green=0, blue=0)
    with pytest.raises(ValueError, match="blue"):
        RgbColor(red=0, green=0, blue=256)
