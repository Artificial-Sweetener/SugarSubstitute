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

"""Select the host-specific system appearance adapter."""

from __future__ import annotations

import sys

from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProvider,
)
from substitute.infrastructure.appearance.linux_system_appearance import (
    LinuxSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.macos_system_appearance import (
    MacOsSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)
from substitute.infrastructure.appearance.windows_system_appearance import (
    WindowsSystemAppearanceProvider,
)


def build_system_appearance_provider(
    platform_name: str | None = None,
) -> SystemAppearanceProvider:
    """Return the isolated adapter for the requested or current host platform."""

    current_platform = platform_name or sys.platform
    if current_platform == "win32":
        return WindowsSystemAppearanceProvider()
    if current_platform == "darwin":
        return MacOsSystemAppearanceProvider()
    if current_platform.startswith("linux"):
        return LinuxSystemAppearanceProvider()
    return QtSystemAppearanceProvider(adapter_name="qt_fallback")


__all__ = ["build_system_appearance_provider"]
