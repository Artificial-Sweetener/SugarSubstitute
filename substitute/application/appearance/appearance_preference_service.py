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

"""Coordinate appearance preference loading, normalization, and updates."""

from __future__ import annotations

import re

from substitute.application.ports.appearance_preference_repository import (
    AppearancePreferenceRepository,
)
from substitute.domain.appearance import (
    APPEARANCE_PREFERENCES_SCHEMA_VERSION,
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    default_appearance_preferences,
)

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-F]{6}$")


class AppearancePreferenceService:
    """Own normalized appearance preference use cases."""

    def __init__(self, repository: AppearancePreferenceRepository) -> None:
        """Store the appearance preference repository."""

        self._repository = repository

    def load_preferences(self) -> AppearancePreferences:
        """Load appearance preferences and normalize persisted values."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> AppearancePreferences:
        """Return the default appearance preference snapshot."""

        return default_appearance_preferences()

    def save_preferences(self, preferences: AppearancePreferences) -> None:
        """Persist normalized appearance preferences."""

        self._repository.save(self._normalize(preferences))

    def set_theme_mode(
        self,
        theme_mode: AppearanceThemeMode,
    ) -> AppearancePreferences:
        """Persist one theme-mode update and return the new snapshot."""

        preferences = self.load_preferences().with_theme_mode(theme_mode)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_accent_source(
        self,
        accent_source: AppearanceAccentSource,
    ) -> AppearancePreferences:
        """Persist one accent-source update and return the new snapshot."""

        preferences = self.load_preferences().with_accent_source(accent_source)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_custom_accent_color(self, color: str) -> AppearancePreferences:
        """Persist one custom accent color update and return the new snapshot."""

        preferences = self.load_preferences().with_custom_accent_color(color)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_custom_warning_color(self, color: str | None) -> AppearancePreferences:
        """Persist one warning color override and return the new snapshot."""

        preferences = self.load_preferences().with_custom_warning_color(color)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_warning_color_mode(
        self,
        mode: AppearanceWarningColorMode,
    ) -> AppearancePreferences:
        """Persist one warning color mode and return the new snapshot."""

        preferences = self.load_preferences().with_warning_color_mode(mode)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_custom_error_color(self, color: str | None) -> AppearancePreferences:
        """Persist one error color override and return the new snapshot."""

        preferences = self.load_preferences().with_custom_error_color(color)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_error_color_mode(
        self,
        mode: AppearanceErrorColorMode,
    ) -> AppearancePreferences:
        """Persist one error color mode and return the new snapshot."""

        preferences = self.load_preferences().with_error_color_mode(mode)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> AppearancePreferences:
        """Persist one backdrop-mode update and return the new snapshot."""

        preferences = self.load_preferences().with_backdrop_mode(backdrop_mode)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def _normalize(
        self,
        preferences: AppearancePreferences,
    ) -> AppearancePreferences:
        """Return appearance preferences with valid schema, enums, and accent color."""

        custom_accent_color = _normalized_required_color(
            preferences.custom_accent_color,
            fallback=DEFAULT_CUSTOM_ACCENT_COLOR,
        )
        return AppearancePreferences(
            schema_version=APPEARANCE_PREFERENCES_SCHEMA_VERSION,
            theme_mode=preferences.theme_mode
            if isinstance(preferences.theme_mode, AppearanceThemeMode)
            else AppearanceThemeMode.DARK,
            accent_source=preferences.accent_source
            if isinstance(preferences.accent_source, AppearanceAccentSource)
            else AppearanceAccentSource.CUSTOM,
            custom_accent_color=custom_accent_color,
            backdrop_mode=preferences.backdrop_mode
            if isinstance(preferences.backdrop_mode, AppearanceBackdropMode)
            else AppearanceBackdropMode.MICA_ALT,
            warning_color_mode=preferences.warning_color_mode
            if isinstance(preferences.warning_color_mode, AppearanceWarningColorMode)
            else AppearanceWarningColorMode.DEFAULT,
            error_color_mode=preferences.error_color_mode
            if isinstance(preferences.error_color_mode, AppearanceErrorColorMode)
            else AppearanceErrorColorMode.DEFAULT,
            custom_warning_color=_normalized_optional_color(
                preferences.custom_warning_color
            ),
            custom_error_color=_normalized_optional_color(
                preferences.custom_error_color
            ),
        )


def _normalized_required_color(color: str, *, fallback: str) -> str:
    """Return a valid uppercase hex color or the supplied fallback."""

    normalized = color.strip().upper()
    if _HEX_COLOR_PATTERN.fullmatch(normalized) is None:
        return fallback
    return normalized


def _normalized_optional_color(color: str | None) -> str | None:
    """Return a valid uppercase optional hex color or no override."""

    if color is None:
        return None
    normalized = color.strip().upper()
    if _HEX_COLOR_PATTERN.fullmatch(normalized) is None:
        return None
    return normalized


__all__ = ["AppearancePreferenceService"]
