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

"""Describe prompt-editor feature-family composition results."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)

from ..async_work import PromptScheduledLoraContextProvider
from ..features import (
    PromptDanbooruActionController,
    PromptFeatureProfileController,
    PromptSceneContextPublication,
    PromptScenePositionContextPreparation,
    PromptSearchFeatureController,
    PromptSegmentPresetController,
    PromptWildcardAutocompletePresentation,
    PromptWildcardDiagnosticsPresentation,
)
from ..interactions import (
    PromptAutocompleteTimingController,
    PromptInteractionController,
    PromptWeightInteraction,
    PromptWheelController,
)
from ..overlays import PromptTokenWeightControls
from ..syntax_renderers import PromptSyntaxRendererCoordinator
from ..syntax_renderers import PromptSyntaxStateController


@dataclass(frozen=True, slots=True)
class PromptEditorServiceCollaborators:
    """Carry construction results for prompt-editor service state."""

    lora_schedule_service: PromptLoraScheduleService
    prompt_scheduled_lora_service: PromptScheduledLoraService
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    scheduled_lora_context_provider: PromptScheduledLoraContextProvider
    feature_profile_controller: PromptFeatureProfileController
    scene_context_publication: PromptSceneContextPublication
    scene_position_preparation: PromptScenePositionContextPreparation
    search_feature_controller: PromptSearchFeatureController
    wildcard_autocomplete_presentation: PromptWildcardAutocompletePresentation
    wildcard_diagnostics_presentation: PromptWildcardDiagnosticsPresentation
    segment_preset_controller: PromptSegmentPresetController
    danbooru_action_controller: PromptDanbooruActionController


@dataclass(frozen=True, slots=True)
class PromptEditorSyntaxCollaborators:
    """Carry construction results for syntax and interaction collaborators."""

    autocomplete_timing_controller: PromptAutocompleteTimingController
    document_service: PromptDocumentService
    mutation_service: PromptMutationService
    syntax_profile: PromptSyntaxProfile
    syntax_service: PromptSyntaxService
    token_weight_controls: PromptTokenWeightControls
    weight_interaction: PromptWeightInteraction
    wheel_controller: PromptWheelController
    syntax_renderer_coordinator: PromptSyntaxRendererCoordinator
    syntax_state: PromptSyntaxStateController
    interaction_controller: PromptInteractionController
