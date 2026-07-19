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

"""Persist the generated-output preference aggregate as JSON."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from substitute.application.ports.output_preference_repository import (
    OutputPreferenceRepository,
)
from substitute.domain.generation.output_preferences import (
    default_output_preferences,
    JpegOutputSettings,
    JpegSizingMode,
    OUTPUT_PREFERENCES_SCHEMA_VERSION,
    OutputOrganizationSettings,
    OutputPersistenceMode,
    OutputPreferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.output_preferences")
_PREFERENCES_FILE_NAME = "output_organization.json"
_EnumValue = TypeVar("_EnumValue", bound=StrEnum)


class FileOutputPreferenceRepository(OutputPreferenceRepository):
    """Load current preferences and migrate organization-only persisted data."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation settings directory."""

        self._path = Path(settings_dir) / _PREFERENCES_FILE_NAME

    def load(self) -> OutputPreferences:
        """Load output preferences or defaults after invalid data."""

        defaults = default_output_preferences()
        if not self._path.exists():
            return defaults
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load output preferences; using defaults",
                error=repr(error),
            )
            return defaults
        if not isinstance(payload, dict):
            return defaults
        organization_payload = payload.get("organization")
        organization = (
            organization_payload if isinstance(organization_payload, dict) else payload
        )
        jpeg_payload = payload.get("jpeg")
        jpeg = jpeg_payload if isinstance(jpeg_payload, dict) else {}
        return OutputPreferences(
            schema_version=str(
                payload.get("schema_version", OUTPUT_PREFERENCES_SCHEMA_VERSION)
            ),
            organization=OutputOrganizationSettings(
                output_root=_optional_path(organization.get("output_root")),
                path_pattern=_string_or_default(
                    organization.get("path_pattern"),
                    defaults.organization.path_pattern,
                ),
            ),
            jpeg=JpegOutputSettings(
                enabled=jpeg.get("enabled") is True,
                sizing_mode=_enum_or_default(
                    JpegSizingMode,
                    jpeg.get("sizing_mode"),
                    defaults.jpeg.sizing_mode,
                ),
                quality=_int_or_default(jpeg.get("quality"), defaults.jpeg.quality),
                target_size_kib=_int_or_default(
                    jpeg.get("target_size_kib"), defaults.jpeg.target_size_kib
                ),
            ),
            persistence_mode=_enum_or_default(
                OutputPersistenceMode,
                payload.get("persistence_mode"),
                defaults.persistence_mode,
            ),
        )

    def save(self, preferences: OutputPreferences) -> None:
        """Persist stable, human-readable output preference JSON."""

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": OUTPUT_PREFERENCES_SCHEMA_VERSION,
            "organization": {
                "output_root": (
                    str(preferences.organization.output_root)
                    if preferences.organization.output_root is not None
                    else None
                ),
                "path_pattern": preferences.organization.path_pattern,
            },
            "jpeg": {
                "enabled": preferences.jpeg.enabled,
                "sizing_mode": preferences.jpeg.sizing_mode.value,
                "quality": preferences.jpeg.quality,
                "target_size_kib": preferences.jpeg.target_size_kib,
            },
            "persistence_mode": preferences.persistence_mode.value,
        }
        self._path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def _optional_path(value: object) -> Path | None:
    """Parse an optional persisted path."""

    return Path(value) if isinstance(value, str) and value.strip() else None


def _string_or_default(value: object, default: str) -> str:
    """Return non-empty string value or default."""

    return value if isinstance(value, str) and value.strip() else default


def _int_or_default(value: object, default: int) -> int:
    """Return a concrete integer value or default."""

    return value if type(value) is int else default


def _enum_or_default(
    enum_type: type[_EnumValue], value: object, default: _EnumValue
) -> _EnumValue:
    """Parse one string enum value or return default."""

    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            pass
    return default


__all__ = ["FileOutputPreferenceRepository"]
