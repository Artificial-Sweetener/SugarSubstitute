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

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import count
from typing import Any, cast

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

from substitute.application.ports import (
    PromptTagLexiconSnapshot,
    PromptTagLexiconSnapshotProvider,
)
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
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.application.prompt_editor.editing.structured_text import (
    PromptStructuredTextMutationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.application.prompt_editor.lora.schedule import PromptLoraScheduleService
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.infrastructure.persistence.qt_prompt_parenthesis_education_state import (
    QtPromptParenthesisEducationState,
)
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)

from ..async_work import (
    PromptEditorTaskExecutor,
    PromptLatestWinsRequestChannel,
    PromptLoraThumbnailPreloader,
    PromptScheduledLoraContextProvider,
    QtDanbooruUrlImportDispatcher,
    build_prompt_scheduled_lora_context_coordinator,
    build_prompt_semantic_refresh_controller,
)
from ..commands.autocomplete_commands import (
    PromptAutocompleteAcceptance,
    PromptAutocompleteCommandService,
)
from ..commands.contracts import PromptCommandResult
from ..commands.context_insertion import (
    PromptCommandCursor,
    PromptCommandContextInsertState,
    PromptContextInsertionService,
)
from ..commands.diagnostic_commands import PromptDiagnosticCommandService
from ..commands.execution import PromptEditExecution
from ..commands.feature_commands import PromptFeatureSnapshotIdentity
from ..commands.reorder_commands import PromptReorderCommandService
from ..commands.source_service import PromptSourceCommandService
from ..commands.trigger_word_commands import PromptTriggerWordCommandService
from ..commands.weight_commands import PromptWeightCommandService
from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQueryResultLifecycle,
    PromptAutocompleteResultController,
    PromptAutocompleteSceneContextController,
    PromptAutocompleteScheduledLoraContextController,
    PromptAutocompleteWildcardResultProvider,
    PromptContextMenuPreparationLifecycle,
    PromptContextMenuSnapshotAssembler,
    PromptDanbooruActionController,
    PromptDanbooruPasteImportController,
    PromptFeatureProfileController,
    PromptLoraMetadataPresentation,
    PromptLoraTriggerWordController,
    PromptSceneContextPublication,
    PromptScenePositionContextPreparation,
    PromptScenePositionContextSnapshot,
    PromptSearchFeatureController,
    PromptSegmentPresetController,
    PromptWildcardAutocompletePresentation,
    PromptWildcardDiagnosticsPresentation,
    prompt_feature_profile_from_legacy_syntax,
)
from ..features.prompt_segment_selection import PromptSegmentCursor
from ..interactions import (
    PromptAutocompleteAcceptanceController,
    PromptAutocompleteAcceptanceLifecycle,
    PromptAutocompleteInputAdapter,
    PromptAutocompleteInputPort,
    PromptAutocompleteSessionPublication,
    PromptAutocompleteSessionController,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
    PromptContextMenuRequestPresenter,
    PromptDanbooruDialogHostAdapter,
    PromptDanbooruDialogRunner,
    PromptExternalUrlActionRunner,
    PromptExternalUrlOpener,
    PromptInlineLoraContextMenuPresenter,
    PromptInlineLoraShellMenu,
    PromptInteractionController,
    PromptInteractionEditor,
    PromptLoraPickerPopupPresenter,
    PromptLoraPickerPopupView,
    PromptSegmentPresetHostAdapter,
    PromptTokenWeightWheelIntentController,
    PromptTriggerWordActionAdapter,
    PromptWeightInteraction,
    PromptWheelController,
    PromptWheelScrollResult,
)
from ..interactions.weight_interaction import PromptWeightInteractionEditor
from ..interactions.parenthesis_education_controller import (
    PromptParenthesisEducationController,
)
from ..interactions.clipboard_history_controller import PromptClipboardHistoryActions
from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..interactions.reorder_preview_publication import (
    PromptReorderPreviewPublicationOwner,
)
from ..interactions.region_pointer_controller import PromptRegionPointerController
from ..interactions.region_inline_editor import PromptRegionInlineEditor
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..overlays import (
    PromptAutocompleteLoraWall,
    PromptAutocompletePanel,
    PromptAutocompletePanelPresenter,
    PromptLoraWallView,
    PromptTokenWeightControls,
    show_lora_picker_popup,
)
from ..projection.autocomplete_ghost_text import PromptAutocompleteGhostTextPublisher
from ..projection.reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
)
from ..projection.surface import (
    PromptProjectionSurface,
)
from ..projection.undo_payload import PromptProjectionUndoPayload
from ..qt_lifecycle import qt_object_is_alive
from ..syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from .collaborator_bundle import (
    PromptEditorAutocompleteCollaborators,
    PromptEditorCollaborators,
    PromptEditorConstructionInputs,
)
from .editing_runtime_factory import PromptProjectionEditingRuntimeBuilder
from .reorder_overlay_factory import PromptSegmentReorderOverlayFactory
from .token_weight_controls_factory import PromptTokenWeightControlsFactory

type _PromptSceneContextReader = Callable[[int], PromptScenePositionContextSnapshot]


type PromptEditorFillPlaneFactory = Callable[..., QWidget]
"""Create one shell-owned fill plane from its concrete host and surface."""


type PromptEditorResizeHandleFactory = Callable[[Any], QWidget]
"""Create the shell resize handle from its concrete public host."""


@dataclass(frozen=True, slots=True)
class PromptEditorCompositionContext:
    """Carry construction-only values supplied by the live public widget."""

    editor: QWidget
    shell_viewport: QWidget
    autocomplete_limit: int
    autocomplete_minimum_prefix_length: int
    fill_plane_factory: PromptEditorFillPlaneFactory
    resize_handle_factory: PromptEditorResizeHandleFactory


def _publish_region_hover(
    editor: QWidget,
    surface: PromptProjectionSurface,
    region_index: int | None,
) -> None:
    """Update local chrome and publish panel-level regional hover intent."""

    surface.set_region_hovered(region_index)
    signal = getattr(editor, "regionHovered", None)
    emit = getattr(signal, "emit", None)
    if callable(emit):
        emit(region_index)


@dataclass(frozen=True, slots=True)
class PromptEditorProjectionCollaborators:
    """Carry projection-surface construction results."""

    lora_thumbnail_cache: PromptLoraThumbnailCache
    lora_thumbnail_preloader: PromptLoraThumbnailPreloader
    surface: PromptProjectionSurface
    edit_execution: PromptEditExecution[PromptProjectionUndoPayload]
    source_commands: PromptSourceCommandService[PromptProjectionUndoPayload]
    autocomplete_commands: PromptAutocompleteCommandService[PromptProjectionUndoPayload]
    diagnostic_commands: PromptDiagnosticCommandService[PromptProjectionUndoPayload]
    weight_commands: PromptWeightCommandService[PromptProjectionUndoPayload]
    reorder_commands: PromptReorderCommandService[PromptProjectionUndoPayload]
    trigger_word_commands: PromptTriggerWordCommandService[PromptProjectionUndoPayload]
    structured_text_mutations: PromptStructuredTextMutationService
    parenthesis_education_controller: PromptParenthesisEducationController
    danbooru_paste_import_controller: PromptDanbooruPasteImportController[Any]
    clipboard_history_controller: PromptClipboardHistoryActions
    shell_padding_fill_plane: QWidget
    fill_plane: QWidget


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
    interaction_controller: PromptInteractionController


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


def _build_projection_editing_session() -> PromptEditingSession[
    PromptProjectionUndoPayload
]:
    """Create the source-backed editing session before projection wiring."""
    return PromptEditingSession[PromptProjectionUndoPayload](
        source_text="",
        source_revision=0,
        cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
        max_undo_states=100,
        max_redo_states=100,
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

    _prompt_executor_request_ids = count(1)

    def build_prompt_task_executor(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        *,
        owner_label: str,
    ) -> PromptEditorTaskExecutor:
        """Build one prompt task adapter from the composed execution factory."""
        if inputs.prompt_task_executor_factory is None:
            raise RuntimeError("prompt_task_executor_factory is required.")
        request_id = next(self._prompt_executor_request_ids)
        return inputs.prompt_task_executor_factory(
            context.editor,
            f"{owner_label}:{id(context.editor):x}:{request_id}",
        )

    def build_prompt_request_channel(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        *,
        owner_label: str,
    ) -> PromptLatestWinsRequestChannel[object]:
        """Build one latest-wins prompt request channel from shared execution."""
        return PromptLatestWinsRequestChannel(
            executor=self.build_prompt_task_executor(
                inputs,
                context,
                owner_label=owner_label,
            )
        )

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

    def build_projection_collaborators(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        *,
        paste_completed: Callable[[str], None],
    ) -> PromptEditorProjectionCollaborators:
        """Build the projection surface and passive fill-plane widgets."""

        lora_thumbnail_cache = PromptLoraThumbnailCache(
            inputs.thumbnail_asset_repository
        )
        lora_thumbnail_preloader = PromptLoraThumbnailPreloader(
            cache=lora_thumbnail_cache,
            asset_repository=inputs.thumbnail_asset_repository,
            parent=context.editor,
            executor=self.build_prompt_task_executor(
                inputs,
                context,
                owner_label="prompt-thumbnail",
            ),
        )
        tag_snapshot = PromptTagLexiconSnapshot()
        if isinstance(
            inputs.prompt_autocomplete_gateway,
            PromptTagLexiconSnapshotProvider,
        ):
            tag_snapshot = (
                inputs.prompt_autocomplete_gateway.prepared_prompt_tag_snapshot()
            )
        source_normalizer = PromptSourceNormalizationService(tag_snapshot=tag_snapshot)
        structured_text_mutations = PromptStructuredTextMutationService(
            inputs.prompt_document_semantics
        )
        editing_session = _build_projection_editing_session()
        editing_runtime_builder = PromptProjectionEditingRuntimeBuilder(
            session=editing_session,
            normalizer=source_normalizer,
            structured_text_mutations=structured_text_mutations,
            danbooru_dispatcher=QtDanbooruUrlImportDispatcher(
                context.editor,
                is_alive=qt_object_is_alive,
                executor=self.build_prompt_task_executor(
                    inputs,
                    context,
                    owner_label="prompt-danbooru-import",
                ),
            ),
            paste_completed=paste_completed,
        )
        surface = PromptProjectionSurface(
            context.shell_viewport,
            editing_session=editing_session,
            editing_runtime_factory=editing_runtime_builder,
            document_semantics=inputs.prompt_document_semantics,
            lora_thumbnail_cache=lora_thumbnail_cache,
            lora_thumbnail_preloader=lora_thumbnail_preloader,
        )
        parenthesis_education_controller = PromptParenthesisEducationController(
            state=QtPromptParenthesisEducationState(),
            target=surface,
            parent=context.editor,
        )
        surface.implicitParenthesisAuthored.connect(
            parenthesis_education_controller.handle_authored_nested_parentheses
        )
        surface.set_defer_source_rebuilds_until_prompt_state(True)
        edit_execution = surface.edit_execution
        source_commands = surface.source_commands
        region_inline_editor = PromptRegionInlineEditor(
            viewport=surface.viewport(),
            target_provider=surface.region_edit_target,
            scroll_offset=surface.projection_scroll_offset,
            active_region_sink=surface.set_region_editing,
            draft_sink=surface.set_region_editing_draft,
        )
        region_pointer_controller = PromptRegionPointerController(
            document_view=surface.prompt_document_view,
            source_commands=source_commands,
            scroll_offset=surface.projection_scroll_offset,
            cursor_position=lambda: surface.cursor_position,
            inline_editor=region_inline_editor,
            hover_sink=lambda index: _publish_region_hover(
                context.editor,
                surface,
                index,
            ),
        )
        surface.pointer_interactions.set_region_double_click_handler(
            region_pointer_controller.handle_double_click
        )
        surface.pointer_interactions.set_region_hover_handler(
            region_pointer_controller.handle_hover
        )
        surface.pointer_interactions.set_region_keyboard_rename_handler(
            region_pointer_controller.handle_keyboard_rename
        )
        autocomplete_commands = PromptAutocompleteCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
            structured_text_mutations=structured_text_mutations,
        )
        diagnostic_commands = PromptDiagnosticCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        weight_commands = PromptWeightCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        reorder_commands = PromptReorderCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        trigger_word_commands = PromptTriggerWordCommandService(
            execution=edit_execution,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
            structured_text_mutations=structured_text_mutations,
        )
        danbooru_paste_import_controller = editing_runtime_builder.danbooru_controller
        clipboard_history_controller = surface.clipboard_history_actions
        shell_padding_fill_plane = context.fill_plane_factory(
            context.editor,
            surface,
            context.editor,
            shell_padding_only=True,
        )
        fill_plane = context.fill_plane_factory(
            context.editor,
            surface,
            context.shell_viewport,
            shell_padding_only=False,
        )
        return PromptEditorProjectionCollaborators(
            lora_thumbnail_cache=lora_thumbnail_cache,
            lora_thumbnail_preloader=lora_thumbnail_preloader,
            surface=surface,
            edit_execution=edit_execution,
            source_commands=source_commands,
            autocomplete_commands=autocomplete_commands,
            diagnostic_commands=diagnostic_commands,
            weight_commands=weight_commands,
            reorder_commands=reorder_commands,
            trigger_word_commands=trigger_word_commands,
            structured_text_mutations=structured_text_mutations,
            parenthesis_education_controller=parenthesis_education_controller,
            danbooru_paste_import_controller=danbooru_paste_import_controller,
            clipboard_history_controller=clipboard_history_controller,
            shell_padding_fill_plane=shell_padding_fill_plane,
            fill_plane=fill_plane,
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
                executor=self.build_prompt_task_executor(
                    inputs,
                    context,
                    owner_label="prompt-scheduled-lora",
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
                self.build_prompt_request_channel(
                    inputs,
                    context,
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

    def build_prompt_menu_presenter(
        self,
        context: PromptEditorCompositionContext,
        *,
        snapshot_reader: PromptContextMenuSnapshotAssembler,
        preparation: PromptContextMenuPreparationLifecycle,
        segment_presets: PromptSegmentPresetController,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        trigger_word_identity_validator: Callable[
            [PromptFeatureSnapshotIdentity], bool
        ],
        schedule_lora: Callable[[], None],
        open_danbooru_wiki_for_selection: Callable[[str], object],
        queue_scene: Callable[[str], None],
        is_read_only: Callable[[], bool],
        rich_prompt_rendering_enabled: Callable[[], bool],
        toggle_rich_prompt_rendering: Callable[[bool], None],
    ) -> PromptContextMenuRequestPresenter:
        """Build the prompt context-menu request presenter."""
        return PromptContextMenuRequestPresenter(
            snapshot_reader=snapshot_reader,
            preparation=preparation,
            segment_presets=segment_presets,
            trigger_word_action_adapter=PromptTriggerWordActionAdapter(
                action_parent=context.editor,
                text_insertion_executor=context_insertion,
                identity_validator=trigger_word_identity_validator,
            ),
            schedule_lora=schedule_lora,
            open_danbooru_wiki_for_selection=open_danbooru_wiki_for_selection,
            queue_scene=queue_scene,
            is_read_only=is_read_only,
            rich_prompt_rendering_enabled=rich_prompt_rendering_enabled,
            toggle_rich_prompt_rendering=toggle_rich_prompt_rendering,
        )

    def build_inline_lora_menu_presenter(
        self,
        context: PromptEditorCompositionContext,
        *,
        lora_metadata: PromptLoraMetadataPresentation,
        lora_trigger_words: PromptLoraTriggerWordController,
        prepared_scene_context_at_position: _PromptSceneContextReader,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        shell_menu: PromptInlineLoraShellMenu,
        finish_pending_key_edit_block: Callable[[str], None],
        external_url_actions: PromptExternalUrlActionRunner,
        metadata_action_handler: (ModelMetadataContextActionHandler | None) = None,
    ) -> PromptInlineLoraContextMenuPresenter:
        """Build the inline LoRA context-menu presenter."""
        return PromptInlineLoraContextMenuPresenter(
            lora_metadata=lora_metadata,
            lora_trigger_words=lora_trigger_words,
            prepared_scene_context_at_position=prepared_scene_context_at_position,
            trigger_word_action_adapter=PromptTriggerWordActionAdapter(
                action_parent=context.editor,
                text_insertion_executor=context_insertion,
                identity_validator=lora_trigger_words.action_identity_is_current,
            ),
            shell_menu=shell_menu,
            finish_pending_key_edit_block=finish_pending_key_edit_block,
            external_url_actions=external_url_actions,
            metadata_action_handler=metadata_action_handler,
        )

    def build_lora_picker_popup_presenter(
        self,
        context: PromptEditorCompositionContext,
        *,
        lora_metadata: PromptLoraMetadataPresentation,
        lora_thumbnail_cache: PromptLoraThumbnailCache,
        context_insertion: PromptContextInsertionService[PromptProjectionUndoPayload],
        last_context_menu_global_pos: Callable[[], QPoint | None],
        cursor_global_position: Callable[[], QPoint],
        external_url_actions: PromptExternalUrlActionRunner,
        metadata_action_handler: (ModelMetadataContextActionHandler | None) = None,
    ) -> PromptLoraPickerPopupPresenter:
        """Build the LoRA picker popup presenter."""

        def create_lora_picker_popup(
            parent: QWidget,
            items: Iterable[PromptLoraCatalogItem],
            *,
            thumbnail_cache: PromptLoraThumbnailCache,
            global_position: QPoint,
        ) -> PromptLoraPickerPopupView:
            """Create the concrete overlay popup behind the presenter protocol."""

            return cast(
                PromptLoraPickerPopupView,
                show_lora_picker_popup(
                    parent,
                    items,
                    thumbnail_cache=thumbnail_cache,
                    global_position=global_position,
                    open_url=external_url_actions.open_civitai_model_page,
                    metadata_action_handler=metadata_action_handler,
                ),
            )

        return PromptLoraPickerPopupPresenter(
            parent=context.editor,
            data_source=lora_metadata,
            thumbnail_cache=lora_thumbnail_cache,
            text_insertion_executor=context_insertion,
            popup_factory=create_lora_picker_popup,
            last_context_menu_global_pos=last_context_menu_global_pos,
            cursor_global_position=cursor_global_position,
        )

    def build_autocomplete(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
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
        """Build the autocomplete coordinator from prepared construction inputs."""

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
                    metadata_action_handler=inputs.model_metadata_action_handler,
                ),
            )

        autocomplete_presenter = PromptAutocompletePanelPresenter(
            host_widget=context.editor,
            viewport=viewport,
            cursor_rect=cursor_rect,
            panel_factory=lambda parent: PromptAutocompletePanel(parent),
            lora_wall_factory=create_lora_wall,
            lora_thumbnail_cache=projection_collaborators.lora_thumbnail_cache,
        )
        autocomplete_ghost_text_publisher = PromptAutocompleteGhostTextPublisher(
            publish_preview_state=(
                projection_collaborators.surface.set_autocomplete_preview_state
            ),
        )
        autocomplete_acceptance_controller = PromptAutocompleteAcceptanceController(
            cursor_position=autocomplete_cursor_position,
            current_source_identity=(
                projection_collaborators.source_commands.source_identity
            ),
            execute_acceptance=execute_autocomplete_acceptance,
            complete_lora_replacement=complete_lora_autocomplete_replacement,
        )
        autocomplete_scene_context_controller = PromptAutocompleteSceneContextController(
            scene_context_identity=(
                lambda: (
                    service_collaborators.scene_context_publication.scene_context_identity
                )
            ),
        )
        autocomplete_scheduled_lora_context_controller = PromptAutocompleteScheduledLoraContextController(
            context_provider=(service_collaborators.scheduled_lora_context_provider),
            enabled=(
                service_collaborators.feature_profile_controller.lora_trigger_words_enabled
            ),
        )
        autocomplete_result_controller = PromptAutocompleteResultController(
            prompt_autocomplete_gateway=inputs.prompt_autocomplete_gateway,
            limit=context.autocomplete_limit,
            scene_autocomplete_state=(
                lambda: (
                    service_collaborators.scene_context_publication.snapshot.autocomplete
                )
            ),
            wildcard_feature=cast(
                PromptAutocompleteWildcardResultProvider,
                service_collaborators.wildcard_autocomplete_presentation,
            ),
            prompt_lora_catalog_service=inputs.prompt_lora_catalog_service,
            trigger_word_provider=autocomplete_scheduled_lora_context_controller,
        )
        autocomplete_session_controller = PromptAutocompleteSessionController()
        session_publication = PromptAutocompleteSessionPublication(
            sessions=autocomplete_session_controller,
            presenter=autocomplete_presenter,
            ghost_text_publisher=autocomplete_ghost_text_publisher,
            ghost_text_enabled=(
                service_collaborators.feature_profile_controller.autocomplete_ghost_text_enabled
            ),
        )
        acceptance_lifecycle = PromptAutocompleteAcceptanceLifecycle(
            acceptance_controller=autocomplete_acceptance_controller,
            session_publication=session_publication,
        )
        autocomplete = PromptAutocompleteInputAdapter(
            autocomplete_focus_host,
            restore_focus=restore_autocomplete_focus,
            acceptance_lifecycle=acceptance_lifecycle,
            session_publication=session_publication,
        )
        query_result_lifecycle = PromptAutocompleteQueryResultLifecycle(
            query_controller=PromptAutocompleteQueryController(
                document_service=document_service,
                feature_profile=service_collaborators.feature_profile_controller,
                minimum_prefix_length=context.autocomplete_minimum_prefix_length,
            ),
            result_controller=autocomplete_result_controller,
            scene_context_controller=autocomplete_scene_context_controller,
            publication=session_publication,
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
        autocomplete_scheduled_lora_context_controller.bind_current_context(
            query_result_lifecycle
        )
        return PromptEditorAutocompleteCollaborators(
            autocomplete=autocomplete,
            query_result_lifecycle=query_result_lifecycle,
        )

    def build_syntax_collaborators(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
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
            executor=self.build_prompt_task_executor(
                inputs,
                context,
                owner_label="prompt-semantic",
            ),
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
