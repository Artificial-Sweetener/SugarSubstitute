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

"""Persist user control bindings as JSON under the installation config root."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.control_binding_preference_repository import (
    ControlBindingPreferenceRepository,
)
from substitute.domain.controls import (
    CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION,
    ControlBindingPreferences,
    default_control_binding_preferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.control_bindings")
_PREFERENCES_FILE_NAME = "controls.json"


class FileControlBindingPreferenceRepository(ControlBindingPreferenceRepository):
    """Load and save user control bindings from ``config/controls.json``."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the installation's settings directory."""

        self._settings_dir = settings_dir

    def load(self) -> ControlBindingPreferences:
        """Load saved bindings or return safe empty defaults."""

        path = self._path()
        if not path.exists():
            return default_control_binding_preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load control bindings; using defaults.",
                path=path,
                error=repr(error),
            )
            return default_control_binding_preferences()
        if not isinstance(payload, dict):
            return default_control_binding_preferences()
        raw_bindings = payload.get("bindings", {})
        bindings = (
            {
                command_id: binding if isinstance(binding, str) else None
                for command_id, binding in raw_bindings.items()
                if isinstance(command_id, str)
            }
            if isinstance(raw_bindings, dict)
            else {}
        )
        return ControlBindingPreferences(
            schema_version=str(
                payload.get(
                    "schema_version", CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION
                )
            ),
            bindings=bindings,
        )

    def save(self, preferences: ControlBindingPreferences) -> None:
        """Persist one normalized binding snapshot with stable formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION,
                    "bindings": dict(preferences.bindings),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _path(self) -> Path:
        """Return the stable controls-preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


__all__ = ["FileControlBindingPreferenceRepository"]
