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

"""Build prompt-editor collaborators without owning their runtime behavior."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.autocomplete.query_service import (
    PromptAutocompleteQueryService,
)
from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptSyntaxSpanView
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
)
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
)

from ..async_work import (
    build_prompt_scheduled_lora_context_coordinator,
    build_prompt_semantic_refresh_controller,
)
from ..commands.context_insertion import (
    PromptCommandCursor,
    PromptCommandContextInsertState,
    PromptContextInsertionService,
)
from ..features import (
    PromptAutocompleteQueryResultLifecycle,
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
    PromptAutocompleteInputPort,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
    PromptDanbooruDialogHostAdapter,
    PromptDanbooruDialogRunner,
    PromptExternalUrlActionRunner,
    PromptExternalUrlOpener,
    PromptInlineLoraContextMenuPresenter,
    PromptInteractionController,
    PromptInteractionEditor,
    PromptSegmentPresetHostAdapter,
    PromptTokenWeightWheelIntentController,
    PromptWeightInteraction,
    PromptWheelController,
    PromptWheelScrollResult,
)
from ..interactions.weight_interaction import PromptWeightInteractionEditor
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from ..projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from ..projection.undo_payload import PromptProjectionUndoPayload
from ..syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from .collaborator_bundle import (
    PromptEditorCollaborators,
    PromptEditorConstructionInputs,
)
from .context import PromptEditorCompositionContext
from .execution_factory import PromptEditorExecutionFactory
from .feature_collaborators import (
    PromptEditorServiceCollaborators,
    PromptEditorSyntaxCollaborators,
)
from .projection_factory import PromptEditorProjectionCollaborators
from .reorder_overlay_factory import PromptSegmentReorderOverlayFactory
from .token_weight_controls_factory import PromptTokenWeightControlsFactory


def build_external_url_action_runner(
    open_url: PromptExternalUrlOpener | None,
) -> PromptExternalUrlActionRunner:
    """Build the prompt-editor external URL action runner."""
    return PromptExternalUrlActionRunner(open_url=open_url)


def build_prompt_document_service(
    inputs: PromptEditorConstructionInputs,
) -> PromptDocumentService:
    """Build the shared document-query authority before feature composition."""
    return PromptDocumentService(
        autocomplete_query_service=PromptAutocompleteQueryService(
            document_semantics=inputs.prompt_document_semantics
        ),
        document_semantics=inputs.prompt_document_semantics,
    )


def _danbooru_dialog_parent(editor: QWidget) -> QWidget:
    """Return the top-level parent used for large browsing dialogs."""
    window = editor.window()
    if isinstance(window, QWidget) and window is not editor:
        return window
    parent = editor.parentWidget()
    if parent is not None:
        return parent
    return editor


class PromptEditorCompositionFactory:
    """Construct prompt-editor collaborators while leaving behavior wiring to owners."""

    def build_danbooru_dialog_host_adapter(
        self,
        context: PromptEditorCompositionContext,
        *,
        source_identity_provider: Callable[[], object | None],
        external_url_actions: PromptExternalUrlActionRunner,
    ) -> PromptDanbooruDialogHostAdapter:
        """Build the Danbooru action host adapter without depending on PromptEditor."""
        return PromptDanbooruDialogHostAdapter(
            source_identity_provider=source_identity_provider,
            dialog_parent_provider=lambda: _danbooru_dialog_parent(context.editor),
            external_url_actions=external_url_actions,
        )

    def build_danbooru_dialog_runner(
        self,
        *,
        action_controller: PromptDanbooruActionController,
        lookup_dispatcher_factory: Callable[[QWidget], QtDanbooruWikiLookupDispatcher]
        | None,
    ) -> PromptDanbooruDialogRunner:
        """Build the native Danbooru wiki dialog execution boundary."""
        if lookup_dispatcher_factory is None:
            return PromptDanbooruDialogRunner(action_controller=action_controller)

        return PromptDanbooruDialogRunner(
            action_controller=action_controller,
            lookup_dispatcher_factory=lookup_dispatcher_factory,
        )

    def build_context_insertion_service(
        self,
        projection_collaborators: PromptEditorProjectionCollaborators,
        *,
        cursor_provider: Callable[[], PromptCommandCursor],
        context_insert_state_provider: Callable[[], PromptCommandContextInsertState],
        focus_restorer: Callable[[], None],
        source_text_provider: Callable[[], str],
    ) -> PromptContextInsertionService[PromptProjectionUndoPayload]:
        """Build prompt-aware context insertion around focused command owners."""
        return PromptContextInsertionService(
            source_commands=projection_collaborators.source_commands,
            trigger_word_commands=projection_collaborators.trigger_word_commands,
            cursor_provider=cursor_provider,
            context_insert_state_provider=context_insert_state_provider,
            focus_restorer=focus_restorer,
            source_text_provider=source_text_provider,
            structured_text_mutations=projection_collaborators.structured_text_mutations,
        )

    def build_service_collaborators(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        execution: PromptEditorExecutionFactory,
        projection_collaborators: PromptEditorProjectionCollaborators,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        *,
        cursor_provider: Callable[[], PromptSegmentCursor],
        cursor_setter: Callable[[object], None],
        external_url_actions: PromptExternalUrlActionRunner,
        source_text_provider: Callable[[], str],
    ) -> PromptEditorServiceCollaborators:
        """Build normalized service collaborators and feature profile state."""

        lora_schedule_service = PromptLoraScheduleService()
        prompt_scheduled_lora_service = (
            inputs.prompt_scheduled_lora_service or PromptScheduledLoraService()
        )

        scheduled_lora_fallback_document_projector = PromptDocumentProjector()

        def inline_scheduled_lora_fallback(
            prompt_text: str,
        ) -> tuple[PromptScheduledLora, ...]:
            """Return inline scheduled LoRAs for autocomplete fallback resolution."""

            if inputs.prompt_lora_catalog_service is None:
                return ()
            return prompt_scheduled_lora_service.inline_scheduled_loras(
                prompt_text=prompt_text,
                document_projector=scheduled_lora_fallback_document_projector,
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
        scheduled_lora_context_provider = (
            build_prompt_scheduled_lora_context_coordinator(
                resolver=scheduled_lora_resolver,
                enabled=feature_profile_controller.lora_trigger_words_enabled,
                parent=context.editor,
                executor=execution.build_task_executor(
                    owner_label="prompt-scheduled-lora"
                ),
            )
        )
        scene_semantics = (
            inputs.prompt_document_semantics or OrdinaryPromptDocumentSemantics()
        )
        scene_context_publication = PromptSceneContextPublication(
            source_identity=projection_collaborators.source_commands.source_identity,
            feature_profile=feature_profile_controller,
            document_semantics=scene_semantics,
        )
        scene_position_preparation = PromptScenePositionContextPreparation(
            source_text=source_text_provider,
            source_identity=projection_collaborators.source_commands.source_identity,
            publication=scene_context_publication,
            document_semantics=scene_semantics,
        )
        search_feature_controller = PromptSearchFeatureController(
            source_identity=projection_collaborators.source_commands.source_identity,
            surface=projection_collaborators.surface,
            feature_profile=feature_profile_controller,
        )
        wildcard_autocomplete_presentation = PromptWildcardAutocompletePresentation(
            feature_profile=feature_profile_controller,
            wildcard_catalog_gateway=inputs.prompt_wildcard_catalog_gateway,
            source_identity_provider=(
                projection_collaborators.source_commands.source_identity
            ),
            request_channel=cast(
                Any,
                execution.build_request_channel(
                    owner_label="prompt-wildcard-autocomplete",
                ),
            ),
        )
        wildcard_diagnostics_presentation = PromptWildcardDiagnosticsPresentation(
            feature_profile=feature_profile_controller,
            wildcard_catalog_gateway=inputs.prompt_wildcard_catalog_gateway,
        )
        segment_host = PromptSegmentPresetHostAdapter(
            host_widget=context.editor,
            cursor_provider=cursor_provider,
            cursor_setter=cursor_setter,
            source_text_provider=source_text_provider,
            source_identity_provider=projection_collaborators.source_commands.source_identity,
        )
        segment_preset_controller = PromptSegmentPresetController(
            host=segment_host,
            text_insertion_executor=context_insertion,
            feature_profile=feature_profile_controller,
            preset_source=inputs.prompt_segment_preset_source,
        )
        danbooru_host = self.build_danbooru_dialog_host_adapter(
            context,
            source_identity_provider=projection_collaborators.source_commands.source_identity,
            external_url_actions=external_url_actions,
        )
        danbooru_action_controller = PromptDanbooruActionController(
            host=danbooru_host,
            feature_profile=feature_profile_controller,
            wiki_service=inputs.danbooru_wiki_service,
            image_preview_service=inputs.danbooru_image_preview_service,
            recent_posts_service=inputs.danbooru_recent_posts_service,
            url_import_service=inputs.danbooru_url_import_service,
        )
        return PromptEditorServiceCollaborators(
            lora_schedule_service=lora_schedule_service,
            prompt_scheduled_lora_service=prompt_scheduled_lora_service,
            scheduled_lora_resolver=scheduled_lora_resolver,
            scheduled_lora_context_provider=scheduled_lora_context_provider,
            feature_profile_controller=feature_profile_controller,
            scene_context_publication=scene_context_publication,
            scene_position_preparation=scene_position_preparation,
            search_feature_controller=search_feature_controller,
            wildcard_autocomplete_presentation=wildcard_autocomplete_presentation,
            wildcard_diagnostics_presentation=wildcard_diagnostics_presentation,
            segment_preset_controller=segment_preset_controller,
            danbooru_action_controller=danbooru_action_controller,
        )

    def build_syntax_collaborators(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        execution: PromptEditorExecutionFactory,
        projection_collaborators: PromptEditorProjectionCollaborators,
        service_collaborators: PromptEditorServiceCollaborators,
        autocomplete: PromptAutocompleteInputPort,
        document_service: PromptDocumentService,
        autocomplete_query_result_lifecycle: PromptAutocompleteQueryResultLifecycle,
        *,
        autocomplete_cursor_state: Callable[[], tuple[int, bool]],
        autocomplete_source_text: Callable[[], str],
        syntax_active_span: Callable[[], PromptSyntaxSpanView | None],
        syntax_cursor_position: Callable[[], int],
        syntax_editor_session_id: int,
        syntax_source_text: Callable[[], str],
        interaction_editor: PromptInteractionEditor,
        weight_interaction_editor: PromptWeightInteractionEditor,
        wheel_surface_scroll_allowed: Callable[[QWheelEvent], bool],
        wheel_surface_scroll_handler: Callable[[QWheelEvent], PromptWheelScrollResult],
        wheel_to_editor_panel: Callable[[QWheelEvent], None],
    ) -> PromptEditorSyntaxCollaborators:
        """Build syntax services, renderers, controls, and interaction controller."""
        semantics = inputs.prompt_document_semantics
        feature_profile = service_collaborators.feature_profile_controller
        mutation_service = PromptMutationService(document_semantics=semantics)
        syntax_profile = feature_profile.syntax_profile()
        syntax_service = PromptSyntaxService(
            inputs.prompt_wildcard_catalog_gateway,
            prompt_lora_catalog_service=inputs.prompt_lora_catalog_service,
            document_semantics=semantics,
        )
        reorder_preview_projection_provider = PromptReorderPreviewProjectionProvider(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )
        reorder_interaction_metrics = PromptReorderInteractionMetricsOwner()
        reorder_overlay_factory = PromptSegmentReorderOverlayFactory(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            geometry_owner=projection_collaborators.surface.reorder_geometry_owner,
            interaction_metrics=reorder_interaction_metrics,
        )
        syntax_renderer_coordinator = PromptSyntaxRendererCoordinator(
            (projection_collaborators.surface,)
        )
        syntax_state_controller = PromptSyntaxStateController(
            active_syntax_span=syntax_active_span,
            cursor_position=syntax_cursor_position,
            editor_session_id=syntax_editor_session_id,
            renderers=syntax_renderer_coordinator,
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            state=projection_collaborators.surface.editor_state,
            source_text=syntax_source_text,
            source_changed_callback=lambda reason: (
                reorder_preview_projection_provider.clear_cache(reason=reason)
            ),
        )
        semantic_refresh_controller = build_prompt_semantic_refresh_controller(
            host=syntax_state_controller,
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            executor=execution.build_task_executor(owner_label="prompt-semantic"),
        )
        autocomplete_source_snapshots = PromptAutocompleteSourceSnapshotController(
            cursor_state=autocomplete_cursor_state,
            document_view_provider=lambda: syntax_state_controller.document_view,
            feature_profile=service_collaborators.feature_profile_controller,
            source_identity=projection_collaborators.source_commands.source_identity,
            source_text=autocomplete_source_text,
        )
        autocomplete_timing_controller = PromptAutocompleteTimingController(
            source_snapshots=autocomplete_source_snapshots,
            lifecycle_requester=autocomplete_query_result_lifecycle,
            lora_autocomplete_enabled=(
                lambda: (
                    service_collaborators.feature_profile_controller.lora_autocomplete_enabled
                )
            ),
        )
        reorder_preview_publication = PromptReorderPreviewPublicationOwner(
            clear_preview_state=projection_collaborators.surface.clear_reorder_preview_state,
            current_document_view=lambda: syntax_state_controller.document_view,
            publish_preview_state=projection_collaborators.surface.set_reorder_preview_state,
            source_identity=projection_collaborators.source_commands.source_identity,
            viewport_width=lambda: projection_collaborators.surface.viewport().width(),
            document_service=document_service,
            projection_provider=reorder_preview_projection_provider,
            metrics=reorder_interaction_metrics,
            interval_ms=PromptReorderPreviewPublicationOwner.DEFAULT_INTERVAL_MS,
        )
        weight_interaction = PromptWeightInteraction(
            editor=weight_interaction_editor,
            autocomplete_timing=autocomplete_timing_controller,
            syntax_state=syntax_state_controller,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            feature_profile=service_collaborators.feature_profile_controller,
            semantic_refresh=semantic_refresh_controller,
            projection=projection_collaborators.surface,
        )
        interaction_controller = PromptInteractionController(
            interaction_editor,
            autocomplete=autocomplete,
            autocomplete_timing_controller=autocomplete_timing_controller,
            syntax_state=syntax_state_controller,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            feature_profile=service_collaborators.feature_profile_controller,
            semantic_refresh_controller=semantic_refresh_controller,
            reorder_overlay_factory=reorder_overlay_factory,
            reorder_preview_publication=reorder_preview_publication,
            weight_interaction=weight_interaction,
        )
        token_weight_wheel_intent = PromptTokenWeightWheelIntentController(
            projection_collaborators.surface
        )
        token_weight_controls = PromptTokenWeightControlsFactory(
            surface=projection_collaborators.surface,
            exact_edit_host=weight_interaction,
            wheel_intent_owner=token_weight_wheel_intent,
        ).create_token_weight_controls()
        wheel_controller = PromptWheelController(
            allow_surface_scroll=wheel_surface_scroll_allowed,
            forward_to_editor_panel=wheel_to_editor_panel,
            handle_surface_scroll=wheel_surface_scroll_handler,
            token_weight_wheel_intent=token_weight_wheel_intent,
            token_weight_wheel_handler=token_weight_controls.handle_host_wheel_event,
        )
        syntax_state_controller.add_renderer(token_weight_controls)
        return PromptEditorSyntaxCollaborators(
            autocomplete_timing_controller=autocomplete_timing_controller,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_profile=syntax_profile,
            syntax_service=syntax_service,
            token_weight_controls=token_weight_controls,
            weight_interaction=weight_interaction,
            wheel_controller=wheel_controller,
            syntax_renderer_coordinator=syntax_renderer_coordinator,
            interaction_controller=interaction_controller,
        )

    def build_resize_handle(
        self,
        context: PromptEditorCompositionContext,
    ) -> QWidget:
        """Build the resize handle used by later signal/layout wiring."""
        return context.resize_handle_factory(context.editor)

    def bundle_collaborators(
        self,
        projection_collaborators: PromptEditorProjectionCollaborators,
        service_collaborators: PromptEditorServiceCollaborators,
        autocomplete: PromptAutocompleteInputPort,
        syntax_collaborators: PromptEditorSyntaxCollaborators,
        inline_lora_menu_presenter: PromptInlineLoraContextMenuPresenter,
        resize_handle: QWidget,
    ) -> PromptEditorCollaborators:
        """Combine phase-local construction results into the public bundle."""
        return PromptEditorCollaborators(
            lora_thumbnail_cache=projection_collaborators.lora_thumbnail_cache,
            lora_thumbnail_preloader=(
                projection_collaborators.lora_thumbnail_preloader
            ),
            surface=projection_collaborators.surface,
            edit_execution=projection_collaborators.edit_execution,
            shell_padding_fill_plane=projection_collaborators.shell_padding_fill_plane,
            fill_plane=projection_collaborators.fill_plane,
            lora_schedule_service=service_collaborators.lora_schedule_service,
            prompt_scheduled_lora_service=(
                service_collaborators.prompt_scheduled_lora_service
            ),
            scheduled_lora_resolver=service_collaborators.scheduled_lora_resolver,
            scheduled_lora_context_provider=(
                service_collaborators.scheduled_lora_context_provider
            ),
            feature_profile_controller=(
                service_collaborators.feature_profile_controller
            ),
            scene_context_publication=service_collaborators.scene_context_publication,
            scene_position_preparation=service_collaborators.scene_position_preparation,
            search_feature_controller=service_collaborators.search_feature_controller,
            wildcard_autocomplete_presentation=(
                service_collaborators.wildcard_autocomplete_presentation
            ),
            wildcard_diagnostics_presentation=(
                service_collaborators.wildcard_diagnostics_presentation
            ),
            segment_preset_controller=service_collaborators.segment_preset_controller,
            danbooru_action_controller=(
                service_collaborators.danbooru_action_controller
            ),
            autocomplete=autocomplete,
            document_service=syntax_collaborators.document_service,
            mutation_service=syntax_collaborators.mutation_service,
            syntax_profile=syntax_collaborators.syntax_profile,
            syntax_service=syntax_collaborators.syntax_service,
            token_weight_controls=syntax_collaborators.token_weight_controls,
            weight_interaction=syntax_collaborators.weight_interaction,
            wheel_controller=syntax_collaborators.wheel_controller,
            syntax_renderer_coordinator=(
                syntax_collaborators.syntax_renderer_coordinator
            ),
            interaction_controller=syntax_collaborators.interaction_controller,
            inline_lora_menu_presenter=inline_lora_menu_presenter,
            resize_handle=resize_handle,
        )
