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

"""Own prompt-editor autocomplete presentation composition."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService

from ..autocomplete_preview_state import PromptAutocompletePreviewState
from ..commands.autocomplete_commands import PromptAutocompleteAcceptance
from ..commands.contracts import PromptCommandResult
from ..features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQueryResultLifecycle,
    PromptAutocompleteResultController,
    PromptAutocompleteSceneContextController,
    PromptAutocompleteScheduledLoraContextController,
    PromptAutocompleteWildcardResultProvider,
)
from ..interactions import (
    PromptAutocompleteAcceptanceController,
    PromptAutocompleteAcceptanceLifecycle,
    PromptAutocompleteInputAdapter,
    PromptAutocompleteSessionController,
    PromptAutocompleteSessionPublication,
    PromptExternalUrlActionRunner,
)
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..overlays import (
    PromptAutocompleteLoraWall,
    PromptAutocompletePanel,
    PromptAutocompletePanelPresenter,
    PromptLoraWallView,
)
from ..projection.autocomplete_ghost_text import PromptAutocompleteGhostTextPublisher
from .collaborator_bundle import (
    PromptEditorAutocompleteCollaborators,
    PromptEditorConstructionInputs,
)
from .context import PromptEditorCompositionContext
from .feature_collaborators import PromptEditorServiceCollaborators
from .projection_factory import PromptEditorProjectionCollaborators


class PromptEditorAutocompleteFactory:
    """Build autocomplete collaborators from one prepared editor graph."""

    def __init__(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
    ) -> None:
        """Retain immutable construction inputs and shell-owned context."""
        self._inputs = inputs
        self._context = context

    def build(
        self,
        projection_collaborators: PromptEditorProjectionCollaborators,
        service_collaborators: PromptEditorServiceCollaborators,
        external_url_actions: PromptExternalUrlActionRunner,
        document_service: PromptDocumentService,
        *,
        autocomplete_cursor_position: Callable[[], int],
        autocomplete_focus_host: QWidget,
        complete_lora_autocomplete_replacement: Callable[[], None],
        cursor_rect: Callable[[], QRect],
        execute_autocomplete_acceptance: Callable[
            [PromptAutocompleteAcceptance],
            PromptCommandResult[object],
        ],
        restore_autocomplete_focus: Callable[[], None],
        viewport: Callable[[], QWidget],
    ) -> PromptEditorAutocompleteCollaborators:
        """Build the autocomplete coordinator and publication lifecycle."""

        def create_lora_wall(
            parent: QWidget,
            thumbnail_cache: object,
        ) -> PromptAutocompleteLoraWall:
            """Create the concrete LoRA wall used inside autocomplete."""
            return cast(
                PromptAutocompleteLoraWall,
                PromptLoraWallView(
                    parent,
                    thumbnail_cache=cast(PromptLoraThumbnailCache, thumbnail_cache),
                    open_url=external_url_actions.open_civitai_model_page,
                    metadata_action_handler=self._inputs.model_metadata_action_handler,
                ),
            )

        presenter = PromptAutocompletePanelPresenter(
            host_widget=self._context.editor,
            viewport=viewport,
            cursor_rect=cursor_rect,
            panel_factory=lambda parent: PromptAutocompletePanel(parent),
            lora_wall_factory=create_lora_wall,
            lora_thumbnail_cache=projection_collaborators.lora_thumbnail_cache,
        )

        def publish_preview_state(
            preview_state: PromptAutocompletePreviewState | None,
        ) -> None:
            """Publish through the current observable preview owner."""

            projection_collaborators.surface.autocomplete_preview.set_preview_state(
                preview_state
            )

        ghost_text = PromptAutocompleteGhostTextPublisher(
            publish_preview_state=publish_preview_state,
        )
        acceptance = PromptAutocompleteAcceptanceController(
            cursor_position=autocomplete_cursor_position,
            current_source_identity=(
                projection_collaborators.source_commands.source_identity
            ),
            execute_acceptance=execute_autocomplete_acceptance,
            complete_lora_replacement=complete_lora_autocomplete_replacement,
        )
        scene_context = PromptAutocompleteSceneContextController(
            scene_context_identity=(
                lambda: (
                    service_collaborators.scene_context_publication.scene_context_identity
                )
            ),
        )
        scheduled_lora_context = PromptAutocompleteScheduledLoraContextController(
            context_provider=service_collaborators.scheduled_lora_context_provider,
            enabled=(
                service_collaborators.feature_profile_controller.lora_trigger_words_enabled
            ),
        )
        results = PromptAutocompleteResultController(
            prompt_autocomplete_gateway=self._inputs.prompt_autocomplete_gateway,
            limit=self._context.autocomplete_limit,
            scene_autocomplete_state=(
                lambda: (
                    service_collaborators.scene_context_publication.snapshot.autocomplete
                )
            ),
            wildcard_feature=cast(
                PromptAutocompleteWildcardResultProvider,
                service_collaborators.wildcard_autocomplete_presentation,
            ),
            prompt_lora_catalog_service=self._inputs.prompt_lora_catalog_service,
            trigger_word_provider=scheduled_lora_context,
        )
        sessions = PromptAutocompleteSessionController()
        publication = PromptAutocompleteSessionPublication(
            sessions=sessions,
            presenter=presenter,
            ghost_text_publisher=ghost_text,
            ghost_text_enabled=(
                service_collaborators.feature_profile_controller.autocomplete_ghost_text_enabled
            ),
        )
        acceptance_lifecycle = PromptAutocompleteAcceptanceLifecycle(
            acceptance_controller=acceptance,
            session_publication=publication,
        )
        autocomplete = PromptAutocompleteInputAdapter(
            autocomplete_focus_host,
            restore_focus=restore_autocomplete_focus,
            acceptance_lifecycle=acceptance_lifecycle,
            session_publication=publication,
        )
        query_result_lifecycle = PromptAutocompleteQueryResultLifecycle(
            query_controller=PromptAutocompleteQueryController(
                document_service=document_service,
                feature_profile=service_collaborators.feature_profile_controller,
                minimum_prefix_length=(
                    self._context.autocomplete_minimum_prefix_length
                ),
            ),
            result_controller=results,
            scene_context_controller=scene_context,
            publication=publication,
            current_source_identity=(
                projection_collaborators.source_commands.source_identity
            ),
            lora_autocomplete_enabled=(
                lambda: (
                    service_collaborators.feature_profile_controller.lora_autocomplete_enabled
                )
            ),
            lora_thumbnail_cache_available=(
                lambda: projection_collaborators.lora_thumbnail_cache is not None
            ),
        )
        scheduled_lora_context.bind_current_context(query_result_lifecycle)
        return PromptEditorAutocompleteCollaborators(
            autocomplete=autocomplete,
            query_result_lifecycle=query_result_lifecycle,
        )
