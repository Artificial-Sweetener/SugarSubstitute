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

"""Tests for appearance runtime capability gating and fallback resolution."""

from __future__ import annotations

from substitute.application.appearance import (
    AppearanceResolver,
    WindowMaterialCapabilities,
)
from substitute.domain.appearance import (
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceThemeMode,
    RgbColor,
    SystemAppearanceSnapshot,
    SystemColorScheme,
)
from tests.application.appearance.support import appearance_preferences


def test_resolver_uses_detected_colors_without_enabling_native_materials() -> None:
    """Resolve portable system colors independently of Windows-only materials."""

    resolver = AppearanceResolver(WindowMaterialCapabilities())
    resolved = resolver.resolve(
        appearance_preferences(
            theme_mode=AppearanceThemeMode.AUTO,
            accent_source=AppearanceAccentSource.SYSTEM,
            custom_accent_color="#224466",
        ),
        system_appearance=SystemAppearanceSnapshot(
            color_scheme=SystemColorScheme.LIGHT,
            accent_color=RgbColor(153, 136, 119),
        ),
    )

    assert resolved.capabilities.system_accent_available is True
    assert resolved.capabilities.backdrop_available is False
    assert resolved.effective_theme_mode is AppearanceThemeMode.LIGHT
    assert resolved.effective_accent_source is AppearanceAccentSource.SYSTEM
    assert resolved.effective_accent_color == "#998877"
    assert resolved.effective_backdrop_mode is None


def test_resolver_uses_stable_fallbacks_when_system_colors_are_unavailable() -> None:
    """Resolve Auto to dark and System accent to Substitute pink when unknown."""

    resolved = AppearanceResolver().resolve(
        appearance_preferences(
            theme_mode=AppearanceThemeMode.AUTO,
            accent_source=AppearanceAccentSource.SYSTEM,
            custom_accent_color="#224466",
        ),
        system_appearance=SystemAppearanceSnapshot(),
    )

    assert resolved.capabilities.system_accent_available is False
    assert resolved.effective_theme_mode is AppearanceThemeMode.DARK
    assert resolved.effective_accent_source is AppearanceAccentSource.CUSTOM
    assert resolved.effective_accent_color == DEFAULT_CUSTOM_ACCENT_COLOR


def test_resolver_falls_back_from_mica_alt_to_acrylic_on_windows_10() -> None:
    """Resolve requested Mica Alt to Acrylic when only Acrylic is supported."""

    resolver = AppearanceResolver(
        WindowMaterialCapabilities(acrylic_available=True, mica_alt_available=False)
    )
    resolved = resolver.resolve(
        appearance_preferences(custom_accent_color="#224466"),
        system_appearance=SystemAppearanceSnapshot(
            color_scheme=SystemColorScheme.DARK,
        ),
    )

    assert resolved.capabilities.acrylic_available is True
    assert resolved.capabilities.mica_alt_available is False
    assert resolved.effective_backdrop_mode is AppearanceBackdropMode.ACRYLIC


def test_resolver_keeps_requested_backdrop_on_windows_11() -> None:
    """Retain requested Mica Alt when its native capability is available."""

    resolver = AppearanceResolver(
        WindowMaterialCapabilities(acrylic_available=True, mica_alt_available=True)
    )
    resolved = resolver.resolve(
        appearance_preferences(
            theme_mode=AppearanceThemeMode.DARK,
            custom_accent_color="#224466",
        ),
        system_appearance=SystemAppearanceSnapshot(),
    )

    assert resolved.effective_theme_mode is AppearanceThemeMode.DARK
    assert resolved.effective_backdrop_mode is AppearanceBackdropMode.MICA_ALT
