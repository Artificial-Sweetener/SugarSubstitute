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

"""Read Windows theme and accent values with portable Qt fallbacks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor

from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.domain.appearance import (
    RgbColor,
    SystemAppearanceSnapshot,
    SystemColorScheme,
)
from substitute.infrastructure.appearance.qt_system_appearance import (
    QtSystemAppearanceProvider,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.appearance.windows")
WindowsSchemeReader = Callable[[], SystemColorScheme | None]
WindowsAccentReader = Callable[[], RgbColor | None]


class WindowsSystemAppearanceProvider:
    """Prefer native Windows personalization values and fill gaps through Qt."""

    def __init__(
        self,
        *,
        scheme_reader: WindowsSchemeReader | None = None,
        accent_reader: WindowsAccentReader | None = None,
        qt_provider: QtSystemAppearanceProvider | None = None,
    ) -> None:
        """Store native readers and the portable fallback adapter."""

        self._scheme_reader = scheme_reader or read_windows_color_scheme
        self._accent_reader = accent_reader or read_windows_accent_color
        self._qt_provider = qt_provider or QtSystemAppearanceProvider()

    def probe(self) -> SystemAppearanceProbe:
        """Return one fresh Windows appearance snapshot."""

        native_scheme = self._scheme_reader()
        native_accent = self._accent_reader()
        fallback = self._qt_provider.probe()
        color_scheme = native_scheme or fallback.snapshot.color_scheme
        accent_color = native_accent or fallback.snapshot.accent_color
        return SystemAppearanceProbe(
            snapshot=SystemAppearanceSnapshot(color_scheme, accent_color),
            adapter_name="windows",
            color_scheme_source=(
                "windows_registry"
                if native_scheme is not None
                else fallback.color_scheme_source
            ),
            accent_color_source=(
                "windows_accent"
                if native_accent is not None
                else fallback.accent_color_source
            ),
        )


def read_windows_color_scheme() -> SystemColorScheme | None:
    """Read the current app theme from Windows personalization settings."""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            raw_value, _value_type = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except (OSError, ImportError) as error:
        log_warning(
            _LOGGER,
            "Failed to read Windows application color scheme",
            error=repr(error),
        )
        return None
    if raw_value == 0:
        return SystemColorScheme.DARK
    if raw_value == 1:
        return SystemColorScheme.LIGHT
    return None


def read_windows_accent_color() -> RgbColor | None:
    """Read the current Windows accent using available native helpers."""

    try:
        import winaccent  # type: ignore[import-untyped]

        accent_value = getattr(winaccent, "accent", None)
        if isinstance(accent_value, str):
            return RgbColor.from_hex(accent_value)
    except (ModuleNotFoundError, ValueError):
        pass
    try:
        from qframelesswindow.utils import win32_utils  # type: ignore[import-untyped]

        color = win32_utils.getSystemAccentColor()
        if isinstance(color, QColor) and color.isValid():
            return RgbColor(color.red(), color.green(), color.blue())
    except (AttributeError, ImportError, RuntimeError) as error:
        log_warning(
            _LOGGER,
            "Failed to read Windows accent color",
            error=repr(error),
        )
    return None


__all__ = [
    "WindowsSystemAppearanceProvider",
    "read_windows_accent_color",
    "read_windows_color_scheme",
]
