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

"""Translate splash command-line values into presentation identities."""

from __future__ import annotations

from substitute.domain.appearance import AppearanceThemeMode
from substitute.presentation.shell.window_effects import ShellBackdropMode


def theme_mode_from_argument(raw_value: str | None) -> AppearanceThemeMode:
    """Return the safe theme mode represented by one splash argument."""

    if raw_value is None:
        return AppearanceThemeMode.DARK
    try:
        return AppearanceThemeMode(raw_value)
    except ValueError:
        return AppearanceThemeMode.DARK


def backdrop_mode_from_argument(raw_value: str | None) -> ShellBackdropMode | None:
    """Return the safe backdrop mode represented by one splash argument."""

    if raw_value is None:
        return ShellBackdropMode.MICA
    if raw_value == "none":
        return None
    if raw_value == ShellBackdropMode.ACRYLIC.value:
        return ShellBackdropMode.ACRYLIC
    return ShellBackdropMode.MICA


__all__ = ["backdrop_mode_from_argument", "theme_mode_from_argument"]
