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

"""Own prompt feature-service composition above projection commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)

from ..async_work import build_prompt_scheduled_lora_context_coordinator
from ..commands.context_insertion import PromptContextInsertionService
from ..features import (
    PromptDanbooruActionController,
    PromptFeatureProfileController,
    PromptSceneContextPublication,
    PromptScenePositionContextPreparation,
    PromptSearchFeatureController,
    PromptSegmentPresetController,
    PromptWildcardAutocompletePresentation,
    PromptWildcardDiagnosticsPresentation,
    prompt_feature_profile_from_legacy_syntax,
)
from ..features.prompt_segment_selection import PromptSegmentCursor
from ..interactions import (
    PromptExternalUrlActionRunner,
    PromptSegmentPresetHostAdapter,
)
from ..projection.undo_payload import PromptProjectionUndoPayload
from .collaborator_bundle import PromptEditorConstructionInputs
from .context import PromptEditorCompositionContext
from .danbooru_factory import PromptEditorDanbooruFactory
from .execution_factory import PromptEditorExecutionFactory
from .feature_collaborators import PromptEditorServiceCollaborators
from .projection_factory import PromptEditorProjectionCollaborators


class PromptEditorServiceFactory:
    """Build feature-service state from shared construction authorities."""

    def __init__(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        execution: PromptEditorExecutionFactory,
        danbooru: PromptEditorDanbooruFactory,
    ) -> None:
        """Retain the construction boundaries shared by feature services."""
        self._inputs = inputs
        self._context = context
        self._execution = execution
        self._danbooru = danbooru

    def build(
        self,
        projection: PromptEditorProjectionCollaborators,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        *,
        cursor_provider: Callable[[], PromptSegmentCursor],
        cursor_setter: Callable[[object], None],
        external_url_actions: PromptExternalUrlActionRunner,
        source_text_provider: Callable[[], str],
    ) -> PromptEditorServiceCollaborators:
        """Build normalized service collaborators and feature profile state."""
        inputs = self._inputs
        lora_schedule_service = PromptLoraScheduleService()
        scheduled_lora_service = (
            inputs.prompt_scheduled_lora_service or PromptScheduledLoraService()
        )
        fallback_projector = PromptDocumentProjector()

        def inline_scheduled_lora_fallback(
            prompt_text: str,
        ) -> tuple[PromptScheduledLora, ...]:
            """Return inline scheduled LoRAs for autocomplete fallback resolution."""
            if inputs.prompt_lora_catalog_service is None:
                return ()
            return scheduled_lora_service.inline_scheduled_loras(
                prompt_text=prompt_text,
                document_projector=fallback_projector,
                lora_catalog=inputs.prompt_lora_catalog_service,
            )

        scheduled_lora_resolver = (
            inputs.scheduled_lora_resolver or inline_scheduled_lora_fallback
        )
        feature_profile = (
            inputs.prompt_feature_profile
            if inputs.prompt_feature_profile is not None
            else prompt_feature_profile_from_legacy_syntax(inputs.prompt_syntax_profile)
        )
        feature_profile_controller = PromptFeatureProfileController(feature_profile)
        scheduled_lora_context = build_prompt_scheduled_lora_context_coordinator(
            resolver=scheduled_lora_resolver,
            enabled=feature_profile_controller.lora_trigger_words_enabled,
            parent=self._context.editor,
            executor=self._execution.build_task_executor(
                owner_label="prompt-scheduled-lora"
            ),
        )
        scene_semantics = (
            inputs.prompt_document_semantics or OrdinaryPromptDocumentSemantics()
        )
        scene_context = PromptSceneContextPublication(
            source_identity=projection.source_commands.source_identity,
            feature_profile=feature_profile_controller,
            document_semantics=scene_semantics,
        )
        scene_preparation = PromptScenePositionContextPreparation(
            source_text=source_text_provider,
            source_identity=projection.source_commands.source_identity,
            publication=scene_context,
            document_semantics=scene_semantics,
        )
        search = PromptSearchFeatureController(
            source_identity=projection.source_commands.source_identity,
            surface=projection.surface,
            feature_profile=feature_profile_controller,
        )
        wildcard_autocomplete = PromptWildcardAutocompletePresentation(
            feature_profile=feature_profile_controller,
            wildcard_catalog_gateway=inputs.prompt_wildcard_catalog_gateway,
            source_identity_provider=projection.source_commands.source_identity,
            request_channel=cast(
                Any,
                self._execution.build_request_channel(
                    owner_label="prompt-wildcard-autocomplete"
                ),
            ),
        )
        wildcard_diagnostics = PromptWildcardDiagnosticsPresentation(
            feature_profile=feature_profile_controller,
            wildcard_catalog_gateway=inputs.prompt_wildcard_catalog_gateway,
        )
        segment_presets = PromptSegmentPresetController(
            host=PromptSegmentPresetHostAdapter(
                host_widget=self._context.editor,
                cursor_provider=cursor_provider,
                cursor_setter=cursor_setter,
                source_text_provider=source_text_provider,
                source_identity_provider=projection.source_commands.source_identity,
            ),
            text_insertion_executor=context_insertion,
            feature_profile=feature_profile_controller,
            preset_source=inputs.prompt_segment_preset_source,
        )
        danbooru_actions = PromptDanbooruActionController(
            host=self._danbooru.build_host_adapter(
                source_identity_provider=projection.source_commands.source_identity,
                external_url_actions=external_url_actions,
            ),
            feature_profile=feature_profile_controller,
            wiki_service=inputs.danbooru_wiki_service,
            image_preview_service=inputs.danbooru_image_preview_service,
            recent_posts_service=inputs.danbooru_recent_posts_service,
            url_import_service=inputs.danbooru_url_import_service,
        )
        return PromptEditorServiceCollaborators(
            lora_schedule_service=lora_schedule_service,
            prompt_scheduled_lora_service=scheduled_lora_service,
            scheduled_lora_resolver=scheduled_lora_resolver,
            scheduled_lora_context_provider=scheduled_lora_context,
            feature_profile_controller=feature_profile_controller,
            scene_context_publication=scene_context,
            scene_position_preparation=scene_preparation,
            search_feature_controller=search,
            wildcard_autocomplete_presentation=wildcard_autocomplete,
            wildcard_diagnostics_presentation=wildcard_diagnostics,
            segment_preset_controller=segment_presets,
            danbooru_action_controller=danbooru_actions,
        )
