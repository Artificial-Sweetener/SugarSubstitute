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

"""Read portable appearance hints from the active Qt application."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from substitute.application.ports.system_appearance_provider import (
    SystemAppearanceProbe,
)
from substitute.domain.appearance import (
    RgbColor,
    SystemAppearanceSnapshot,
    SystemColorScheme,
)


class QtSystemAppearanceReader:
    """Read Qt style hints and palette values as normalized domain colors."""

    def read_color_scheme(self) -> tuple[SystemColorScheme | None, str | None]:
        """Return Qt's system scheme and the native hint used to derive it."""

        application = cast(QGuiApplication | None, QGuiApplication.instance())
        if application is None:
            return None, None
        color_scheme = application.styleHints().colorScheme()
        if color_scheme is Qt.ColorScheme.Dark:
            return SystemColorScheme.DARK, "qt_style_hints"
        if color_scheme is Qt.ColorScheme.Light:
            return SystemColorScheme.LIGHT, "qt_style_hints"
        window_color = QColor(application.palette().color(QPalette.ColorRole.Window))
        if not window_color.isValid():
            return None, None
        return _infer_palette_color_scheme(window_color), "qt_palette"

    def read_accent_color(self) -> RgbColor | None:
        """Return Qt's native accent palette role when it is valid."""

        application = cast(QGuiApplication | None, QGuiApplication.instance())
        if application is None:
            return None
        color = QColor(application.palette().color(QPalette.ColorRole.Accent))
        if not color.isValid():
            return None
        return RgbColor(color.red(), color.green(), color.blue())


class QtSystemAppearanceProvider:
    """Provide a portable Qt-only system appearance fallback."""

    def __init__(
        self,
        *,
        adapter_name: str = "qt",
        reader: QtSystemAppearanceReader | None = None,
    ) -> None:
        """Store the adapter label and injectable Qt reader."""

        self._adapter_name = adapter_name
        self._reader = reader or QtSystemAppearanceReader()

    def probe(self) -> SystemAppearanceProbe:
        """Return one fresh appearance probe from active Qt state."""

        color_scheme, color_scheme_source = self._reader.read_color_scheme()
        accent_color = self._reader.read_accent_color()
        return SystemAppearanceProbe(
            snapshot=SystemAppearanceSnapshot(
                color_scheme=color_scheme,
                accent_color=accent_color,
            ),
            adapter_name=self._adapter_name,
            color_scheme_source=color_scheme_source,
            accent_color_source="qt_palette" if accent_color is not None else None,
        )


def _infer_palette_color_scheme(window_color: QColor) -> SystemColorScheme:
    """Infer a color scheme from Qt's native window-background palette role."""

    if window_color.lightness() < 128:
        return SystemColorScheme.DARK
    return SystemColorScheme.LIGHT


__all__ = ["QtSystemAppearanceProvider", "QtSystemAppearanceReader"]
