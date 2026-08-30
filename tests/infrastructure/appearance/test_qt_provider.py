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

"""Test normalized Qt system appearance fallback behavior."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from substitute.domain.appearance import RgbColor, SystemColorScheme
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
    _infer_palette_color_scheme,
)
from tests.infrastructure.appearance.support import StubQtAppearanceReader


def test_provider_normalizes_style_hint_and_palette_sources() -> None:
    """Expose normalized Qt values without leaking toolkit types."""

    provider = QtSystemAppearanceProvider(
        reader=StubQtAppearanceReader(SystemColorScheme.DARK, RgbColor(10, 20, 30))
    )

    probe = provider.probe()

    assert probe.snapshot.color_scheme is SystemColorScheme.DARK
    assert probe.snapshot.accent_color == RgbColor(10, 20, 30)
    assert probe.color_scheme_source == "qt_style_hints"
    assert probe.accent_color_source == "qt_palette"


@pytest.mark.parametrize(
    ("window_color", "expected"),
    [("#202020", SystemColorScheme.DARK), ("#F8F8F8", SystemColorScheme.LIGHT)],
)
def test_palette_scheme_fallback(
    window_color: str,
    expected: SystemColorScheme,
) -> None:
    """Infer a stable scheme when the plugin lacks explicit style hints."""

    assert _infer_palette_color_scheme(QColor(window_color)) is expected
