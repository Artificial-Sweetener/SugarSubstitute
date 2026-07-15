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

"""Coordinate prompt editor preference loading and updates."""

from __future__ import annotations

from substitute.application.ports.prompt_editor_preference_repository import (
    PromptEditorPreferenceRepository,
)
from substitute.application.prompt_editor.prompt_feature_registry import (
    default_prompt_feature_preferences,
    prompt_feature_definitions,
)
from substitute.domain.prompt.features import PromptEditorFeature
from substitute.domain.prompt.preferences import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
    PromptWheelAdjustmentMode,
)


class PromptEditorPreferenceService:
    """Own normalized prompt editor preference use cases."""

    def __init__(self, repository: PromptEditorPreferenceRepository) -> None:
        """Store the preference repository."""

        self._repository = repository

    def load_preferences(self) -> PromptEditorPreferences:
        """Load preferences and normalize them against the current registry."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> PromptEditorPreferences:
        """Return registry-backed default prompt editor preferences."""

        return PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features=default_prompt_feature_preferences(),
            wheel_adjustment_mode=PromptWheelAdjustmentMode.HOVER_DWELL,
        )

    def save_preferences(self, preferences: PromptEditorPreferences) -> None:
        """Persist normalized prompt editor preferences."""

        self._repository.save(self._normalize(preferences))

    def set_feature_allowed(
        self,
        feature: PromptEditorFeature,
        allowed: bool,
    ) -> PromptEditorPreferences:
        """Persist one feature preference update and return the new snapshot."""

        preferences = self.load_preferences().with_feature_allowed(feature, allowed)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_wheel_adjustment_mode(
        self,
        mode: PromptWheelAdjustmentMode,
    ) -> PromptEditorPreferences:
        """Persist the prompt editor mouse-wheel adjustment mode."""

        preferences = self.load_preferences().with_wheel_adjustment_mode(mode)
        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def _normalize(
        self,
        preferences: PromptEditorPreferences,
    ) -> PromptEditorPreferences:
        """Return preferences with current features and schema version."""

        defaults = default_prompt_feature_preferences()
        normalized = {
            definition.feature: bool(
                preferences.user_allowed_features.get(
                    definition.feature,
                    defaults[definition.feature],
                )
            )
            for definition in prompt_feature_definitions()
        }
        raw_wheel_adjustment_mode: object = preferences.wheel_adjustment_mode
        wheel_adjustment_mode = (
            raw_wheel_adjustment_mode
            if isinstance(raw_wheel_adjustment_mode, PromptWheelAdjustmentMode)
            else PromptWheelAdjustmentMode.HOVER_DWELL
        )
        return PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features=normalized,
            wheel_adjustment_mode=wheel_adjustment_mode,
        )


__all__ = ["PromptEditorPreferenceService"]
