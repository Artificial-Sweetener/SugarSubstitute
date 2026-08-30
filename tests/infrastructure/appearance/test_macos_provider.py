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

"""Test macOS system appearance adapter attribution."""

from __future__ import annotations

from substitute.domain.appearance import RgbColor, SystemColorScheme
from substitute.infrastructure.appearance.macos_system_appearance import (
    MacOsSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)
from tests.infrastructure.appearance.support import StubQtAppearanceReader


def test_provider_preserves_qt_values_and_relabels_adapter() -> None:
    """Report Qt Cocoa values through the isolated macOS adapter."""

    qt_provider = QtSystemAppearanceProvider(
        reader=StubQtAppearanceReader(SystemColorScheme.DARK, RgbColor(4, 5, 6))
    )

    probe = MacOsSystemAppearanceProvider(qt_provider).probe()

    assert probe.adapter_name == "macos"
    assert probe.snapshot.accent_color == RgbColor(4, 5, 6)
