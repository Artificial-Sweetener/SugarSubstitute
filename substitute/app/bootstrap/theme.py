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

"""Apply shared QFluent theme and accent settings for Substitute Qt processes."""

from __future__ import annotations

from PySide6.QtGui import QColor

from substitute.domain.appearance import (
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceThemeMode,
)


def configure_theme(
    *,
    theme_mode: AppearanceThemeMode = AppearanceThemeMode.DARK,
    accent_color: str = DEFAULT_CUSTOM_ACCENT_COLOR,
) -> None:
    """Apply Substitute's requested QFluent theme mode and accent color."""

    from qfluentwidgets import Theme, setTheme, setThemeColor  # type: ignore[import-untyped]

    setTheme(_qfluent_theme_value(theme_mode=theme_mode, theme_namespace=Theme))
    setThemeColor(QColor(accent_color))


def configure_accent_color(*, accent_color: str) -> None:
    """Apply only Substitute's requested QFluent accent color."""

    from qfluentwidgets import setThemeColor

    setThemeColor(QColor(accent_color))


def _qfluent_theme_value(
    *,
    theme_mode: AppearanceThemeMode,
    theme_namespace: object,
) -> object:
    """Return the qfluentwidgets theme enum value for one appearance theme mode."""

    mapping = {
        AppearanceThemeMode.LIGHT: "LIGHT",
        AppearanceThemeMode.DARK: "DARK",
    }
    if theme_mode is AppearanceThemeMode.AUTO:
        raise ValueError("Auto theme must be resolved before QFluent configuration")
    return getattr(theme_namespace, mapping[theme_mode])


__all__ = ["configure_accent_color", "configure_theme"]
