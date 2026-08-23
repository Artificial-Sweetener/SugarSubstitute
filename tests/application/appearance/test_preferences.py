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

"""Tests for appearance preference persistence and normalization."""

from __future__ import annotations

from substitute.application.appearance import AppearancePreferenceService
from substitute.domain.appearance import (
    APPEARANCE_PREFERENCES_SCHEMA_VERSION,
    DEFAULT_CUSTOM_ACCENT_COLOR,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
)
from tests.application.appearance.support import (
    MemoryAppearancePreferenceRepository,
)


def test_appearance_preference_service_normalizes_invalid_accent_color() -> None:
    """Normalize invalid persisted accent colors back to the default accent."""

    service = AppearancePreferenceService(
        MemoryAppearancePreferenceRepository(
            AppearancePreferences(
                schema_version="old",
                theme_mode=AppearanceThemeMode.LIGHT,
                accent_source=AppearanceAccentSource.CUSTOM,
                custom_accent_color="hotpink",
                backdrop_mode=AppearanceBackdropMode.ACRYLIC,
                custom_warning_color="banana",
                custom_error_color="#12ABef",
            )
        )
    )

    preferences = service.load_preferences()

    assert preferences.schema_version == APPEARANCE_PREFERENCES_SCHEMA_VERSION
    assert preferences.theme_mode is AppearanceThemeMode.LIGHT
    assert preferences.custom_accent_color == DEFAULT_CUSTOM_ACCENT_COLOR
    assert preferences.warning_color_mode is AppearanceWarningColorMode.DEFAULT
    assert preferences.error_color_mode is AppearanceErrorColorMode.DEFAULT
    assert preferences.custom_warning_color is None
    assert preferences.custom_error_color == "#12ABEF"
