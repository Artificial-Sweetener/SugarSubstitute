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

"""Test prompt-editor feature preference application behavior."""

from __future__ import annotations

from substitute.application.prompt_editor.features.definitions import (
    default_prompt_feature_preferences,
    prompt_feature_definitions,
)
from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.domain.prompt.features.models import PromptEditorFeature
from substitute.domain.prompt.preferences.models import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
    PromptWheelAdjustmentMode,
)


def test_prompt_feature_registry_defaults_cover_every_feature() -> None:
    """Include each supported feature in the default preference registry."""

    defaults = default_prompt_feature_preferences()

    assert set(defaults) == {
        definition.feature for definition in prompt_feature_definitions()
    }
    assert set(defaults) == set(PromptEditorFeature)


def test_prompt_editor_preference_service_normalizes_missing_features() -> None:
    """Fill missing persisted feature ids from the application defaults."""

    service = PromptEditorPreferenceService(
        _MemoryPreferenceRepository(
            PromptEditorPreferences(
                schema_version="old",
                user_allowed_features={PromptEditorFeature.EMPHASIS: False},
            )
        )
    )

    preferences = service.load_preferences()

    assert preferences.schema_version == PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION
    assert preferences.user_allows(PromptEditorFeature.EMPHASIS) is False
    assert preferences.user_allows(PromptEditorFeature.WILDCARD_SYNTAX) is True
    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.HOVER_DWELL


def test_prompt_editor_preference_service_defaults_to_hover_dwell_wheel_adjustment() -> (
    None
):
    """Preserve hover-dwell wheel edits in default preferences."""

    service = PromptEditorPreferenceService(
        _MemoryPreferenceRepository(
            PromptEditorPreferences(
                schema_version="old",
                user_allowed_features={},
            )
        )
    )

    preferences = service.default_preferences()

    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.HOVER_DWELL


def test_prompt_editor_preference_service_sets_wheel_adjustment_mode() -> None:
    """Persist the selected mouse-wheel adjustment mode through the port."""

    repository = _MemoryPreferenceRepository(
        PromptEditorPreferences(
            schema_version="old",
            user_allowed_features={},
        )
    )
    service = PromptEditorPreferenceService(repository)

    preferences = service.set_wheel_adjustment_mode(
        PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )

    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    assert (
        repository.preferences.wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )


def test_prompt_editor_preference_service_can_disable_ghost_text() -> None:
    """Persist the autocomplete ghost-text feature flag through the port."""

    repository = _MemoryPreferenceRepository(
        PromptEditorPreferences(
            schema_version="old",
            user_allowed_features={},
        )
    )
    service = PromptEditorPreferenceService(repository)

    preferences = service.set_feature_allowed(
        PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT,
        False,
    )

    assert preferences.user_allows(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT) is False
    assert (
        repository.preferences.user_allows(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT)
        is False
    )


class _MemoryPreferenceRepository:
    """Store preference snapshots at the application port boundary."""

    def __init__(self, preferences: PromptEditorPreferences) -> None:
        """Store the preference snapshot returned by load."""

        self.preferences = preferences

    def load(self) -> PromptEditorPreferences:
        """Return the stored preference snapshot."""

        return self.preferences

    def save(self, preferences: PromptEditorPreferences) -> None:
        """Replace the stored preference snapshot."""

        self.preferences = preferences
