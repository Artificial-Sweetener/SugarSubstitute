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

"""Define the appearance runtime port consumed by Settings presentation code."""

from __future__ import annotations

from typing import Protocol

from substitute.application.appearance import ResolvedAppearance
from substitute.domain.appearance import (
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
)


class AppearanceRuntimeProtocol(Protocol):
    """Describe appearance runtime behavior consumed by the settings UI."""

    def load_preferences(self) -> AppearancePreferences:
        """Load the current persisted appearance preferences."""

    def resolve_preferences(self) -> ResolvedAppearance:
        """Resolve the current appearance snapshot for display."""

    def set_theme_mode(self, theme_mode: AppearanceThemeMode) -> ResolvedAppearance:
        """Persist one theme-mode update."""

    def set_accent_source(
        self,
        accent_source: AppearanceAccentSource,
    ) -> ResolvedAppearance:
        """Persist and apply one accent-source update."""

    def set_custom_accent_color(self, color: str) -> ResolvedAppearance:
        """Persist and apply one custom accent color update."""

    def set_custom_warning_color(self, color: str | None) -> ResolvedAppearance:
        """Persist and apply one custom warning color update."""

    def set_warning_color_mode(
        self,
        mode: AppearanceWarningColorMode,
    ) -> ResolvedAppearance:
        """Persist and apply one warning color mode update."""

    def set_custom_error_color(self, color: str | None) -> ResolvedAppearance:
        """Persist and apply one custom error color update."""

    def set_error_color_mode(
        self,
        mode: AppearanceErrorColorMode,
    ) -> ResolvedAppearance:
        """Persist and apply one error color mode update."""

    def set_backdrop_mode(
        self,
        backdrop_mode: AppearanceBackdropMode,
    ) -> ResolvedAppearance:
        """Persist one backdrop-mode update and resolve the new snapshot."""


__all__ = ["AppearanceRuntimeProtocol"]
