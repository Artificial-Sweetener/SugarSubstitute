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

"""Persist output organization preferences as JSON under the config root."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.output_organization_preference_repository import (
    OutputOrganizationPreferenceRepository,
)
from substitute.domain.generation import (
    OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION,
    OutputOrganizationPreferences,
    default_output_organization_preferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.output_organization_preferences")
_PREFERENCES_FILE_NAME = "output_organization.json"


class FileOutputOrganizationPreferenceRepository(
    OutputOrganizationPreferenceRepository
):
    """Load and save output organization preferences from the install config root."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation config directory."""

        self._settings_dir = settings_dir

    def load(self) -> OutputOrganizationPreferences:
        """Load output organization preferences or return defaults."""

        path = self._path()
        defaults = default_output_organization_preferences()
        if not path.exists():
            return defaults
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load output organization preferences; using defaults.",
                path=path,
                error=repr(error),
            )
            return defaults
        if not isinstance(payload, dict):
            return defaults
        output_root = _optional_path(payload.get("output_root"))
        path_pattern = _string_or_default(
            payload.get("path_pattern"),
            defaults.path_pattern,
        )
        return OutputOrganizationPreferences(
            schema_version=str(
                payload.get(
                    "schema_version",
                    OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION,
                )
            ),
            output_root=output_root,
            path_pattern=path_pattern,
        )

    def save(self, preferences: OutputOrganizationPreferences) -> None:
        """Persist output organization preferences with stable JSON formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION,
            "output_root": (
                str(preferences.output_root)
                if preferences.output_root is not None
                else None
            ),
            "path_pattern": preferences.path_pattern,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _path(self) -> Path:
        """Return the output organization preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


def _optional_path(value: object) -> Path | None:
    """Parse an optional persisted path value."""

    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def _string_or_default(value: object, default: str) -> str:
    """Return value when it is a non-empty string, otherwise default."""

    if isinstance(value, str) and value.strip():
        return value
    return default


__all__ = ["FileOutputOrganizationPreferenceRepository"]
