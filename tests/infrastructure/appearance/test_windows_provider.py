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

"""Test Windows system appearance field ownership and fallback."""

from __future__ import annotations

from substitute.domain.appearance import RgbColor, SystemColorScheme
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.windows_system_appearance import (
    WindowsSystemAppearanceProvider,
)
from tests.infrastructure.appearance.support import StubQtAppearanceReader


def test_provider_prefers_native_fields_and_fills_missing_accent() -> None:
    """Keep Windows native and Qt fallback responsibilities field-specific."""

    qt_provider = QtSystemAppearanceProvider(
        reader=StubQtAppearanceReader(SystemColorScheme.LIGHT, RgbColor(1, 2, 3))
    )
    provider = WindowsSystemAppearanceProvider(
        scheme_reader=lambda: SystemColorScheme.DARK,
        accent_reader=lambda: None,
        qt_provider=qt_provider,
    )

    probe = provider.probe()

    assert probe.snapshot.color_scheme is SystemColorScheme.DARK
    assert probe.snapshot.accent_color == RgbColor(1, 2, 3)
    assert probe.color_scheme_source == "windows_registry"
    assert probe.accent_color_source == "qt_palette"
