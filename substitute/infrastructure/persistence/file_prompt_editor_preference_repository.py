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

"""Persist prompt editor preferences as JSON under the installation config root."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.ports.prompt_editor_preference_repository import (
    PromptEditorPreferenceRepository,
)
from substitute.application.prompt_editor.prompt_feature_registry import (
    default_prompt_feature_preferences,
)
from substitute.domain.prompt.features import PromptEditorFeature
from substitute.domain.prompt.preferences import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
    PromptWheelAdjustmentMode,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.prompt_editor_preferences")
_PREFERENCES_FILE_NAME = "prompt_editor.json"


class FilePromptEditorPreferenceRepository(PromptEditorPreferenceRepository):
    """Load and save prompt editor preferences from `config/prompt_editor.json`."""

    def __init__(self, settings_dir: Path) -> None:
        """Store the active installation config directory."""

        self._settings_dir = settings_dir

    def load(self) -> PromptEditorPreferences:
        """Load prompt editor preferences or return defaults when absent/invalid."""

        path = self._path()
        if not path.exists():
            return _default_preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to load prompt editor preferences; using defaults.",
                path=path,
                error=repr(error),
            )
            return _default_preferences()
        if not isinstance(payload, dict):
            return _default_preferences()
        raw_features = payload.get("features", {})
        if not isinstance(raw_features, dict):
            raw_features = {}
        features: dict[PromptEditorFeature, bool] = {}
        for feature in PromptEditorFeature:
            raw_value = raw_features.get(feature.value)
            if isinstance(raw_value, bool):
                features[feature] = raw_value
        wheel_adjustment_mode = _wheel_adjustment_mode_from_payload(
            payload.get("wheel_adjustment_mode")
        )
        return PromptEditorPreferences(
            schema_version=str(
                payload.get("schema_version", PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION)
            ),
            user_allowed_features=features,
            wheel_adjustment_mode=wheel_adjustment_mode,
        )

    def save(self, preferences: PromptEditorPreferences) -> None:
        """Persist prompt editor preferences with stable JSON formatting."""

        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            "wheel_adjustment_mode": preferences.wheel_adjustment_mode.value,
            "features": {
                feature.value: bool(preferences.user_allowed_features.get(feature))
                for feature in PromptEditorFeature
            },
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _path(self) -> Path:
        """Return the prompt editor preference file path."""

        return self._settings_dir / _PREFERENCES_FILE_NAME


def _default_preferences() -> PromptEditorPreferences:
    """Return file-repository fallback preferences."""

    return PromptEditorPreferences(
        schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
        user_allowed_features=default_prompt_feature_preferences(),
        wheel_adjustment_mode=PromptWheelAdjustmentMode.HOVER_DWELL,
    )


def _wheel_adjustment_mode_from_payload(value: object) -> PromptWheelAdjustmentMode:
    """Return a safe wheel adjustment mode from a persisted JSON value."""

    if isinstance(value, str):
        try:
            return PromptWheelAdjustmentMode(value)
        except ValueError:
            return PromptWheelAdjustmentMode.HOVER_DWELL
    return PromptWheelAdjustmentMode.HOVER_DWELL


__all__ = ["FilePromptEditorPreferenceRepository"]
