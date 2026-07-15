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

"""Persist prompt wildcard preprocessing preferences as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.prompt_wildcards.preferences import (
    PROMPT_WILDCARD_PREFERENCES_SCHEMA_VERSION,
    PromptWildcardPreferences,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger(
    "infrastructure.persistence.file_prompt_wildcard_preference_repository"
)
_FILE_NAME = "prompt_wildcards.json"


class FilePromptWildcardPreferenceRepository:
    """Load and save wildcard preferences under the install config directory."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the repository root."""

        self._path = Path(settings_dir) / _FILE_NAME

    def load(self) -> PromptWildcardPreferences:
        """Load wildcard preferences, returning defaults when absent or invalid."""

        if not self._path.exists():
            return PromptWildcardPreferences()
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load wildcard preferences; using defaults.",
                error=repr(error),
            )
            return PromptWildcardPreferences()
        if not isinstance(payload, dict):
            return PromptWildcardPreferences()
        try:
            return PromptWildcardPreferences(
                resolve_on_generation=bool(payload.get("resolve_on_generation", True)),
            )
        except (TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Invalid wildcard preferences; using defaults.",
                error=repr(error),
            )
            return PromptWildcardPreferences()

    def save(self, preferences: PromptWildcardPreferences) -> None:
        """Persist wildcard preferences as stable JSON."""

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PROMPT_WILDCARD_PREFERENCES_SCHEMA_VERSION,
            "resolve_on_generation": preferences.resolve_on_generation,
        }
        self._path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


__all__ = ["FilePromptWildcardPreferenceRepository"]
