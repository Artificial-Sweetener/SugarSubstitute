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

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from itertools import count
from typing import Any, Protocol, cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptLoraCatalogItem,
    PromptLoraScheduleService,
    PromptMutationService,
    PromptSourceNormalizationService,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSyntaxProfile,
    PromptSyntaxService,
)
from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)
from substitute.application.ports import (
    PromptTagLexiconSnapshot,
    PromptTagLexiconSnapshotProvider,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.infrastructure.persistence.qt_prompt_parenthesis_education_state import (
    QtPromptParenthesisEducationState,
)
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
)
from ..async_work import (
    QtDanbooruUrlImportDispatcher,
    PromptLoraThumbnailPreloader,
    PromptEditorTaskExecutor,
    PromptLatestWinsRequestChannel,
    PromptScheduledLoraContextProvider,
    build_prompt_scheduled_lora_context_coordinator,
    build_prompt_semantic_refresh_controller,
)
from ..editing_session import PromptCursorState, PromptEditingSession
from ..editing_session.edit_controller import PromptEditController
from ..editing_session.undo_coalescing import (
    DELETE_UNDO_COALESCE_IDLE_MS,
    PromptUndoCoalescingController,
    TYPING_UNDO_COALESCE_IDLE_MS,
)
from ..interactions import (
    PromptAutocompleteAcceptanceController,
    PromptAutocompleteCoordinator,
    PromptAutocompleteController,
    PromptAutocompleteQueryRefreshController,
    PromptAutocompleteSessionController,
    PromptAutocompleteSourceSnapshotController,
    PromptAutocompleteTimingController,
    PromptClipboardHistoryController,
    PromptCommandContextInsertState,
    PromptContextMenuRequestPresenter,
    PromptContextMenuTextInsertionExecutor,
    PromptDanbooruDialogHostAdapter,
    PromptDanbooruDialogRunner,
    PromptEditCommandRouter,
    PromptEditorCommandAdapter,
    PromptExternalUrlActionRunner,
    PromptExternalUrlOpener,
    PromptInlineLoraContextMenuPresenter,
    PromptInlineLoraShellMenu,
    PromptInteractionController,
    PromptLoraPickerPopupPresenter,
    PromptLoraPickerPopupView,
    PromptSegmentPresetHostAdapter,
    PromptTokenWeightWheelIntentController,
    PromptTriggerWordActionAdapter,
    PromptTriggerWordInsertionExecutor,
    PromptWheelController,
)
from ..interactions.parenthesis_education_controller import (
    PromptParenthesisEducationController,
)
from ..projection.autocomplete_ghost_text import PromptAutocompleteGhostTextPublisher
from ..interactions.undo_coalescing_timer import PromptQtUndoCoalescingTimer
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..commands import PromptCommandSourceIdentity, PromptFeatureSnapshotIdentity
from ..features import (
    PromptAutocompleteQueryController,
    PromptAutocompleteResultController,
    PromptAutocompleteSceneContextController,
    PromptAutocompleteScheduledLoraContextController,
    PromptAutocompleteScheduledLoraCurrentContext,
    PromptAutocompleteWildcardResultProvider,
    PromptContextMenuActionController,
    PromptDanbooruActionController,
    PromptDanbooruPasteImportController,
    PromptFeatureProfileController,
    PromptLoraMetadataFeatureController,
    PromptLoraTriggerWordController,
    PromptSegmentPresetController,
    PromptSceneFeatureController,
    PromptScenePositionContextSnapshot,
    PromptSearchFeatureController,
    PromptWildcardFeatureController,
    prompt_feature_profile_from_legacy_syntax,
)
from ..projection.surface import (
    PromptProjectionSurface,
    PromptProjectionUndoPayload,
)
from ..projection.reorder_preview_projection import (
    PromptReorderPreviewProjectionProvider,
)
from ..qt_lifecycle import qt_object_is_alive
from ..syntax_renderers import (
    PromptSyntaxRendererCoordinator,
    PromptSyntaxStateController,
)
from ..overlays import (
    PromptAutocompleteLoraWall,
    PromptAutocompletePanel,
    PromptAutocompletePanelPresenter,
    PromptLoraWallView,
    PromptTokenWeightControls,
    show_lora_picker_popup,
)
from .collaborator_bundle import (
    PromptEditorCollaborators,
    PromptEditorConstructionInputs,
)
from .reorder_overlay_factory import PromptSegmentReorderOverlayFactory
from .token_weight_controls_factory import PromptTokenWeightControlsFactory

type _PromptSceneContextReader = Callable[[int], PromptScenePositionContextSnapshot]


class PromptEditorFillPlaneFactory(Protocol):
    """Create one prompt-editor fill plane without coupling composition to widget.py."""

    def __call__(
        self,
        editor: QWidget,
        surface: PromptProjectionSurface,
        parent: QWidget,
        *,
        shell_padding_only: bool,
    ) -> QWidget:
        """Return a fill-plane widget for the supplied editor surface."""


class PromptEditorResizeHandleFactory(Protocol):
    """Create the prompt-editor resize handle without importing widget.py."""

    def __call__(self, editor: QWidget) -> QWidget:
        """Return a resize-handle widget for the supplied editor."""


@dataclass(frozen=True, slots=True)
class PromptEditorCompositionContext:
    """Carry construction-only values supplied by the live public widget."""

    editor: QWidget
    shell_viewport: QWidget
    autocomplete_limit: int
    autocomplete_minimum_prefix_length: int
    fill_plane_factory: PromptEditorFillPlaneFactory
    resize_handle_factory: PromptEditorResizeHandleFactory


@dataclass(frozen=True, slots=True)
class PromptEditorProjectionCollaborators:
    """Carry projection-surface construction results."""

    lora_thumbnail_cache: PromptLoraThumbnailCache
    lora_thumbnail_preloader: PromptLoraThumbnailPreloader
    surface: PromptProjectionSurface
    edit_controller: PromptEditController[PromptProjectionUndoPayload]
    edit_command_router: PromptEditCommandRouter[Any]
    danbooru_paste_import_controller: PromptDanbooruPasteImportController[Any]
    clipboard_history_controller: PromptClipboardHistoryController[Any]
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
    scene_feature_controller: PromptSceneFeatureController
    search_feature_controller: PromptSearchFeatureController
    wildcard_feature_controller: PromptWildcardFeatureController
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
    wheel_controller: PromptWheelController
    syntax_renderer_coordinator: PromptSyntaxRendererCoordinator
    interaction_controller: PromptInteractionController


def build_external_url_action_runner(
    open_url: PromptExternalUrlOpener | None,
) -> PromptExternalUrlActionRunner:
    """Build the prompt-editor external URL action runner."""

    return PromptExternalUrlActionRunner(open_url=open_url)


class _QtPromptTextClipboard:
    """Adapt QApplication clipboard text to the clipboard/history controller."""

    def text(self) -> str:
        """Return the current system clipboard text."""

        return QApplication.clipboard().text()

    def set_text(self, text: str) -> None:
        """Set the current system clipboard text."""

        QApplication.clipboard().setText(text)


@dataclass(frozen=True, slots=True)
class _PromptSurfaceEditBlockActions:
    """Adapt the edit controller to the surface viewport action protocol."""

    edit_controller: PromptEditController[PromptProjectionUndoPayload]

    def begin_surface_edit_block(self, *, finish_typing: bool = True) -> None:
        """Begin a grouped edit block through the composed edit controller."""

        self.edit_controller.begin_edit_block(finish_typing=finish_typing)

    def end_surface_edit_block(self) -> None:
        """End a grouped edit block through the composed edit controller."""

        self.edit_controller.end_edit_block()

    def finish_surface_pending_key_edit_block(self, *, reason: str) -> None:
        """Flush pending key edits through the composed edit controller."""

        self.edit_controller.finish_pending_key_edit_block(reason=reason)


class _PromptAutocompleteCurrentContextBridge:
    """Bind scheduled-LoRA autocomplete context to the composed coordinator."""

    def __init__(self) -> None:
        """Initialize an unbound current-context bridge."""

        self._current_context: PromptAutocompleteScheduledLoraCurrentContext | None = (
            None
        )

    def bind(
        self,
        current_context: PromptAutocompleteScheduledLoraCurrentContext,
    ) -> None:
        """Attach the live autocomplete current-context provider."""

        self._current_context = current_context

    def current_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the bound autocomplete source identity."""

        if self._current_context is None:
            return None
        return self._current_context.current_source_identity()

    def current_query_identity(self) -> Hashable | None:
        """Return the bound autocomplete query identity."""

        if self._current_context is None:
            return None
        return self._current_context.current_query_identity()

    def refresh_current_query(self) -> None:
        """Refresh the bound autocomplete query when available."""

        if self._current_context is not None:
            self._current_context.refresh_current_query()


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


def _build_undo_coalescing_controller(
    *,
    surface: PromptProjectionSurface,
    edit_controller: PromptEditController[PromptProjectionUndoPayload],
) -> PromptUndoCoalescingController[PromptProjectionUndoPayload]:
    """Wire typing/delete undo coalescing for one projection surface."""

    undo_coalescing_controller = PromptUndoCoalescingController[
        PromptProjectionUndoPayload
    ](
        edit_controller=edit_controller,
        typing_timer=PromptQtUndoCoalescingTimer(
            parent=surface,
            interval_ms=TYPING_UNDO_COALESCE_IDLE_MS,
        ),
        delete_timer=PromptQtUndoCoalescingTimer(
            parent=surface,
            interval_ms=DELETE_UNDO_COALESCE_IDLE_MS,
        ),
        cursor_position=lambda: surface.cursor_position,
        selection_empty=lambda: not surface.textCursor().hasSelection(),
    )
    edit_controller.set_pending_key_flusher(undo_coalescing_controller)
    return undo_coalescing_controller


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
        editing_session = _build_projection_editing_session()
        surface = PromptProjectionSurface(
            context.shell_viewport,
            editing_session=editing_session,
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
        cast(
            Any, context.editor
        )._parenthesis_education_controller = parenthesis_education_controller
        surface.set_defer_source_rebuilds_until_prompt_state(True)
        edit_controller = PromptEditController[PromptProjectionUndoPayload](
            session=editing_session,
            undo_payload_provider=surface,
            availability_signal_sink=surface,
            projection_mutation_sink=surface,
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
        edit_command_router = PromptEditCommandRouter[PromptProjectionUndoPayload](
            edit_controller=edit_controller,
            normalizer=source_normalizer,
            mutation_sink=surface,
            source_text_provider=surface.toPlainText,
            cursor_position_provider=lambda: surface.cursor_position,
            anchor_position_provider=lambda: surface.anchor_position,
            exact_source_provider=surface.exact_source_editing_enabled,
        )
        undo_coalescing_controller = _build_undo_coalescing_controller(
            surface=surface,
            edit_controller=edit_controller,
        )
        danbooru_paste_import_controller = PromptDanbooruPasteImportController[Any](
            edit_controller=edit_controller,
            source_replacement_executor=edit_command_router,
            import_executor=edit_command_router,
            normalizer=source_normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
            dispatcher=QtDanbooruUrlImportDispatcher(
                context.editor,
                is_alive=qt_object_is_alive,
                executor=self.build_prompt_task_executor(
                    inputs,
                    context,
                    owner_label="prompt-danbooru-import",
                ),
            ),
        )
        clipboard_history_controller = PromptClipboardHistoryController[Any](
            edit_controller=edit_controller,
            clipboard=_QtPromptTextClipboard(),
            sink=surface,
            source_replacement_executor=edit_command_router,
            danbooru_paste_scheduler=danbooru_paste_import_controller,
            editing_enabled=surface.editing_enabled,
            paste_completed=cast(Any, context.editor)._handle_clipboard_paste_completed,
        )
        surface.attach_runtime_mutation_actions(
            source_mutation_actions=edit_command_router,
            edit_block_actions=_PromptSurfaceEditBlockActions(edit_controller),
            clipboard_history_actions=clipboard_history_controller,
            undo_coalescing_actions=undo_coalescing_controller,
        )
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
            edit_controller=edit_controller,
            edit_command_router=edit_command_router,
            danbooru_paste_import_controller=danbooru_paste_import_controller,
            clipboard_history_controller=clipboard_history_controller,
            shell_padding_fill_plane=shell_padding_fill_plane,
            fill_plane=fill_plane,
        )

    def build_command_adapter(
        self,
        context: PromptEditorCompositionContext,
        projection_collaborators: PromptEditorProjectionCollaborators,
        *,
        context_insert_state_provider: Callable[[], PromptCommandContextInsertState],
    ) -> PromptEditorCommandAdapter:
        """Build the host command adapter around controller-owned source identity."""

        editor = cast(Any, context.editor)
        return PromptEditorCommandAdapter(
            executor=projection_collaborators.edit_command_router,
            source_identity_provider=(
                projection_collaborators.edit_command_router
            ).prompt_command_source_identity,
            cursor_provider=editor.textCursor,
            context_insert_state_provider=context_insert_state_provider,
            focus_restorer=editor.setFocus,
        )

    def build_service_collaborators(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        projection_collaborators: PromptEditorProjectionCollaborators,
        command_adapter: PromptEditorCommandAdapter,
        *,
        external_url_actions: PromptExternalUrlActionRunner,
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
        scene_feature_controller = PromptSceneFeatureController(
            host=cast(Any, context.editor),
            feature_profile=feature_profile_controller,
        )
        search_feature_controller = PromptSearchFeatureController(
            host=cast(Any, context.editor),
            surface=projection_collaborators.surface,
            feature_profile=feature_profile_controller,
        )
        wildcard_feature_controller = PromptWildcardFeatureController(
            feature_profile=feature_profile_controller,
            wildcard_catalog_gateway=inputs.prompt_wildcard_catalog_gateway,
            host=cast(Any, context.editor),
            parent=context.editor,
            request_channel=cast(
                Any,
                self.build_prompt_request_channel(
                    inputs,
                    context,
                    owner_label="prompt-wildcard-autocomplete",
                ),
            ),
        )
        segment_host = PromptSegmentPresetHostAdapter(
            host=cast(Any, context.editor),
            source_identity_provider=command_adapter.prompt_command_source_identity,
        )
        segment_preset_controller = PromptSegmentPresetController(
            host=segment_host,
            text_insertion_executor=command_adapter,
            feature_profile=feature_profile_controller,
            preset_source=inputs.prompt_segment_preset_source,
        )
        danbooru_host = self.build_danbooru_dialog_host_adapter(
            context,
            source_identity_provider=command_adapter.prompt_command_source_identity,
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
            scene_feature_controller=scene_feature_controller,
            search_feature_controller=search_feature_controller,
            wildcard_feature_controller=wildcard_feature_controller,
            segment_preset_controller=segment_preset_controller,
            danbooru_action_controller=danbooru_action_controller,
        )

    def build_prompt_menu_presenter(
        self,
        context: PromptEditorCompositionContext,
        *,
        action_snapshot_provider: PromptContextMenuActionController,
        segment_presets: PromptSegmentPresetController,
        command_adapter: PromptTriggerWordInsertionExecutor,
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
            action_snapshot_provider=action_snapshot_provider,
            segment_presets=segment_presets,
            trigger_word_action_adapter=PromptTriggerWordActionAdapter(
                action_parent=context.editor,
                text_insertion_executor=command_adapter,
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
        lora_metadata: PromptLoraMetadataFeatureController,
        lora_trigger_words: PromptLoraTriggerWordController,
        prepared_scene_context_at_position: _PromptSceneContextReader,
        command_adapter: PromptTriggerWordInsertionExecutor,
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
                text_insertion_executor=command_adapter,
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
        lora_metadata: PromptLoraMetadataFeatureController,
        lora_thumbnail_cache: PromptLoraThumbnailCache,
        command_adapter: PromptContextMenuTextInsertionExecutor,
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
            text_insertion_executor=command_adapter,
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
    ) -> PromptAutocompleteCoordinator:
        """Build the autocomplete coordinator from prepared construction inputs."""

        def create_lora_wall(
            parent: QWidget,
            *,
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
            editor=cast(Any, context.editor),
            panel_factory=lambda parent: PromptAutocompletePanel(parent),
            lora_wall_factory=create_lora_wall,
            lora_thumbnail_cache=projection_collaborators.lora_thumbnail_cache,
        )
        autocomplete_ghost_text_publisher = PromptAutocompleteGhostTextPublisher(
            preview_sink=cast(Any, context.editor),
        )
        autocomplete_acceptance_controller = PromptAutocompleteAcceptanceController(
            editor=cast(Any, context.editor),
        )
        autocomplete_current_context = _PromptAutocompleteCurrentContextBridge()
        autocomplete_scene_context_controller = (
            PromptAutocompleteSceneContextController(
                scene_context_provider=service_collaborators.scene_feature_controller,
            )
        )
        autocomplete_scheduled_lora_context_controller = PromptAutocompleteScheduledLoraContextController(
            context_provider=(service_collaborators.scheduled_lora_context_provider),
            current_context=autocomplete_current_context,
            enabled=(
                service_collaborators.feature_profile_controller.lora_trigger_words_enabled
            ),
        )
        autocomplete_result_controller = PromptAutocompleteResultController(
            prompt_autocomplete_gateway=inputs.prompt_autocomplete_gateway,
            limit=context.autocomplete_limit,
            scene_feature=service_collaborators.scene_feature_controller,
            wildcard_feature=cast(
                PromptAutocompleteWildcardResultProvider,
                service_collaborators.wildcard_feature_controller,
            ),
            prompt_lora_catalog_service=inputs.prompt_lora_catalog_service,
            trigger_word_provider=autocomplete_scheduled_lora_context_controller,
        )
        autocomplete_session_controller = PromptAutocompleteSessionController()
        autocomplete = PromptAutocompleteCoordinator(
            cast(Any, context.editor),
            autocomplete_result_controller=autocomplete_result_controller,
            autocomplete_scene_context_controller=autocomplete_scene_context_controller,
            autocomplete_scheduled_lora_context_controller=(
                autocomplete_scheduled_lora_context_controller
            ),
            autocomplete_presenter=autocomplete_presenter,
            autocomplete_ghost_text_publisher=autocomplete_ghost_text_publisher,
            autocomplete_ghost_text_enabled=(
                service_collaborators.feature_profile_controller.autocomplete_ghost_text_enabled
            ),
            autocomplete_acceptance_controller=autocomplete_acceptance_controller,
            autocomplete_session_controller=autocomplete_session_controller,
            lora_autocomplete_enabled=(
                service_collaborators.feature_profile_controller.lora_autocomplete_enabled
            ),
            lora_thumbnail_cache_available=(
                projection_collaborators.lora_thumbnail_cache is not None
            ),
        )
        autocomplete_current_context.bind(autocomplete)
        return autocomplete

    def build_syntax_collaborators(
        self,
        inputs: PromptEditorConstructionInputs,
        context: PromptEditorCompositionContext,
        projection_collaborators: PromptEditorProjectionCollaborators,
        service_collaborators: PromptEditorServiceCollaborators,
        autocomplete: PromptAutocompleteController,
    ) -> PromptEditorSyntaxCollaborators:
        """Build syntax services, renderers, controls, and interaction controller."""

        document_service = PromptDocumentService()
        mutation_service = PromptMutationService()
        syntax_profile = (
            service_collaborators.feature_profile_controller.syntax_profile()
        )
        syntax_service = PromptSyntaxService(
            inputs.prompt_wildcard_catalog_gateway,
            prompt_lora_catalog_service=inputs.prompt_lora_catalog_service,
        )
        reorder_preview_projection_provider = PromptReorderPreviewProjectionProvider(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )
        reorder_overlay_factory = PromptSegmentReorderOverlayFactory(
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
        )
        syntax_renderer_coordinator = PromptSyntaxRendererCoordinator(
            (projection_collaborators.surface,)
        )
        syntax_state_controller = PromptSyntaxStateController(
            editor=cast(Any, context.editor),
            renderers=syntax_renderer_coordinator,
            document_service=document_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
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
        autocomplete_query_refresh_controller = (
            PromptAutocompleteQueryRefreshController(
                autocomplete=autocomplete,
                query_controller=PromptAutocompleteQueryController(
                    document_service=document_service,
                    feature_profile=service_collaborators.feature_profile_controller,
                    minimum_prefix_length=context.autocomplete_minimum_prefix_length,
                ),
            )
        )
        autocomplete_source_snapshots = PromptAutocompleteSourceSnapshotController(
            cast(Any, context.editor),
            document_view_provider=lambda: syntax_state_controller.document_view,
            feature_profile=service_collaborators.feature_profile_controller,
        )
        autocomplete_timing_controller = PromptAutocompleteTimingController(
            source_snapshots=autocomplete_source_snapshots,
            lifecycle_requester=autocomplete_query_refresh_controller,
            lora_autocomplete_enabled=(
                lambda: (
                    service_collaborators.feature_profile_controller.lora_autocomplete_enabled
                )
            ),
        )
        interaction_controller = PromptInteractionController(
            cast(Any, context.editor),
            autocomplete=autocomplete,
            autocomplete_minimum_prefix_length=context.autocomplete_minimum_prefix_length,
            autocomplete_timing_controller=autocomplete_timing_controller,
            syntax_state=syntax_state_controller,
            document_service=document_service,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            feature_profile=service_collaborators.feature_profile_controller,
            semantic_refresh_controller=semantic_refresh_controller,
            reorder_overlay_factory=reorder_overlay_factory,
            exact_weight_projection=projection_collaborators.surface,
            reorder_preview_projection_provider=reorder_preview_projection_provider,
        )
        token_weight_wheel_intent = PromptTokenWeightWheelIntentController()
        token_weight_controls = PromptTokenWeightControlsFactory(
            surface=projection_collaborators.surface,
            exact_edit_host=interaction_controller,
            wheel_intent_owner=token_weight_wheel_intent,
        ).create_token_weight_controls()
        wheel_controller = PromptWheelController(
            cast(Any, context.editor),
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
        autocomplete: PromptAutocompleteController,
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
            edit_controller=projection_collaborators.edit_controller,
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
            scene_feature_controller=service_collaborators.scene_feature_controller,
            search_feature_controller=service_collaborators.search_feature_controller,
            wildcard_feature_controller=(
                service_collaborators.wildcard_feature_controller
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
            wheel_controller=syntax_collaborators.wheel_controller,
            syntax_renderer_coordinator=(
                syntax_collaborators.syntax_renderer_coordinator
            ),
            interaction_controller=syntax_collaborators.interaction_controller,
            inline_lora_menu_presenter=inline_lora_menu_presenter,
            resize_handle=resize_handle,
        )
