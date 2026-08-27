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

"""Test persistent appearance preference serialization and recovery."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.appearance import AppearancePreferenceService
from substitute.domain.appearance import (
    APPEARANCE_PREFERENCES_SCHEMA_VERSION,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
)
from substitute.infrastructure.persistence import FileAppearancePreferenceRepository


def test_repository_round_trips_normalized_json(tmp_path: Path) -> None:
    """Save stable normalized appearance preference JSON."""

    service = AppearancePreferenceService(FileAppearancePreferenceRepository(tmp_path))

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


def test_repository_returns_defaults_for_invalid_json(tmp_path: Path) -> None:
    """Return defaults when the stored appearance file is unreadable JSON."""

    path = tmp_path / "appearance.json"
    path.write_text("{bad json", encoding="utf-8")

    preferences = FileAppearancePreferenceRepository(tmp_path).load()

    assert preferences.schema_version == APPEARANCE_PREFERENCES_SCHEMA_VERSION
    assert preferences.theme_mode is AppearanceThemeMode.AUTO
    assert preferences.accent_source is AppearanceAccentSource.SYSTEM
    assert preferences.backdrop_mode is AppearanceBackdropMode.MICA_ALT
