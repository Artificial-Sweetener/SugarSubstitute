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

"""Build prompt feature profile service scenarios."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.application.prompt_editor.features.profile import (
    PromptFeatureProfileService,
)
from substitute.application.prompt_editor.lora.effective_provider import (
    WorkflowPromptContext,
)
from substitute.domain.prompt.features.models import PromptEditorFeature
from substitute.domain.prompt.preferences.models import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
)


def profile_service(
    *,
    preferences: PromptEditorPreferences | None = None,
) -> PromptFeatureProfileService:
    """Return a profile service wired to test doubles."""

    return PromptFeatureProfileService(
        preference_service=PromptEditorPreferenceService(
            MemoryPreferenceRepository(preferences)
        ),
    )


def workflow_context(
    nodes: dict[str, dict[str, Any]],
    *,
    original_cube: dict[str, Any] | None = None,
    subgraphs: tuple[dict[str, Any], ...] = (),
) -> WorkflowPromptContext:
    """Return a workflow context containing one cube graph."""

    return WorkflowPromptContext(
        cube_states={
            "Cube": SimpleNamespace(
                original_cube=original_cube or {},
                buffer={
                    "nodes": nodes,
                    "subgraphs": subgraphs,
                },
            )
        },
        stack_order=("Cube",),
        workflow_overrides={},
        behavior_snapshot=None,
    )


class MemoryPreferenceRepository:
    """In-memory repository for feature profile tests."""

    def __init__(self, preferences: PromptEditorPreferences | None) -> None:
        """Store an optional test preference snapshot."""

        self._preferences = preferences or PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features={feature: True for feature in PromptEditorFeature},
        )

    def load(self) -> PromptEditorPreferences:
        """Return the stored preference snapshot."""

        return self._preferences

    def save(self, preferences: PromptEditorPreferences) -> None:
        """Replace the stored preference snapshot."""

        self._preferences = preferences
