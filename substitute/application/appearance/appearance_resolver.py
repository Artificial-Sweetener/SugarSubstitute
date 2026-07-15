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

"""Resolve persisted appearance preferences from normalized system state."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.appearance.window_material_capabilities import (
    WindowMaterialCapabilities,
)
from substitute.domain.appearance import (
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearancePreferences,
    AppearanceThemeMode,
    SystemAppearanceSnapshot,
    SystemColorScheme,
)


@dataclass(frozen=True, slots=True)
class AppearanceCapabilities:
    """Describe appearance features available to settings and shell composition."""

    system_accent_available: bool
    acrylic_available: bool
    mica_alt_available: bool

    @property
    def backdrop_available(self) -> bool:
        """Return whether any native window material is supported."""

        return self.acrylic_available or self.mica_alt_available


@dataclass(frozen=True, slots=True)
class ResolvedAppearance:
    """Describe explicit runtime values after system and capability resolution."""

    requested: AppearancePreferences
    capabilities: AppearanceCapabilities
    effective_theme_mode: AppearanceThemeMode
    effective_accent_source: AppearanceAccentSource
    effective_accent_color: str
    effective_backdrop_mode: AppearanceBackdropMode | None


class AppearanceResolver:
    """Own pure appearance fallback and native-material gating policy."""

    def __init__(
        self,
        material_capabilities: WindowMaterialCapabilities | None = None,
    ) -> None:
        """Store independently detected native window-material capabilities."""

        self._material_capabilities = (
            material_capabilities
            if material_capabilities is not None
            else WindowMaterialCapabilities()
        )

    def capabilities(
        self,
        system_appearance: SystemAppearanceSnapshot | None = None,
    ) -> AppearanceCapabilities:
        """Return capabilities for one normalized system appearance snapshot."""

        snapshot = system_appearance or SystemAppearanceSnapshot()
        return AppearanceCapabilities(
            system_accent_available=snapshot.accent_color is not None,
            acrylic_available=self._material_capabilities.acrylic_available,
            mica_alt_available=self._material_capabilities.mica_alt_available,
        )

    def resolve(
        self,
        preferences: AppearancePreferences,
        *,
        system_appearance: SystemAppearanceSnapshot,
    ) -> ResolvedAppearance:
        """Resolve one runtime appearance with stable explicit fallbacks."""

        capabilities = self.capabilities(system_appearance)
        effective_theme_mode = _resolve_theme_mode(preferences, system_appearance)
        effective_accent_source, effective_accent_color = _resolve_accent(
            preferences,
            system_appearance,
        )
        effective_backdrop_mode = _resolve_backdrop(
            preferences.backdrop_mode,
            self._material_capabilities,
        )
        return ResolvedAppearance(
            requested=preferences,
            capabilities=capabilities,
            effective_theme_mode=effective_theme_mode,
            effective_accent_source=effective_accent_source,
            effective_accent_color=effective_accent_color,
            effective_backdrop_mode=effective_backdrop_mode,
        )


def _resolve_theme_mode(
    preferences: AppearancePreferences,
    system_appearance: SystemAppearanceSnapshot,
) -> AppearanceThemeMode:
    """Resolve Auto to an explicit QFluent theme with a stable dark fallback."""

    if preferences.theme_mode is not AppearanceThemeMode.AUTO:
        return preferences.theme_mode
    if system_appearance.color_scheme is SystemColorScheme.LIGHT:
        return AppearanceThemeMode.LIGHT
    return AppearanceThemeMode.DARK


def _resolve_accent(
    preferences: AppearancePreferences,
    system_appearance: SystemAppearanceSnapshot,
) -> tuple[AppearanceAccentSource, str]:
    """Resolve System accent to detected sRGB or Substitute pink."""

    if preferences.accent_source is AppearanceAccentSource.CUSTOM:
        return AppearanceAccentSource.CUSTOM, preferences.custom_accent_color
    if system_appearance.accent_color is not None:
        return AppearanceAccentSource.SYSTEM, system_appearance.accent_color.to_hex()
    return AppearanceAccentSource.CUSTOM, DEFAULT_CUSTOM_ACCENT_COLOR


def _resolve_backdrop(
    requested: AppearanceBackdropMode,
    capabilities: WindowMaterialCapabilities,
) -> AppearanceBackdropMode | None:
    """Resolve native Windows materials without coupling them to color detection."""

    if requested is AppearanceBackdropMode.MICA_ALT:
        if capabilities.mica_alt_available:
            return requested
        if capabilities.acrylic_available:
            return AppearanceBackdropMode.ACRYLIC
        return None
    if capabilities.acrylic_available:
        return requested
    return None


__all__ = ["AppearanceCapabilities", "AppearanceResolver", "ResolvedAppearance"]
