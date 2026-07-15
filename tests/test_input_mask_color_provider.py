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

"""Tests for input-canvas mask color Qt adaptation."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtGui import QColor

import substitute.presentation.canvas.input.mask_color_provider as mask_color_provider


def test_input_mask_color_returns_theme_color_for_first_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first mask should keep the current theme accent color."""

    base_color = QColor.fromHsv(30, 40, 50)
    monkeypatch.setattr(mask_color_provider, "themeColor", lambda: base_color)

    assert mask_color_provider.input_mask_color(0, 4) == base_color


def test_input_mask_color_adapts_domain_hue_to_vivid_qcolor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Additional masks should use vivid Qt colors from the domain hue policy."""

    monkeypatch.setattr(
        mask_color_provider,
        "themeColor",
        lambda: QColor.fromHsv(30, 40, 50),
    )

    hue, saturation, value, _alpha = cast(
        tuple[int, int, int, int],
        mask_color_provider.input_mask_color(1, 2).getHsv(),
    )

    assert hue == 210
    assert saturation == 200
    assert value == 220
