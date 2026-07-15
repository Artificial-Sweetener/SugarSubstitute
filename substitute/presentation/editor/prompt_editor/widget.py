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

"""Host the custom prompt projection surface inside a QFluent multiline shell."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any, cast

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QContextMenuEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFocusEvent,
    QHideEvent,
    QKeyEvent,
    QMouseEvent,
    QMoveEvent,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QScrollBar, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    TextEdit as QFluentTextEdit,
)
from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptMutationService,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSpellcheckService,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.widgets.wheel_permission import wheel_event_is_allowed
from substitute.shared.logging.logger import get_logger

from .commands import (
    PromptAutocompleteAcceptance,
    PromptCommandResult,
    PromptCommandSourceRange,
    PromptCommandSourceIdentity,
    PromptCommandTextReplacement,
    PromptDiagnosticAction,
    PromptDiagnosticCommandResult,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
    PromptWeightActionRequest,
    PromptWeightCommandResult,
)
from .editing_session import PromptSourceEditOrigin
from .overlays import (
    PromptAutocompletePanel,
    PromptTokenWeightControls,
)
from .composition import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorCompositionContext,
    PromptEditorCompositionFactory,
    PromptEditorConstructionInputs,
    PromptEditorConstructionObserver,
    PromptEditorTaskExecutorFactory,
    apply_prompt_editor_initial_layout,
    bind_prompt_editor_diagnostics_signals,
    bind_prompt_editor_signals,
    build_external_url_action_runner,
    qt_object_is_alive,
    wire_prompt_editor_construction_lifecycle,
)
from .autocomplete_preview_state import PromptAutocompletePreviewState
from .features import (
    PromptContextMenuActionController,
    PromptDanbooruPasteImportController,
    PromptLoraMetadataFeatureController,
    PromptLoraTriggerWordController,
)
from .interactions import (
    PromptContextMenuRequestPresenter,
    PromptDanbooruDialogRunner,
    PromptEditorCommandAdapter,
    PromptExternalUrlActionRunner,
    PromptInlineLoraContextMenuPresenter,
    PromptLoraPickerPopupPresenter,
    PromptReorderOverlayPort,
    PromptWheelScrollResult,
)
from .projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionToken,
    PromptWeightControlIdentity,
)
from .projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)
from .mime_data_policy import (
    mime_data_has_prompt_plain_text,
    prompt_plain_text_from_mime_data,
)
from .projection.selection_geometry import PromptProjectionSourceLineRect
from .projection.reorder_preview import PromptReorderPreviewState
from .shell import (
    PromptEditorShell,
    PromptFillPlane,
    PromptResizeHandle,
    PromptShellContextMenuController,
    PromptShellChromeSurface,
    PromptShellQFluentChrome,
    PromptShellScrollDelegate,
    PromptShellScrollSurface,
    PromptShellSizingController,
)
from .features import (
    PromptDiagnosticsFeatureController,
    PromptFeatureProfileController,
    PromptSegmentPresetSource,
    PromptSceneFeatureController,
    PromptSearchFeatureController,
)

_LOGGER = get_logger("presentation.editor.prompt_editor")


class PromptEditor(QFluentTextEdit):
    """Expose the public prompt editor API through a QFluent-faithful shell."""

    _AUTOCOMPLETE_MIN_PREFIX = 2
    _AUTOCOMPLETE_LIMIT = 10
    _MAX_VISIBLE_LINES = 10
    _PROMPT_SEGMENT_MENU_TEXT_WIDTH = 220

    textChanged = Signal()
    cursorPositionChanged = Signal()
    undoAvailableChanged = Signal(bool)
    redoAvailableChanged = Signal(bool)
    resized = Signal()
    manualScrollHeightChanged = Signal(object)
    richPromptRenderingEnabledChanged = Signal(bool)
    sceneQueueRequested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        danbooru_url_import_service: DanbooruUrlImportService | None = None,
        danbooru_wiki_service: DanbooruWikiContentService | None = None,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
        prompt_feature_profile: PromptEditorFeatureProfile | None = None,
        prompt_syntax_profile: PromptSyntaxProfile | None = None,
        maximum_visible_lines: int | None = _MAX_VISIBLE_LINES,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        prompt_scheduled_lora_service: PromptScheduledLoraService | None = None,
        scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
        | None = None,
        prompt_segment_preset_source: PromptSegmentPresetSource | None = None,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        open_url: Callable[[str], bool] | None = None,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None,
        danbooru_lookup_dispatcher_factory: (
            DanbooruWikiLookupDispatcherFactory | None
        ) = None,
    ) -> None:
        """Create the QFluent host shell and attach the custom projection surface."""

        construction_inputs = PromptEditorConstructionInputs(
            parent=parent,
            prompt_autocomplete_gateway=prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            danbooru_url_import_service=danbooru_url_import_service,
            danbooru_wiki_service=danbooru_wiki_service,
            danbooru_image_preview_service=danbooru_image_preview_service,
            danbooru_recent_posts_service=danbooru_recent_posts_service,
            prompt_feature_profile=prompt_feature_profile,
            prompt_syntax_profile=prompt_syntax_profile,
            maximum_visible_lines=maximum_visible_lines,
            prompt_lora_catalog_service=prompt_lora_catalog_service,
            thumbnail_asset_repository=thumbnail_asset_repository,
            prompt_scheduled_lora_service=prompt_scheduled_lora_service,
            scheduled_lora_resolver=scheduled_lora_resolver,
            prompt_segment_preset_source=prompt_segment_preset_source,
            prompt_spellcheck_service=prompt_spellcheck_service,
            open_url=open_url,
            model_metadata_action_handler=model_metadata_action_handler,
            prompt_task_executor_factory=prompt_task_executor_factory,
            danbooru_lookup_dispatcher_factory=danbooru_lookup_dispatcher_factory,
        )
        parent = construction_inputs.parent
        prompt_autocomplete_gateway = construction_inputs.prompt_autocomplete_gateway
        prompt_wildcard_catalog_gateway = (
            construction_inputs.prompt_wildcard_catalog_gateway
        )
        maximum_visible_lines = construction_inputs.maximum_visible_lines
        prompt_lora_catalog_service = construction_inputs.prompt_lora_catalog_service
        thumbnail_asset_repository = construction_inputs.thumbnail_asset_repository
        prompt_segment_preset_source = construction_inputs.prompt_segment_preset_source
        prompt_spellcheck_service = construction_inputs.prompt_spellcheck_service
        open_url = construction_inputs.open_url

        construction_observer = PromptEditorConstructionObserver(_LOGGER)
        init_started_at = construction_observer.started_at()
        phase_started_at = construction_observer.started_at()
        super().__init__(parent)
        self._shell = PromptEditorShell(
            host=self,
            shell_viewport=super().viewport(),
        )
        self._qfluent_chrome = PromptShellQFluentChrome(
            host=self,
            shell_viewport=super().viewport(),
            content_viewport=self._content_viewport_for_chrome,
            apply_host_placeholder=self._apply_host_placeholder_for_chrome,
            source_text=self.toPlainText,
            surface=self._surface_for_chrome,
            shell_padding_fill_plane=(
                self._shell_padding_fill_plane_for_scroll_delegate
            ),
            fill_plane=self._fill_plane_for_scroll_delegate,
            sync_surface_scroll_metrics_from_host=(
                lambda: self._scroll_delegate.sync_surface_scroll_metrics_from_host()
            ),
            update_backing_fill=lambda rect: self._update_backing_fill_for_chrome(rect),
            finish_pending_key_edit_block=(
                lambda reason: self._edit_controller.finish_pending_key_edit_block(
                    reason=reason
                )
            ),
            schedule_lora_metadata_catchup=(
                lambda: self._schedule_lora_metadata_catchup_if_needed()
            ),
            handle_focus_out=self._handle_focus_out_for_chrome,
            handle_hide=self._handle_hide_for_chrome,
            handle_move=self._handle_move_for_chrome,
            schedule_manual_height_layout_reapply=(
                lambda: self._sizing.schedule_manual_height_layout_reapply()
            ),
            observes_manual_resize_bounds_viewport=(
                lambda watched: self._sizing.observes_manual_resize_bounds_viewport(
                    watched
                )
            ),
            schedule_shell_geometry_sync=(
                lambda: self._scroll_delegate.schedule_shell_geometry_sync()
            ),
            handle_viewport_wheel_event=(
                lambda event: self._handle_viewport_wheel_event(event)
            ),
        )
        self._scroll_delegate = PromptShellScrollDelegate(
            host=self,
            shell_viewport=super().viewport(),
            host_scrollbar=self._host_scrollbar_for_scroll_delegate,
            surface=self._surface_for_scroll_delegate,
            shell_padding_fill_plane=(
                self._shell_padding_fill_plane_for_scroll_delegate
            ),
            fill_plane=self._fill_plane_for_scroll_delegate,
            token_weight_controls=self._token_weight_controls_for_scroll_delegate,
            handle_content_height_changed=(
                lambda content_height: (
                    self._sizing.handle_surface_content_height_changed(content_height)
                )
            ),
            layout_resize_handle=lambda: self._sizing.layout_resize_handle(),
            handle_viewport_scroll=self._handle_viewport_scroll_for_scroll_delegate,
            handle_resize=self._handle_resize_for_scroll_delegate,
            resized=self.resized,
        )
        self._sizing = PromptShellSizingController(
            host=self,
            maximum_visible_lines=maximum_visible_lines,
            manual_scroll_height_changed=self.manualScrollHeightChanged,
            surface_content_height=self._surface_content_height_for_sizing,
            projection_line_height=self._projection_line_height_for_sizing,
            surface_is_alive=self._surface_is_alive_for_sizing,
            sync_surface_scroll_metrics_from_host=(
                self._scroll_delegate.sync_surface_scroll_metrics_from_host
            ),
            sync_host_scrollbar_shell=(self._scroll_delegate.sync_host_scrollbar_shell),
            schedule_shell_geometry_sync=(
                self._scroll_delegate.schedule_shell_geometry_sync
            ),
            update_fill_planes=self._update_sizing_fill_planes,
            resize_handle=self._resize_handle_for_sizing,
            visible_scrollbar=self._scroll_delegate.visible_scrollbar,
            ancestor_external_wheel_handler=self._ancestor_external_wheel_handler,
        )
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(False)
        self.setCursorWidth(0)
        self._scroll_delegate.configure_host_scroll_delegate()

        construction_observer.log_timing(
            "Initialized prompt editor host shell",
            started_at=phase_started_at,
            maximum_visible_lines=maximum_visible_lines,
            level="debug",
        )
        self.setAcceptDrops(True)
        composition_factory = PromptEditorCompositionFactory()
        composition_context = PromptEditorCompositionContext(
            editor=self,
            shell_viewport=self._shell_viewport(),
            autocomplete_limit=self._AUTOCOMPLETE_LIMIT,
            autocomplete_minimum_prefix_length=self._AUTOCOMPLETE_MIN_PREFIX,
            fill_plane_factory=PromptFillPlane,
            resize_handle_factory=PromptResizeHandle,
        )
        phase_started_at = construction_observer.started_at()
        projection_collaborators = composition_factory.build_projection_collaborators(
            construction_inputs,
            composition_context,
        )
        self._lora_thumbnail_cache = projection_collaborators.lora_thumbnail_cache
        self._lora_thumbnail_preloader = (
            projection_collaborators.lora_thumbnail_preloader
        )
        self._surface = projection_collaborators.surface
        self.setFocusProxy(self._surface)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._edit_controller = projection_collaborators.edit_controller
        self._clipboard_history_controller = (
            projection_collaborators.clipboard_history_controller
        )
        self._danbooru_paste_import_controller: PromptDanbooruPasteImportController[
            Any
        ] = projection_collaborators.danbooru_paste_import_controller
        self._shell_padding_fill_plane = (
            projection_collaborators.shell_padding_fill_plane
        )
        self._fill_plane = projection_collaborators.fill_plane
        self._shell_padding_fill_plane.lower()
        self._fill_plane.lower()
        self._qfluent_chrome.configure_owned_fill_plane()
        self._qfluent_chrome.bind_theme_refresh()
        self._surface.raise_()
        self._command_adapter: PromptEditorCommandAdapter = (
            composition_factory.build_command_adapter(
                composition_context,
                projection_collaborators,
                context_insert_state_provider=(
                    lambda: self._shell_context_menu.consume_context_insert_state()
                ),
            )
        )

        construction_observer.log_timing(
            "Initialized prompt editor projection surface",
            started_at=phase_started_at,
            has_thumbnail_repository=thumbnail_asset_repository is not None,
            level="debug",
        )
        phase_started_at = construction_observer.started_at()
        self._external_url_action_runner: PromptExternalUrlActionRunner = (
            build_external_url_action_runner(open_url)
        )
        service_collaborators = composition_factory.build_service_collaborators(
            construction_inputs,
            composition_context,
            projection_collaborators,
            self._command_adapter,
            external_url_actions=self._external_url_action_runner,
        )
        self._feature_profile_controller: PromptFeatureProfileController = (
            service_collaborators.feature_profile_controller
        )
        self._scene_feature_controller: PromptSceneFeatureController = (
            service_collaborators.scene_feature_controller
        )
        self._search_feature_controller: PromptSearchFeatureController = (
            service_collaborators.search_feature_controller
        )
        self._wildcard_feature_controller = (
            service_collaborators.wildcard_feature_controller
        )
        self._segment_preset_controller = (
            service_collaborators.segment_preset_controller
        )
        self._danbooru_action_controller = (
            service_collaborators.danbooru_action_controller
        )
        self._danbooru_dialog_runner: PromptDanbooruDialogRunner = (
            composition_factory.build_danbooru_dialog_runner(
                action_controller=self._danbooru_action_controller,
                lookup_dispatcher_factory=(
                    construction_inputs.danbooru_lookup_dispatcher_factory
                ),
            )
        )
        self._diagnostics_feature_controller = PromptDiagnosticsFeatureController(
            host=self,
            surface=self._surface,
            feature_profile=self._feature_profile_controller,
            wildcard_feature=self._wildcard_feature_controller,
            spellcheck_service=prompt_spellcheck_service,
            parent=self,
            request_channel=cast(
                Any,
                composition_factory.build_prompt_request_channel(
                    construction_inputs,
                    composition_context,
                    owner_label="prompt-diagnostics",
                ),
            ),
            bind_signals=lambda controller: bind_prompt_editor_diagnostics_signals(
                self,
                controller,
            ),
        )
        spellcheck_feature_enabled = self._feature_profile_controller.spellcheck_enabled
        self._danbooru_paste_import_controller.configure_danbooru_url_import(
            self._danbooru_action_controller.url_import_service,
            enabled=self._danbooru_action_controller.url_import_enabled,
        )
        construction_observer.log_timing(
            "Initialized prompt editor service state",
            started_at=phase_started_at,
            has_lora_catalog=prompt_lora_catalog_service is not None,
            has_spellcheck_service=prompt_spellcheck_service is not None,
            has_segment_presets=prompt_segment_preset_source is not None,
            level="debug",
        )
        phase_started_at = construction_observer.started_at()
        self._autocomplete = composition_factory.build_autocomplete(
            construction_inputs,
            composition_context,
            projection_collaborators,
            service_collaborators,
            self._external_url_action_runner,
        )
        construction_observer.log_timing(
            "Initialized prompt editor autocomplete services",
            started_at=phase_started_at,
            has_lora_catalog=prompt_lora_catalog_service is not None,
            lora_autocomplete_enabled=(
                self._feature_profile_controller.lora_autocomplete_enabled
            ),
            trigger_word_suggestions_enabled=(
                self._feature_profile_controller.lora_trigger_words_enabled
            ),
            level="debug",
        )
        phase_started_at = construction_observer.started_at()
        syntax_collaborators = composition_factory.build_syntax_collaborators(
            construction_inputs,
            composition_context,
            projection_collaborators,
            service_collaborators,
            self._autocomplete,
        )
        self._document_service = syntax_collaborators.document_service
        self._mutation_service = syntax_collaborators.mutation_service
        self._syntax_profile = syntax_collaborators.syntax_profile
        self._syntax_service = syntax_collaborators.syntax_service
        self._token_weight_controls = syntax_collaborators.token_weight_controls
        self._wheel_controller = syntax_collaborators.wheel_controller
        self._syntax_renderer_coordinator = (
            syntax_collaborators.syntax_renderer_coordinator
        )
        self._interaction_controller = syntax_collaborators.interaction_controller
        self._autocomplete_refresh_controller = (
            syntax_collaborators.autocomplete_timing_controller
        )
        self._lora_metadata_feature_controller = PromptLoraMetadataFeatureController(
            host=self,
            feature_profile=self._feature_profile_controller,
            lora_catalog=prompt_lora_catalog_service,
            lora_schedule_service=(service_collaborators.lora_schedule_service),
            scheduled_lora_service=(
                service_collaborators.prompt_scheduled_lora_service
            ),
            thumbnail_repository_available=(thumbnail_asset_repository is not None),
            parent=self,
        )
        self._lora_trigger_word_controller = PromptLoraTriggerWordController(
            host=self,
            scheduled_lora_service=(
                service_collaborators.prompt_scheduled_lora_service
            ),
            scheduled_lora_context=(
                service_collaborators.scheduled_lora_context_provider
            ),
            feature_profile_id=(
                lambda: self._feature_profile_controller.identity.feature_profile_id
            ),
            catalog_revision=(
                lambda: self._lora_metadata_feature_controller.snapshot.catalog_revision
            ),
            trigger_words_enabled=(
                lambda: self._feature_profile_controller.lora_trigger_words_enabled
            ),
            effective_prompts=self._scene_feature_controller.effective_prompt_texts,
        )
        self._context_menu_action_controller = PromptContextMenuActionController(
            diagnostics=self._diagnostics_feature_controller,
            lora_metadata=self._lora_metadata_feature_controller,
            lora_trigger_words=self._lora_trigger_word_controller,
            scene=self._scene_feature_controller,
            segment_presets=self._segment_preset_controller,
            danbooru=self._danbooru_action_controller,
            source_identity_provider=(
                self._command_adapter.prompt_command_source_identity
            ),
            feature_profile_id_provider=(
                lambda: self._feature_profile_controller.identity.feature_profile_id
            ),
        )
        self._lora_picker_popup_presenter: PromptLoraPickerPopupPresenter = (
            composition_factory.build_lora_picker_popup_presenter(
                composition_context,
                lora_metadata=self._lora_metadata_feature_controller,
                lora_thumbnail_cache=self._lora_thumbnail_cache,
                command_adapter=self._command_adapter,
                last_context_menu_global_pos=(
                    lambda: self._shell_context_menu.last_context_menu_global_pos()
                ),
                cursor_global_position=(
                    lambda: self.mapToGlobal(self.cursorRect().bottomLeft())
                ),
                external_url_actions=self._external_url_action_runner,
                metadata_action_handler=(
                    construction_inputs.model_metadata_action_handler
                ),
            )
        )
        self._prompt_menu_presenter: PromptContextMenuRequestPresenter = (
            composition_factory.build_prompt_menu_presenter(
                composition_context,
                action_snapshot_provider=self._context_menu_action_controller,
                segment_presets=self._segment_preset_controller,
                command_adapter=self._command_adapter,
                trigger_word_identity_validator=(
                    self._lora_trigger_word_controller.action_identity_is_current
                ),
                schedule_lora=self._lora_picker_popup_presenter.open_lora_picker,
                open_danbooru_wiki_for_selection=(
                    self._danbooru_dialog_runner.open_wiki_for_selection
                ),
                queue_scene=self.sceneQueueRequested.emit,
                is_read_only=self.isReadOnly,
                rich_prompt_rendering_enabled=self.richPromptRenderingEnabled,
                toggle_rich_prompt_rendering=(self.setRichPromptRenderingEnabled),
            )
        )
        self._shell_context_menu = PromptShellContextMenuController(
            host=self,
            finish_pending_key_edit_block=(
                lambda reason: self._edit_controller.finish_pending_key_edit_block(
                    reason=reason
                )
            ),
            has_text_selection=lambda: self.textCursor().hasSelection(),
            selected_prompt_range_and_text=(
                self._prompt_menu_presenter.selected_prompt_range_and_text
            ),
            selected_prompt_text=self._prompt_menu_presenter.selected_prompt_text,
            restore_prompt_selection_snapshot=(
                self._prompt_menu_presenter.restore_prompt_selection_snapshot
            ),
            source_position_for_global_pos=self._source_position_for_global_pos,
            prompt_menu_requires_custom_actions=(
                self._prompt_menu_requires_custom_actions
            ),
            show_native_context_menu=(
                lambda event: QFluentTextEdit.contextMenuEvent(self, event)
            ),
            clipboard_actions=self._clipboard_history_controller,
            prompt_menu_requests=self._prompt_menu_presenter,
        )
        self._inline_lora_menu_presenter: PromptInlineLoraContextMenuPresenter = (
            composition_factory.build_inline_lora_menu_presenter(
                composition_context,
                lora_metadata=self._lora_metadata_feature_controller,
                lora_trigger_words=self._lora_trigger_word_controller,
                prepared_scene_context_at_position=(
                    lambda source_position: (
                        self._scene_feature_controller.prepare_position_context(
                            source_position,
                            reason="inline_lora_context_menu",
                        )
                    )
                ),
                command_adapter=self._command_adapter,
                shell_menu=self._shell_context_menu,
                finish_pending_key_edit_block=(
                    lambda reason: self._edit_controller.finish_pending_key_edit_block(
                        reason=reason
                    )
                ),
                external_url_actions=self._external_url_action_runner,
                metadata_action_handler=(
                    construction_inputs.model_metadata_action_handler
                ),
            )
        )
        self._segment_preset_controller.refresh_menu_model(
            reason="prompt_editor_constructed"
        )
        construction_observer.log_timing(
            "Initialized prompt editor syntax services",
            started_at=phase_started_at,
            spellcheck_feature_enabled=spellcheck_feature_enabled,
            level="debug",
        )
        phase_started_at = construction_observer.started_at()
        lifecycle_wiring_result = wire_prompt_editor_construction_lifecycle(
            self._diagnostics_feature_controller
        )
        construction_observer.log_timing(
            "Scheduled prompt editor spellcheck services",
            started_at=phase_started_at,
            diagnostics_controller_enabled=(
                lifecycle_wiring_result.diagnostics_controller_enabled
            ),
            diagnostics_activation_pending=(
                lifecycle_wiring_result.diagnostics_activation_pending
            ),
            level="debug",
        )
        phase_started_at = construction_observer.started_at()
        resize_handle = composition_factory.build_resize_handle(composition_context)
        collaborators = composition_factory.bundle_collaborators(
            projection_collaborators,
            service_collaborators,
            self._autocomplete,
            syntax_collaborators,
            self._inline_lora_menu_presenter,
            resize_handle,
        )
        self._resize_handle = collaborators.resize_handle
        self._resize_handle.hide()
        bind_prompt_editor_signals(
            self,
            collaborators,
            lora_source_changes=self._lora_trigger_word_controller,
        )

        apply_prompt_editor_initial_layout(self)
        construction_observer.log_timing(
            "Initialized prompt editor layout",
            started_at=phase_started_at,
            maximum_visible_lines=maximum_visible_lines,
            level="debug",
        )
        construction_observer.log_timing(
            "Initialized prompt editor widget",
            started_at=init_started_at,
            maximum_visible_lines=maximum_visible_lines,
            has_lora_catalog=prompt_lora_catalog_service is not None,
            has_spellcheck_service=prompt_spellcheck_service is not None,
            level="debug",
        )

    @property
    def _autocomplete_panel(self) -> PromptAutocompletePanel | None:
        """Expose the live autocomplete panel for prompt-editor tests and wiring."""

        return self._autocomplete.panel

    @property
    def _segment_overlay(self) -> PromptReorderOverlayPort | None:
        """Expose the live segment reorder overlay for prompt-editor tests."""

        return self._interaction_controller.segment_overlay

    @property
    def _token_weight_control_overlay(self) -> PromptTokenWeightControls:
        """Expose the live token weight controls for prompt-editor tests."""

        return self._token_weight_controls

    def viewport(self) -> QWidget:
        """Return the projection viewport used by prompt-editor overlays and tests."""

        if hasattr(self, "_surface"):
            return self._surface.viewport()
        return super().viewport()

    def verticalScrollBar(self) -> QScrollBar:
        """Return the surface-owned scrollbar that owns prompt viewport state."""

        if hasattr(self, "_surface"):
            return self._surface.verticalScrollBar()
        return super().verticalScrollBar()

    def document(self):
        """Return the source-backed compatibility document used by geometry helpers."""

        if hasattr(self, "_surface"):
            return self._surface.document()
        return super().document()

    def lineHeight(self) -> int:  # noqa: N802
        """Return the live single-line text height used by the grow policy."""

        return self._sizing.line_height()

    def minimumEditorHeight(self) -> int:  # noqa: N802
        """Return the shell height for one visible line inside the QFluent host."""

        return self._sizing.minimum_editor_height()

    def manualScrollHeight(self) -> int | None:  # noqa: N802
        """Return the user-requested durable manual prompt height."""

        return self._sizing.manual_scroll_height()

    def setManualScrollHeight(self, height: int | None) -> None:  # noqa: N802
        """Apply a user-requested durable manual prompt height."""

        self._sizing.set_manual_scroll_height(height)

    def sizeHint(self) -> QSize:
        """Return a size hint whose height tracks the current fixed shell height."""

        return self._sizing.size_hint()

    def minimumSizeHint(self) -> QSize:
        """Return a minimum size hint whose height tracks the current shell height."""

        return self._sizing.minimum_size_hint()

    def toPlainText(self) -> str:
        """Return the raw prompt source text owned by the projection surface."""

        return self._surface.toPlainText()

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the full prompt source text without touching the host document."""

        self._command_adapter.set_plain_text(text)

    def setSourceText(self, text: str) -> None:  # noqa: N802
        """Replace the full prompt source text exactly."""

        self._command_adapter.set_source_text(text)

    def replaceBaselineText(self, text: str) -> None:  # noqa: N802
        """Replace restored prompt text and make it the editor undo baseline."""

        self._command_adapter.replace_baseline_text(text)

    def replaceBaselineSourceText(self, text: str) -> None:  # noqa: N802
        """Replace restored exact source text and make it the undo baseline."""

        self._command_adapter.replace_baseline_text(text, exact_source=True)

    def preloadVisibleLoraBanners(  # noqa: N802
        self,
        *,
        on_complete: Callable[[], None],
    ) -> bool:
        """Preload visible LoRA banner pixmaps without blocking the GUI thread."""

        return self._surface.preload_visible_lora_banners(on_complete=on_complete)

    def canUndo(self) -> bool:  # noqa: N802
        """Return whether the prompt editor has a custom undo transaction."""

        return self._surface.can_undo()

    def canRedo(self) -> bool:  # noqa: N802
        """Return whether the prompt editor has a custom redo transaction."""

        return self._surface.can_redo()

    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible prompt projection rects for source logical lines."""

        return self._surface.source_line_rects()

    def current_source_line_index(self) -> int:
        """Return the source logical line containing the current cursor."""

        return self._surface.current_source_line_index()

    def set_source_line_chrome_enabled(self, enabled: bool) -> None:
        """Toggle source logical line backgrounds inside the projection surface."""

        self._surface.set_source_line_chrome_enabled(enabled)

    def set_source_line_content_left_inset(self, inset: float) -> None:
        """Reserve left-side prompt viewport space for source line chrome."""

        self._surface.set_source_line_content_left_inset(inset)

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Render the supplied normalized scene keys as invalid scene titles."""

        self._surface.set_scene_error_keys(scene_error_keys)

    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Replace workflow scene titles offered by line-start autocomplete."""

        self._refresh_scene_context_identity()
        self._scene_feature_controller.set_scene_autocomplete_titles(titles)
        self._autocomplete.refresh_active_scene_session()

    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None:
        """Replace normalized scene keys that may be queued from this editor."""

        self._refresh_scene_context_identity()
        self._scene_feature_controller.set_queueable_scene_keys(scene_keys)

    def _refresh_scene_context_identity(self) -> None:
        """Publish current editor metadata identity to the scene feature owner."""

        metadata = self.property("input_metadata")
        if not isinstance(metadata, dict):
            self._scene_feature_controller.set_context_identity(
                cube_context_id=None,
                scene_context_id=None,
            )
            return
        cube_context_id = (
            metadata.get("cube_alias"),
            metadata.get("node_name"),
            metadata.get("key"),
        )
        self._scene_feature_controller.set_context_identity(
            cube_context_id=cube_context_id,
            scene_context_id=cube_context_id,
        )

    def textCursor(self):
        """Return the source-backed cursor wrapper used by controller seams."""

        return self._surface.textCursor()

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return the current source identity for prepared prompt commands."""

        return self._command_adapter.prompt_command_source_identity()

    def execute_autocomplete_acceptance(
        self,
        acceptance: PromptAutocompleteAcceptance,
    ) -> PromptCommandResult[object]:
        """Execute one prepared autocomplete acceptance on the projection surface."""

        return cast(
            PromptCommandResult[object],
            self._command_adapter.execute_autocomplete_acceptance(acceptance),
        )

    def execute_diagnostic_action(
        self,
        action: PromptDiagnosticAction,
    ) -> PromptDiagnosticCommandResult[object]:
        """Execute one prepared diagnostic action on the projection surface."""

        return cast(
            PromptDiagnosticCommandResult[object],
            self._command_adapter.execute_diagnostic_action(action),
        )

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute one prepared weight action on the projection surface."""

        return cast(
            PromptWeightCommandResult[object],
            self._command_adapter.execute_weight_action(
                request,
                mutation_service=mutation_service,
                syntax_service=syntax_service,
                syntax_profile=syntax_profile,
            ),
        )

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]:
        """Execute one prepared reorder commit on the projection surface."""

        return cast(
            PromptReorderCommandResult[object],
            self._command_adapter.execute_reorder_action(
                request,
                mutation_service=mutation_service,
                syntax_service=syntax_service,
                syntax_profile=syntax_profile,
            ),
        )

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
    ) -> PromptCommandResult[object]:
        """Execute one prepared source replacement on the projection surface."""

        return cast(
            PromptCommandResult[object],
            self._command_adapter.execute_source_replacement(
                replacement,
                command_name=command_name,
            ),
        )

    def setTextCursor(self, cursor) -> None:  # type: ignore[no-untyped-def]
        """Persist one source-backed cursor selection onto the projection surface."""

        self._surface.setTextCursor(cursor)

    def pulse_emphasis_feedback(
        self,
        *,
        outer_start: int,
        outer_end: int,
    ) -> None:
        """Delegate one transient emphasis-feedback pulse into the projection surface."""

        self._surface.pulse_emphasis_feedback(
            outer_start=outer_start,
            outer_end=outer_end,
        )

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Store one active emphasis-adjustment session on the projection surface."""

        self._surface.set_emphasis_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear any active emphasis-adjustment session from the surface."""

        self._surface.clear_emphasis_adjustment_session()

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when one exists."""

        return self._surface.emphasis_adjustment_session()

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range when present."""

        return self._surface.emphasis_adjustment_session_range()

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active emphasis-adjustment session owns one range."""

        return self._surface.emphasis_adjustment_session_matches_range(
            content_start=content_start,
            content_end=content_end,
        )

    def prompt_weight_wheel_identity(
        self,
        token: PromptProjectionToken,
    ) -> PromptWeightControlIdentity:
        """Return stable wheel ownership identity for one prompt weight token."""

        return self._surface.prompt_weight_wheel_identity(token)

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Project a temporary neutral emphasis shell over one plain content range."""

        self._surface.show_transient_neutral_emphasis(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear any temporary neutral emphasis shell from the projection surface."""

        self._surface.clear_transient_neutral_emphasis()

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Clear transient neutral emphasis only when overlay interaction owns it."""

        self._surface.clear_overlay_owned_transient_neutral_emphasis()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the content range currently owned by a temporary neutral shell."""

        return self._surface.transient_neutral_emphasis_range()

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the current transient neutral shell when present."""

        return self._surface.transient_neutral_emphasis_owner()

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at one projected emphasis-content boundary when possible."""

        return self._surface.set_emphasis_caret_to_content_boundary(
            content_start=content_start,
            content_end=content_end,
            prefer_end=prefer_end,
        )

    def cursorRect(self) -> QRect:  # noqa: N802
        """Return the viewport-local caret rect from the projection surface."""

        return self._surface.cursorRect()

    def has_pending_projection_update(self) -> bool:
        """Return whether projected presentation is waiting to catch up."""

        return self._surface.has_pending_projection_update()

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Synchronously apply pending projected presentation work."""

        self._surface.flush_pending_projection_update(reason=reason)

    def commit_lora_autocomplete_replacement(self) -> None:
        """Publish and collapse projection state after a LoRA autocomplete accept."""

        self._interaction_controller.flush_pending_semantic_refresh(
            reason="lora_autocomplete_accept"
        )
        self._surface.force_collapse_expanded_token()

    def set_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace the active projection-owned autocomplete preview state."""

        self._surface.set_autocomplete_preview_state(preview_state)

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        active_index: int | None,
        *,
        query_identity: Hashable | None = None,
    ) -> None:
        """Render one transient set of search matches on the projection surface."""

        self._search_feature_controller.set_search_matches(
            matches,
            active_index=active_index,
            query_identity=query_identity,
        )

    def clear_search_matches(self) -> None:
        """Clear any transient search highlight state from the prompt projection."""

        self._search_feature_controller.clear_search_matches()

    def displayMode(self) -> PromptProjectionDisplayMode:  # noqa: N802
        """Return the current visible prompt display mode."""

        return self._surface.display_mode()

    def setDisplayMode(self, display_mode: PromptProjectionDisplayMode) -> None:  # noqa: N802
        """Replace the visible prompt display mode without changing source text."""

        self._surface.set_display_mode(display_mode)
        self._interaction_controller.handle_cursor_position_changed()

    def richPromptRenderingEnabled(self) -> bool:  # noqa: N802
        """Return whether rich projected prompt rendering is enabled."""

        return self.displayMode() is PromptProjectionDisplayMode.PROJECTED

    def setRichPromptRenderingEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Toggle rich prompt rendering and exact source editing."""

        previous_enabled = self.richPromptRenderingEnabled()
        if enabled:
            self._surface.set_exact_source_editing_enabled(False)
            self.setDisplayMode(PromptProjectionDisplayMode.PROJECTED)
        else:
            self._surface.set_exact_source_editing_enabled(True)
            self.setDisplayMode(PromptProjectionDisplayMode.RAW)
        if previous_enabled != enabled:
            self.richPromptRenderingEnabledChanged.emit(enabled)

    def source_range_fragments(
        self,
        *,
        start: int,
        end: int,
    ):
        """Return the wrapped viewport fragments for one raw source range."""

        return self._surface.source_range_fragments(start=start, end=end)

    def set_reorder_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
    ) -> None:
        """Delegate explicit reorder preview ownership into the projection surface."""

        self._surface.set_reorder_preview_state(preview_state)

    def clear_reorder_preview_state(self) -> None:
        """Clear the active reorder preview state from the projection surface."""

        self._surface.clear_reorder_preview_state()

    def set_wheel_intent_token_handlers(
        self,
        *,
        token_pointer_moved: Callable[[PromptProjectionToken, QPointF], None] | None,
        token_wheel_ready: Callable[[PromptProjectionToken, QPointF], bool] | None,
        token_wheel_allowed: Callable[[PromptProjectionToken, QWheelEvent], bool]
        | None,
        token_wheel_activated: Callable[[PromptProjectionToken, QPointF], None] | None,
    ) -> None:
        """Set callbacks that gate weighted-token wheel adjustment."""

        self._wheel_controller.set_token_weight_handlers(
            token_pointer_moved=token_pointer_moved,
            token_wheel_ready=token_wheel_ready,
            token_wheel_allowed=token_wheel_allowed,
            token_wheel_activated=token_wheel_activated,
            token_range_changed=self._surface.set_wheel_intent_emphasis_accent_range,
        )

    def reorder_preview_fragments(
        self,
        *,
        start: int,
        end: int,
    ):
        """Return wrapped fragments for one active reorder preview source range."""

        return self._surface.reorder_preview_fragments(start=start, end=end)

    def reorder_live_chip_geometry_snapshot(
        self,
        *,
        layout_view,
        chip_rendered_ranges_by_index,
        chip_owned_ranges_by_index,
    ):
        """Return projection-owned live reorder chip geometry."""

        return self._surface.reorder_live_chip_geometry_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot,
        layout_view,
    ):
        """Return projection-owned preview reorder chip geometry."""

        return self._surface.reorder_preview_chip_geometry_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot,
        chip_owned_ranges_by_index,
    ):
        """Return projection-owned live paint snapshots for visible reorder chips."""

        return self._surface.reorder_live_chip_projection_paint_snapshots(
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot,
        chip_owned_ranges_by_index,
    ):
        """Return projection-owned preview paint snapshots for visible reorder chips."""

        return self._surface.reorder_preview_chip_projection_paint_snapshots(
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def set_reorder_overlay_suppressed_chip_indices(self, chip_indices):
        """Suppress document-painted chips currently rendered by reorder overlay."""

        self._surface.set_reorder_overlay_suppressed_chip_indices(chip_indices)

    def reorder_preview_cursor_rect(self, position: int):
        """Return the active reorder preview caret rect for one source position."""

        return self._surface.reorder_preview_cursor_rect(position)

    def reorder_base_drag_fragments(
        self,
        *,
        start: int,
        end: int,
    ):
        """Return wrapped fragments for one active base-drag preview source range."""

        return self._surface.reorder_base_drag_fragments(start=start, end=end)

    def reorder_base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot,
        layout_view,
    ):
        """Return projection-owned base-drag reorder chip geometry."""

        return self._surface.reorder_base_drag_chip_geometry_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_base_drag_cursor_rect(self, position: int):
        """Return the active base-drag caret rect for one source position."""

        return self._surface.reorder_base_drag_cursor_rect(position)

    def reorder_base_drag_placement_snapshot(
        self,
        *,
        snapshot,
        layout_view,
    ):
        """Return projection-owned base-drag placement geometry."""

        return self._surface.reorder_base_drag_placement_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reset_reorder_geometry_cache_counters(self):
        """Reset surface reorder cache counters for a new drag gesture."""

        self._surface.reset_reorder_geometry_cache_counters()

    def reorder_geometry_cache_counters(self):
        """Return surface reorder cache counters for gesture diagnostics."""

        return self._surface.reorder_geometry_cache_counters()

    def reorder_placement_at_rect(
        self,
        drag_rect,
        *,
        snapshot,
        active_placement_id,
    ):
        """Return the projection-owned placement selected by one drag rect."""

        return self._surface.reorder_placement_at_rect(
            drag_rect,
            snapshot=snapshot,
            active_placement_id=active_placement_id,
        )

    def active_syntax_span(self):
        """Return the syntax span currently owned by the surface caret model."""

        return self._surface.active_syntax_span()

    def cursorForPosition(self, position):  # type: ignore[no-untyped-def]
        """Return the cursor located at one viewport-local point."""

        return self._surface.cursorForPosition(position)

    def replace_document_text(self, text: str) -> None:
        """Replace the document text through one grouped edit."""

        self._command_adapter.replace_document_text(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace document text using a known semantic prompt snapshot."""

        self._command_adapter.replace_document_text_with_prompt_state(
            text,
            document_view=document_view,
            render_plan=render_plan,
        )

    def copy(self) -> None:
        """Copy the selected raw prompt source text."""

        self._clipboard_history_controller.copy()

    def selectAll(self) -> None:  # noqa: N802
        """Select the full raw prompt source text."""

        self._clipboard_history_controller.select_all()

    def cut(self) -> None:
        """Cut the selected raw prompt source text."""

        self._clipboard_history_controller.cut()

    def paste(self) -> None:
        """Paste clipboard text into the prompt source."""

        self._clipboard_history_controller.paste()

    def canInsertFromMimeData(self, source: QMimeData) -> bool:  # noqa: N802
        """Return whether external MIME data may become prompt source text."""

        return mime_data_has_prompt_plain_text(source)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """Insert prompt-safe MIME text through the source command boundary."""

        text = prompt_plain_text_from_mime_data(source)
        if text is None:
            return
        self._insert_dropped_prompt_text(text, viewport_position=None)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept only prompt-safe plain text drag payloads."""

        self._accept_or_ignore_prompt_mime_event(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep rejecting non-text drag payloads while the pointer moves."""

        self._accept_or_ignore_prompt_mime_event(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Insert prompt-safe dropped text and reject rich/file payloads."""

        text = prompt_plain_text_from_mime_data(event.mimeData())
        if text is None:
            event.ignore()
            return
        self._insert_dropped_prompt_text(
            text,
            viewport_position=self._viewport_position_for_host_drop(event),
        )
        event.acceptProposedAction()

    def _handle_clipboard_paste_completed(self, reason: str) -> None:
        """Refresh semantic prompt state after any clipboard paste entrypoint."""

        if not hasattr(self, "_interaction_controller"):
            return
        self._interaction_controller.flush_pending_semantic_refresh(reason=reason)

    def _accept_or_ignore_prompt_mime_event(
        self,
        event: QDragEnterEvent | QDragMoveEvent,
    ) -> None:
        """Accept one drag event only when it carries prompt-safe plain text."""

        if mime_data_has_prompt_plain_text(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def _insert_dropped_prompt_text(
        self,
        text: str,
        *,
        viewport_position: QPoint | None,
    ) -> None:
        """Replace the current source selection with externally dropped text."""

        if viewport_position is not None:
            self.setTextCursor(self.cursorForPosition(viewport_position))
        cursor = self.textCursor()
        self._command_adapter.execute_source_replacement(
            PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(
                    start=cursor.selectionStart(),
                    end=cursor.selectionEnd(),
                ),
                replacement_text=text,
                origin=PromptSourceEditOrigin.PASTE,
                exact_source=False,
                record_undo=True,
            ),
            command_name="drop_plain_text",
        )
        self._handle_clipboard_paste_completed("drop_plain_text")

    def _viewport_position_for_host_drop(self, event: QDropEvent) -> QPoint:
        """Return a host drop position in projection-viewport coordinates."""

        return self.viewport().mapFrom(self, event.position().toPoint())

    def undo(self) -> None:
        """Undo the previous prompt edit."""

        self._clipboard_history_controller.undo()

    def redo(self) -> None:
        """Redo the next prompt edit."""

        self._clipboard_history_controller.redo()

    def modify_emphasis(self, delta: float) -> None:
        """Adjust the emphasis weight around the current selection."""

        if not self._feature_profile_controller.emphasis_enabled:
            return
        self._interaction_controller.modify_emphasis(delta)

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        """Store placeholder text while keeping the host document visually empty."""

        self._qfluent_chrome.set_placeholder_text(text)

    def setReadOnly(self, read_only: bool) -> None:  # noqa: N802
        """Apply read-only state to both the QFluent shell and projection surface."""

        super().setReadOnly(read_only)
        if hasattr(self, "_surface"):
            self._surface.set_editing_enabled(not read_only)

    def placeholderText(self) -> str:  # noqa: N802
        """Return the configured placeholder text for the prompt editor shell."""

        return self._qfluent_chrome.placeholder_text()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Refresh dirty LoRA metadata when a visible editor gains focus."""

        super().focusInEvent(event)
        self._qfluent_chrome.handle_focus_in()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Clear autocomplete after focus leaves the editor interaction flow."""

        self._qfluent_chrome.finish_pending_focus_out_edit_block()
        super().focusOutEvent(event)
        self._qfluent_chrome.schedule_focus_out_cleanup()

    def changeEvent(self, event: QEvent) -> None:
        """Keep the projection surface aligned to host font and palette changes."""

        super().changeEvent(event)
        if not hasattr(self, "_surface"):
            return
        self._qfluent_chrome.handle_change_event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route viewport-owned geometry and context-menu events back to the host."""

        if not hasattr(self, "_surface"):
            return super().eventFilter(watched, event)
        if watched is self._surface:
            if event.type() == QEvent.Type.FocusIn:
                self._qfluent_chrome.handle_focus_in()
                return False
            if event.type() == QEvent.Type.FocusOut:
                self._qfluent_chrome.schedule_focus_out_cleanup()
                return False
            if event.type() == QEvent.Type.KeyPress:
                self._handle_prompt_key_press(cast(QKeyEvent, event))
                return True
            if event.type() == QEvent.Type.KeyRelease:
                self._handle_prompt_key_release(cast(QKeyEvent, event))
                return True
        shell_result = self._qfluent_chrome.handle_event_filter(watched, event)
        if shell_result is not None:
            return shell_result
        if watched is self._shell_viewport() or watched is self.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                mouse_event = cast(QMouseEvent, event)
                if mouse_event.button() == Qt.MouseButton.RightButton:
                    self._shell_context_menu.record_context_menu_press()
            if event.type() == QEvent.Type.ContextMenu:
                return self._shell_context_menu.forward_context_menu_event_to_host(
                    cast(QContextMenuEvent, event)
                )
        return super().eventFilter(watched, event)

    def hideEvent(self, event: QHideEvent) -> None:
        """Close autocomplete when the prompt editor itself is hidden."""

        self._qfluent_chrome.handle_hide()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh dirty LoRA metadata after a hidden editor becomes visible."""

        super().showEvent(event)
        self._qfluent_chrome.handle_show()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Route prompt-editor key handling through the interaction controller."""

        self._handle_prompt_key_press(event)

    def _handle_prompt_key_press(self, event: QKeyEvent) -> None:
        """Route one physical key press through prompt interaction ownership."""

        autocomplete_consumed = self._interaction_controller.handle_key_press(event)
        if autocomplete_consumed:
            return
        self._surface.keyPressEvent(event)
        if event.isAccepted():
            if _emphasis_shortcut_should_mute_autocomplete(event):
                self._interaction_controller.handle_emphasis_shortcut_accepted()
                return
            if _accepted_key_should_skip_autocomplete_post_refresh(event):
                self._interaction_controller.clear_autocomplete_for_non_text_key_from_keymap()
                return
            self._interaction_controller.handle_post_key_press(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Commit segment reorder mode when Alt is released."""

        self._handle_prompt_key_release(event)

    def _handle_prompt_key_release(self, event: QKeyEvent) -> None:
        """Route one physical key release through prompt interaction ownership."""

        if self._interaction_controller.handle_key_release(event):
            return
        self._surface.keyReleaseEvent(event)
        if event.isAccepted():
            return
        event.ignore()

    def setFocus(  # noqa: N802
        self,
        reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason,
    ) -> None:
        """Focus the projection surface while preserving the public editor facade."""

        if hasattr(self, "_surface"):
            self._surface.setFocus(reason)
            return
        super().setFocus(reason)

    def hasFocus(self) -> bool:  # noqa: N802
        """Return whether the public editor facade or projection surface has focus."""

        return super().hasFocus() or (
            hasattr(self, "_surface") and self._surface.hasFocus()
        )

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002
        """Keep Tab inside the prompt editor so autocomplete acceptance can own it."""

        return self._qfluent_chrome.focus_next_prev_child(next)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh manual layout and schedule shell geometry after resizing."""

        super().resizeEvent(event)
        self._qfluent_chrome.handle_resize()

    def moveEvent(self, event: QMoveEvent) -> None:
        """Reposition autocomplete surfaces when layouts move the prompt editor."""

        super().moveEvent(event)
        self._qfluent_chrome.handle_move()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Refresh autocomplete after caret movement caused by mouse interaction."""

        super().mouseReleaseEvent(event)
        self._interaction_controller.handle_mouse_release()

    def _handle_surface_text_changed(self) -> None:
        """Propagate surface text changes through the public prompt-editor signal."""

        self._qfluent_chrome.apply_placeholder_visibility()
        self._qfluent_chrome.update_fill_planes()
        self.textChanged.emit()

    def _allow_surface_wheel_scroll(self, event: QWheelEvent) -> bool:
        """Return whether the prompt surface may consume one wheel event."""

        return self._wheel_controller.allow_surface_wheel_scroll(event)

    def _handle_viewport_wheel_event(self, event: QWheelEvent) -> bool:
        """Route prompt viewport wheel input through the policy-aware owner."""

        return self._wheel_controller.handle_viewport_wheel_event(event)

    def prompt_surface_handle_wheel_scroll(
        self,
        event: QWheelEvent,
    ) -> PromptWheelScrollResult:
        """Route a wheel event to the projection surface scroll owner."""

        return self._surface.handle_prompt_wheel_scroll(event)

    def prompt_surface_wheel_event_is_allowed(self, event: QWheelEvent) -> bool:
        """Return whether the surface may consume one prompt wheel event."""

        return wheel_event_is_allowed(self, event)

    def forward_wheel_event_to_editor_panel(self, event: QWheelEvent) -> None:
        """Forward intentionally bubbled prompt wheel input to the editor panel."""

        self._forward_wheel_event_to_editor_panel(event)

    def _forward_wheel_event_to_editor_panel(self, event: QWheelEvent) -> None:
        """Forward intentionally bubbled prompt wheel input to the editor panel."""

        panel = self._ancestor_external_wheel_handler()
        if panel is None:
            event.ignore()
            return
        panel.handle_external_wheel(event)

    def _ancestor_external_wheel_handler(self) -> Any | None:
        """Return the nearest ancestor that owns editor-panel wheel scrolling."""

        current = self.parentWidget()
        while current is not None:
            handler = getattr(current, "handle_external_wheel", None)
            if callable(handler):
                return current
            current = current.parentWidget()
        return None

    def _handle_surface_syntax_action(self, action: object) -> None:
        """Delegate surface syntax actions to the interaction controller seam."""

        self._interaction_controller.apply_syntax_action(action)

    def _handle_surface_mouse_release(self) -> None:
        """Refresh autocomplete after surface-owned mouse interactions finish."""

        self._interaction_controller.handle_mouse_release()

    def _prompt_menu_requires_custom_actions(self) -> bool:
        """Return whether prompt-specific menu rows require the custom menu."""

        return True

    def has_lora_spans_for_metadata(self) -> bool:
        """Return whether the current semantic snapshot contains LoRA spans."""

        return self._interaction_controller.has_lora_spans()

    def refresh_lora_render_metadata_now(self, *, reason: str) -> bool:
        """Refresh catalog-backed LoRA render metadata through interactions."""

        return self._interaction_controller.refresh_lora_render_metadata(reason=reason)

    def _source_position_for_global_pos(self, global_pos: QPoint) -> int:
        """Return the prompt source position under one global menu point."""

        cursor = self.cursorForPosition(self.viewport().mapFromGlobal(global_pos))
        return int(cursor.position())

    def mark_lora_metadata_dirty(self) -> None:
        """Mark this editor's catalog-backed LoRA metadata as stale."""

        self._lora_metadata_feature_controller.mark_dirty()

    def refresh_lora_metadata_if_visible(self) -> bool:
        """Refresh dirty LoRA metadata when this editor is currently visible."""

        return self._lora_metadata_feature_controller.refresh_if_visible()

    def clear_lora_thumbnail_cache(self) -> None:
        """Discard decoded LoRA thumbnails after stored thumbnail assets change."""

        self._lora_thumbnail_cache.clear()
        self._surface.refresh_lora_thumbnail_paint(reason="lora_thumbnail_cache_clear")
        self.update()

    def refresh_prompt_segment_presets(self, *, reason: str) -> None:
        """Refresh saved prompt segments from prepared panel model context."""

        self._segment_preset_controller.refresh_menu_model(reason=reason)

    def _refresh_lora_render_metadata_after_catalog_update(self) -> bool:
        """Refresh inline LoRA render metadata after this editor updates catalog rows."""

        return self._lora_metadata_feature_controller.refresh_after_catalog_update()

    def _schedule_lora_metadata_catchup_if_needed(self) -> None:
        """Queue a lazy visible-editor metadata refresh when needed."""

        self._lora_metadata_feature_controller.schedule_catchup_if_needed()

    def _set_context_menu_insert_state_for_tests(
        self,
        *,
        insert_position: int | None,
        should_replace_selection: bool | None = None,
    ) -> None:
        """Set shell-owned context-menu insert state for compatibility tests."""

        self._shell_context_menu.set_context_insert_state(
            insert_position=insert_position,
            should_replace_selection=should_replace_selection,
        )

    def _set_context_menu_selection_state_for_tests(
        self,
        *,
        had_selection: bool | None,
        selection_snapshot: tuple[int, int, str] | None,
    ) -> None:
        """Set shell-owned context-menu selection state for compatibility tests."""

        selected_text = selection_snapshot[2] if selection_snapshot is not None else ""
        self._prompt_menu_presenter.prepare_prompt_menu_selection(
            selected_text=selected_text,
            selection_snapshot=selection_snapshot if had_selection else None,
            reason="test_context_menu_selection_state",
        )
        self._shell_context_menu.set_selection_press_state(
            had_selection=had_selection,
            selection_snapshot=selection_snapshot,
        )

    def _ancestor_editor_panel(self) -> QWidget | None:
        """Return the owning editor panel widget when this editor is panel-hosted."""

        parent = self.parentWidget()
        while parent is not None:
            if parent.__class__.__name__ == "EditorPanel":
                return parent
            parent = parent.parentWidget()
        return None

    def _shell_viewport(self) -> QWidget:
        """Return the real QFluent host viewport beneath the projection surface."""

        return super().viewport()

    def _content_viewport_for_chrome(self) -> QWidget | None:
        """Return the projection viewport after construction has created it."""

        if not hasattr(self, "_surface"):
            return None
        return self.viewport()

    def _apply_host_placeholder_for_chrome(self, text: str) -> None:
        """Apply visible placeholder text to QFluent without recursive dispatch."""

        QFluentTextEdit.setPlaceholderText(self, text)

    def _surface_for_chrome(self) -> PromptShellChromeSurface | None:
        """Return the projection surface for QFluent chrome synchronization."""

        surface = getattr(self, "_surface", None)
        return cast(PromptShellChromeSurface | None, surface)

    def _update_backing_fill_for_chrome(self, rect: QRect) -> None:
        """Repaint shell-owned fill layers for a dirty projection viewport rect."""

        if not (
            hasattr(self, "_surface")
            and hasattr(self, "_fill_plane")
            and hasattr(self, "_shell_padding_fill_plane")
        ):
            return
        self._shell.update_backing_fill(
            rect=rect,
            surface=self._surface,
            fill_plane=self._fill_plane,
            shell_padding_fill_plane=self._shell_padding_fill_plane,
        )

    def _handle_focus_out_for_chrome(self) -> None:
        """Forward deferred focus-out cleanup to the interaction owner."""

        self._interaction_controller.handle_focus_out()

    def _handle_hide_for_chrome(self) -> None:
        """Forward editor-hide cleanup to the interaction owner."""

        self._interaction_controller.handle_hide()

    def _handle_move_for_chrome(self) -> None:
        """Forward editor-move handling to the interaction owner."""

        self._interaction_controller.handle_move()

    def _host_scrollbar_for_scroll_delegate(self) -> QScrollBar:
        """Return QFluent's native host scrollbar for shell metric mirroring."""

        return QFluentTextEdit.verticalScrollBar(self)

    def _surface_for_scroll_delegate(self) -> PromptShellScrollSurface | None:
        """Return the projection surface once construction has created it."""

        surface = getattr(self, "_surface", None)
        return cast(PromptShellScrollSurface | None, surface)

    def _shell_padding_fill_plane_for_scroll_delegate(self) -> QWidget | None:
        """Return the shell padding fill plane once construction has created it."""

        fill_plane = getattr(self, "_shell_padding_fill_plane", None)
        return fill_plane if isinstance(fill_plane, QWidget) else None

    def _fill_plane_for_scroll_delegate(self) -> QWidget | None:
        """Return the viewport fill plane once construction has created it."""

        fill_plane = getattr(self, "_fill_plane", None)
        return fill_plane if isinstance(fill_plane, QWidget) else None

    def _token_weight_controls_for_scroll_delegate(self) -> QWidget | None:
        """Return overlay token controls once construction has created them."""

        controls = getattr(self, "_token_weight_controls", None)
        return controls if isinstance(controls, QWidget) else None

    def _handle_viewport_scroll_for_scroll_delegate(self) -> None:
        """Forward viewport scroll work to the interaction owner."""

        self._interaction_controller.handle_viewport_scroll()

    def _handle_resize_for_scroll_delegate(self) -> None:
        """Forward resize work to the interaction owner."""

        self._interaction_controller.handle_resize()

    def _surface_content_height_for_sizing(self) -> float:
        """Return the live projection content height for shell sizing."""

        return (
            float(self._surface.content_height()) if hasattr(self, "_surface") else 0.0
        )

    def _projection_line_height_for_sizing(self) -> float:
        """Return projection-owned text row height for shell sizing."""

        if not hasattr(self, "_surface"):
            return 1.0
        layout = getattr(self._surface, "_layout", None)
        metrics = getattr(layout, "metrics", None)
        line_height = getattr(metrics, "text_line_height", None)
        return float(line_height) if isinstance(line_height, int | float) else 1.0

    def _surface_is_alive_for_sizing(self) -> bool:
        """Return whether the projection surface can still serve sizing data."""

        return hasattr(self, "_surface") and qt_object_is_alive(self._surface)

    def _update_sizing_fill_planes(self) -> None:
        """Repaint shell fill planes after sizing changes."""

        if hasattr(self, "_shell_padding_fill_plane"):
            self._shell_padding_fill_plane.update()
        if hasattr(self, "_fill_plane"):
            self._fill_plane.update()

    def _resize_handle_for_sizing(self) -> QWidget | None:
        """Return the shell resize handle after construction has created it."""

        resize_handle = getattr(self, "_resize_handle", None)
        return resize_handle if isinstance(resize_handle, QWidget) else None


def _prompt_editor_key_category(event: QKeyEvent) -> str:
    """Return a compact diagnostic category for one prompt-editor key event."""

    key = event.key()
    if key in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
        return "backspace"
    if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
        return "enter"
    if key in {
        Qt.Key.Key_Left,
        Qt.Key.Key_Right,
        Qt.Key.Key_Up,
        Qt.Key.Key_Down,
        Qt.Key.Key_Home,
        Qt.Key.Key_End,
        Qt.Key.Key_PageUp,
        Qt.Key.Key_PageDown,
    }:
        return "line_navigation"
    text = event.text()
    if text in {"(", ")", "{", "}", "[", "]", "<", ">", ":", "\\", "*", ","}:
        return "syntax_sensitive"
    if len(text) == 1 and text.isprintable():
        return "plain_text"
    return "other"


def _emphasis_shortcut_should_mute_autocomplete(event: QKeyEvent) -> bool:
    """Return whether one accepted key event belongs to keyboard emphasis changes."""

    modifiers = event.modifiers()
    if not bool(modifiers & Qt.KeyboardModifier.ControlModifier):
        return False
    disallowed_modifiers = (
        Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    if bool(modifiers & disallowed_modifiers):
        return False
    return event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down}


def _accepted_key_should_skip_autocomplete_post_refresh(event: QKeyEvent) -> bool:
    """Return whether an accepted non-text key must not reopen autocomplete."""

    return event.key() in {Qt.Key.Key_Escape, Qt.Key.Key_Tab}


__all__ = ["PromptEditor"]
