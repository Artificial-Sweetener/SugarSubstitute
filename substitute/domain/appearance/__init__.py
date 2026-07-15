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

"""Expose domain models for persisted application appearance preferences."""

from substitute.domain.appearance.models import (
    APPEARANCE_PREFERENCES_SCHEMA_VERSION,
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    RgbColor,
    SemanticPalette,
    default_appearance_preferences,
)
from substitute.domain.appearance.system_appearance import (
    SystemAppearanceSnapshot,
    SystemColorScheme,
)

__all__ = [
    "APPEARANCE_PREFERENCES_SCHEMA_VERSION",
    "DEFAULT_CUSTOM_ACCENT_COLOR",
    "AppearanceAccentSource",
    "AppearanceBackdropMode",
    "AppearanceErrorColorMode",
    "AppearancePreferences",
    "AppearanceThemeMode",
    "AppearanceWarningColorMode",
    "RgbColor",
    "SemanticPalette",
    "SystemAppearanceSnapshot",
    "SystemColorScheme",
    "default_appearance_preferences",
]
