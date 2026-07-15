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

"""Persist generation preview preferences as JSON under the config root."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.generation_preview_preference_repository import (
    GenerationPreviewPreferenceRepository,
)
from substitute.domain.generation import (
    GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
    GenerationPreviewMethod,
    GenerationPreviewPreferences,
    default_generation_preview_preferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.generation_preview_preferences")
_PREFERENCES_FILE_NAME = "generation_preview.json"


class FileGenerationPreviewPreferenceRepository(GenerationPreviewPreferenceRepository):
    """Load and save generation preview preferences from the install config root."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation config directory."""

        self._settings_dir = settings_dir

    def load(self) -> GenerationPreviewPreferences:
        """Load generation preview preferences or return defaults."""

        path = self._path()
        if not path.exists():
            return default_generation_preview_preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load generation preview preferences; using defaults.",
                path=path,
                error=repr(error),
            )
            return default_generation_preview_preferences()
        if not isinstance(payload, dict):
            return default_generation_preview_preferences()
        method = _preview_method(payload.get("method"))
        if method is None:
            log_warning(
                _LOGGER,
                "Generation preview preferences contained an unknown method.",
                path=path,
                method=payload.get("method"),
            )
            method = GenerationPreviewMethod.LATENT2RGB
        enabled_value = payload.get("enabled")
        enabled = enabled_value if isinstance(enabled_value, bool) else True
        return GenerationPreviewPreferences(
            schema_version=str(
                payload.get(
                    "schema_version",
                    GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
                )
            ),
            enabled=enabled,
            method=method,
        )

    def save(self, preferences: GenerationPreviewPreferences) -> None:
        """Persist generation preview preferences with stable JSON formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
            "enabled": preferences.enabled,
            "method": preferences.method.value,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _path(self) -> Path:
        """Return the generation preview preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


def _preview_method(value: object) -> GenerationPreviewMethod | None:
    """Parse one persisted preview method value."""

    if not isinstance(value, str):
        return None
    try:
        return GenerationPreviewMethod(value)
    except ValueError:
        return None


__all__ = ["FileGenerationPreviewPreferenceRepository"]
