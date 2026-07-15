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

"""Persist appearance preferences as JSON under the installation config root."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.appearance_preference_repository import (
    AppearancePreferenceRepository,
)
from substitute.domain.appearance import (
    APPEARANCE_PREFERENCES_SCHEMA_VERSION,
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearancePreferences,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
    default_appearance_preferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.appearance_preferences")
_PREFERENCES_FILE_NAME = "appearance.json"


class FileAppearancePreferenceRepository(AppearancePreferenceRepository):
    """Load and save appearance preferences from `config/appearance.json`."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation config directory."""

        self._settings_dir = settings_dir

    def load(self) -> AppearancePreferences:
        """Load appearance preferences or return defaults when absent or invalid."""

        path = self._path()
        if not path.exists():
            return default_appearance_preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load appearance preferences; using defaults.",
                path=path,
                error=repr(error),
            )
            return default_appearance_preferences()
        if not isinstance(payload, dict):
            return default_appearance_preferences()
        return AppearancePreferences(
            schema_version=str(
                payload.get(
                    "schema_version",
                    APPEARANCE_PREFERENCES_SCHEMA_VERSION,
                )
            ),
            theme_mode=_enum_from_value(
                AppearanceThemeMode,
                payload.get("theme_mode"),
                default_appearance_preferences().theme_mode,
            ),
            accent_source=_enum_from_value(
                AppearanceAccentSource,
                payload.get("accent_source"),
                default_appearance_preferences().accent_source,
            ),
            custom_accent_color=str(
                payload.get(
                    "custom_accent_color",
                    default_appearance_preferences().custom_accent_color,
                )
            ),
            backdrop_mode=_enum_from_value(
                AppearanceBackdropMode,
                payload.get("backdrop_mode"),
                default_appearance_preferences().backdrop_mode,
            ),
            warning_color_mode=_enum_from_value(
                AppearanceWarningColorMode,
                payload.get("warning_color_mode"),
                default_appearance_preferences().warning_color_mode,
            ),
            error_color_mode=_enum_from_value(
                AppearanceErrorColorMode,
                payload.get("error_color_mode"),
                default_appearance_preferences().error_color_mode,
            ),
            custom_warning_color=_optional_string(payload.get("custom_warning_color")),
            custom_error_color=_optional_string(payload.get("custom_error_color")),
        )

    def save(self, preferences: AppearancePreferences) -> None:
        """Persist appearance preferences with stable JSON formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": APPEARANCE_PREFERENCES_SCHEMA_VERSION,
            "theme_mode": preferences.theme_mode.value,
            "accent_source": preferences.accent_source.value,
            "custom_accent_color": preferences.custom_accent_color,
            "backdrop_mode": preferences.backdrop_mode.value,
            "warning_color_mode": preferences.warning_color_mode.value,
            "error_color_mode": preferences.error_color_mode.value,
            "custom_warning_color": preferences.custom_warning_color,
            "custom_error_color": preferences.custom_error_color,
        }
        path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")

    def _path(self) -> Path:
        """Return the appearance preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


def _enum_from_value[TEnum](
    enum_type: type[TEnum],
    raw_value: object,
    fallback: TEnum,
) -> TEnum:
    """Return one enum member from persisted storage or a fallback value."""

    if isinstance(raw_value, str):
        try:
            return enum_type(raw_value)  # type: ignore[call-arg]
        except ValueError:
            return fallback
    return fallback


def _optional_string(raw_value: object) -> str | None:
    """Return a persisted optional string value without coercing null."""

    if raw_value is None:
        return None
    return str(raw_value)


__all__ = ["FileAppearancePreferenceRepository"]
