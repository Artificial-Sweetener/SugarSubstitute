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

"""Provide macOS appearance through Qt's Cocoa-backed native palette."""

from __future__ import annotations

from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)


class MacOsSystemAppearanceProvider:
    """Read macOS scheme and accent values exposed by Qt's Cocoa plugin."""

    def __init__(self, qt_provider: QtSystemAppearanceProvider | None = None) -> None:
        """Store the independently testable Qt-backed reader."""

        self._qt_provider = qt_provider or QtSystemAppearanceProvider()

    def probe(self) -> SystemAppearanceProbe:
        """Return current Cocoa-backed appearance values and sources."""

        qt_probe = self._qt_provider.probe()
        return SystemAppearanceProbe(
            snapshot=qt_probe.snapshot,
            adapter_name="macos",
            color_scheme_source=qt_probe.color_scheme_source,
            accent_color_source=qt_probe.accent_color_source,
        )


__all__ = ["MacOsSystemAppearanceProvider"]
