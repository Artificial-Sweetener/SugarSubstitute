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

import json
from pathlib import Path

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
from substitute.infrastructure.persistence import FileAppearancePreferenceRepository


def test_appearance_preference_service_normalizes_invalid_accent_color() -> None:
    """Normalize invalid persisted accent colors back to the default accent."""

    service = AppearancePreferenceService(
        _MemoryAppearancePreferenceRepository(
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


def test_file_appearance_preference_repository_round_trips_normalized_json(
    tmp_path: Path,
) -> None:
    """Save stable schema-1 appearance preference JSON."""

    repository = FileAppearancePreferenceRepository(tmp_path)
    service = AppearancePreferenceService(repository)

    preferences = service.set_theme_mode(AppearanceThemeMode.AUTO)
    preferences = service.set_accent_source(AppearanceAccentSource.SYSTEM)
    preferences = service.set_custom_accent_color("#11aa22")
    preferences = service.set_backdrop_mode(AppearanceBackdropMode.ACRYLIC)
    preferences = service.set_warning_color_mode(AppearanceWarningColorMode.YELLOW)
    preferences = service.set_error_color_mode(AppearanceErrorColorMode.RED)
    preferences = service.set_custom_warning_color("#ffaa00")
    preferences = service.set_custom_error_color("#cc1122")

    assert preferences.theme_mode is AppearanceThemeMode.AUTO
    payload = json.loads((tmp_path / "appearance.json").read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": APPEARANCE_PREFERENCES_SCHEMA_VERSION,
        "theme_mode": "auto",
        "accent_source": "system",
        "custom_accent_color": "#11AA22",
        "backdrop_mode": "acrylic",
        "warning_color_mode": "custom",
        "error_color_mode": "custom",
        "custom_warning_color": "#FFAA00",
        "custom_error_color": "#CC1122",
    }


def test_file_appearance_preference_repository_returns_defaults_for_invalid_json(
    tmp_path: Path,
) -> None:
    """Return defaults when the stored appearance file is unreadable JSON."""

    path = tmp_path / "appearance.json"
    path.write_text("{bad json", encoding="utf-8")

    preferences = FileAppearancePreferenceRepository(tmp_path).load()

    assert preferences.schema_version == APPEARANCE_PREFERENCES_SCHEMA_VERSION
    assert preferences.theme_mode is AppearanceThemeMode.AUTO
    assert preferences.accent_source is AppearanceAccentSource.SYSTEM
    assert preferences.backdrop_mode is AppearanceBackdropMode.MICA_ALT


class _MemoryAppearancePreferenceRepository:
    """Provide an in-memory appearance preference repository for tests."""

    def __init__(self, preferences: AppearancePreferences) -> None:
        """Store the preference snapshot returned by load."""

        self.preferences = preferences

    def load(self) -> AppearancePreferences:
        """Return the stored preference snapshot."""

        return self.preferences

    def save(self, preferences: AppearancePreferences) -> None:
        """Replace the stored preference snapshot."""

        self.preferences = preferences
