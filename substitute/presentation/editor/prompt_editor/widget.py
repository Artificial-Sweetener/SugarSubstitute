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
from typing import cast

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
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
    QTextDocument,
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
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.conditioning import PromptConditioningContext
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
    PromptDocumentSemanticsController,
)
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.widgets.menu_model import MenuEntry
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.shared.logging.logger import get_logger

from .autocomplete_preview_state import PromptAutocompletePreviewState
from .composition import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorCompositionContext,
    PromptEditorConstructionInputs,
    PromptEditorConstructionObserver,
    PromptEditorCoreRuntimeBindings,
    PromptEditorFeatureRuntimeBindings,
    PromptEditorHostRuntimeBindings,
    PromptEditorProjectionCollaborators,
    PromptEditorTaskExecutorFactory,
    bind_prompt_editor_diagnostics_signals,
    build_prompt_editor_core_runtime,
    build_prompt_editor_feature_runtime,
    build_prompt_editor_host_runtime,
)
from .features import PromptSegmentPresetSource
from .interactions import PromptReorderOverlayPort
from .interactions.cursor_adapter import PromptCursorAdapter
from .overlays import (
    PromptAutocompletePanel,
    PromptTokenWeightControls,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from .geometry.models import PromptProjectionSourceLineRect
from .command_facade import PromptEditorCommandFacade
from .emphasis_facade import PromptEditorEmphasisFacade
from .host_adapter import PromptEditorHostAdapter
from .reorder_facade import PromptEditorReorderFacade
from .runtime_mount import PromptEditorRuntimeMount
from .shell import (
    PromptEditorShellRuntimeBindings,
    PromptEditorShellRuntimeMount,
    PromptFillPlane,
    PromptResizeHandle,
    build_prompt_editor_shell_runtime,
)

_LOGGER = get_logger("presentation.editor.prompt_editor")


class PromptEditor(
    PromptEditorCommandFacade,
    PromptEditorReorderFacade,
    PromptEditorEmphasisFacade,
    QFluentTextEdit,  # type: ignore[misc]
):
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
    regionHovered = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        prompt_document_semantics: PromptDocumentSemantics | None = None,
        prompt_conditioning_context: PromptConditioningContext | None = None,
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

        self._document_semantics = PromptDocumentSemanticsController(
            prompt_document_semantics or OrdinaryPromptDocumentSemantics()
        )
        construction_inputs = PromptEditorConstructionInputs(
            parent=parent,
            prompt_autocomplete_gateway=prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            prompt_document_semantics=self._document_semantics,
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
        maximum_visible_lines = construction_inputs.maximum_visible_lines
        prompt_lora_catalog_service = construction_inputs.prompt_lora_catalog_service
        prompt_spellcheck_service = construction_inputs.prompt_spellcheck_service

        construction_observer = PromptEditorConstructionObserver(_LOGGER)
        init_started_at = construction_observer.started_at()
        phase_started_at = construction_observer.started_at()
        super().__init__(parent)
        self._runtime = PromptEditorRuntimeMount()
        shell_viewport = super().viewport()
        host_adapter = PromptEditorHostAdapter(
            host=self,
            shell_viewport=shell_viewport,
            host_scrollbar=cast(
                QScrollBar,
                QFluentTextEdit.verticalScrollBar(self),
            ),
            runtime=self._runtime,
            apply_host_placeholder=(
                lambda text: QFluentTextEdit.setPlaceholderText(self, text)
            ),
            publish_text_changed=self.textChanged.emit,
        )
        shell_runtime = build_prompt_editor_shell_runtime(
            PromptEditorShellRuntimeMount(
                widget=self,
                chrome_host=self,
                scroll_host=self,
                sizing_host=self,
                shell_viewport=shell_viewport,
                maximum_visible_lines=maximum_visible_lines,
                resized=self.resized,
                manual_scroll_height_changed=self.manualScrollHeightChanged,
            ),
            PromptEditorShellRuntimeBindings(
                content_viewport=host_adapter.content_viewport,
                apply_host_placeholder=host_adapter.apply_host_placeholder,
                source_text=self.toPlainText,
                chrome_surface=host_adapter.chrome_surface,
                scroll_surface=host_adapter.scroll_surface,
                shell_padding_fill_plane=host_adapter.shell_padding_fill_plane,
                fill_plane=host_adapter.fill_plane,
                token_weight_controls=host_adapter.token_weight_controls,
                update_backing_fill=host_adapter.update_backing_fill,
                finish_pending_key_edit_block=(
                    host_adapter.finish_pending_key_edit_block
                ),
                schedule_lora_metadata_catchup=(
                    host_adapter.schedule_lora_metadata_catchup
                ),
                handle_focus_out=host_adapter.handle_focus_out,
                handle_hide=host_adapter.handle_hide,
                handle_move=host_adapter.handle_move,
                handle_viewport_wheel_event=host_adapter.handle_viewport_wheel_event,
                host_scrollbar=host_adapter.host_scrollbar,
                handle_viewport_scroll=host_adapter.handle_viewport_scroll,
                handle_resize=host_adapter.handle_resize,
                surface_content_height=host_adapter.surface_content_height,
                projection_line_height=host_adapter.projection_line_height,
                surface_is_alive=host_adapter.surface_is_alive,
                update_fill_planes=host_adapter.update_fill_planes,
                resize_handle=host_adapter.resize_handle,
                ancestor_external_wheel_handler=(
                    host_adapter.ancestor_external_wheel_handler
                ),
            ),
        )
        self._runtime.mount_shell(shell_runtime)
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(False)
        self.setCursorWidth(0)

        construction_observer.log_timing(
            "Initialized prompt editor host shell",
            started_at=phase_started_at,
            maximum_visible_lines=maximum_visible_lines,
            level="debug",
        )
        self.setAcceptDrops(True)
        composition_context = PromptEditorCompositionContext(
            editor=self,
            fill_plane_host=host_adapter,
            shell_viewport=shell_viewport,
            autocomplete_limit=self._AUTOCOMPLETE_LIMIT,
            autocomplete_minimum_prefix_length=self._AUTOCOMPLETE_MIN_PREFIX,
            fill_plane_factory=PromptFillPlane,
            resize_handle_factory=PromptResizeHandle,
        )
        core_runtime = build_prompt_editor_core_runtime(
            construction_inputs,
            composition_context,
            self._runtime.shell,
            PromptEditorCoreRuntimeBindings(
                mount_projection=self._runtime.mount_projection,
                context_insert_state=(
                    lambda: self._runtime.host.menu.shell.consume_context_insert_state()
                ),
                restore_focus=self.setFocus,
                complete_lora_autocomplete_replacement=(
                    self.commit_lora_autocomplete_replacement
                ),
                execute_autocomplete_acceptance=self.execute_autocomplete_acceptance,
                interaction_editor=self,
                weight_interaction_editor=self,
                wheel_surface_scroll_allowed=(
                    host_adapter.surface_wheel_event_is_allowed
                ),
                wheel_surface_scroll_handler=(host_adapter.handle_surface_wheel_scroll),
                wheel_to_editor_panel=(
                    host_adapter.forward_wheel_event_to_editor_panel
                ),
                publish_rich_rendering_changed=(
                    self.richPromptRenderingEnabledChanged.emit
                ),
                bind_diagnostics_signals=(
                    lambda controller: bind_prompt_editor_diagnostics_signals(
                        self,
                        controller,
                    )
                ),
            ),
            construction_observer,
            prompt_conditioning_context=prompt_conditioning_context,
        )
        self._runtime.mount_core(core_runtime)
        feature_runtime = build_prompt_editor_feature_runtime(
            construction_inputs,
            composition_context,
            core_runtime,
            PromptEditorFeatureRuntimeBindings(
                lora_metadata_identity=self,
                lora_trigger_word_host=self,
                is_visible=self.isVisible,
                update_host=self.update,
            ),
        )
        self._runtime.mount_features(feature_runtime)
        build_prompt_editor_host_runtime(
            construction_inputs,
            composition_context,
            self._runtime.shell,
            self._runtime.core,
            self._runtime.features,
            PromptEditorHostRuntimeBindings(
                signal_host=self,
                signal_callbacks=host_adapter,
                shell_viewport=shell_viewport,
                layout_host=self,
                mount_runtime=self._runtime.mount_host,
                queue_scene=self.sceneQueueRequested.emit,
                is_read_only=self.isReadOnly,
                rich_prompt_rendering_enabled=self.richPromptRenderingEnabled,
                toggle_rich_prompt_rendering=self.setRichPromptRenderingEnabled,
                has_text_selection=lambda: self.textCursor().hasSelection(),
                source_position_for_global_pos=self._source_position_for_global_pos,
                current_source_position=lambda: int(self.textCursor().position()),
                prompt_menu_requires_custom_actions=(
                    host_adapter.prompt_menu_requires_custom_actions
                ),
                show_native_context_menu=(
                    lambda event: QFluentTextEdit.contextMenuEvent(self, event)
                ),
                cursor_global_position=(
                    lambda: self.mapToGlobal(self.cursorRect().bottomLeft())
                ),
            ),
            construction_observer,
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
        return self._runtime.core.autocomplete.autocomplete.panel

    def _mounted_projection_or_none(self) -> PromptEditorProjectionCollaborators | None:
        """Return projection ownership when the staged runtime has published it."""

        runtime = getattr(self, "_runtime", None)
        if not isinstance(runtime, PromptEditorRuntimeMount):
            return None
        return runtime.projection_or_none

    @property
    def _segment_overlay(self) -> PromptReorderOverlayPort | None:
        """Expose the live segment reorder overlay for prompt-editor tests."""
        return self._runtime.core.syntax.interaction_controller.segment_overlay

    @property
    def _token_weight_control_overlay(self) -> PromptTokenWeightControls:
        """Expose the live token weight controls for prompt-editor tests."""
        return self._runtime.core.syntax.token_weight_controls

    def viewport(self) -> QWidget:
        """Return the projection viewport used by prompt-editor overlays and tests."""

        projection = self._mounted_projection_or_none()
        if projection is not None:
            return projection.surface.viewport()
        return cast(QWidget, super().viewport())

    def verticalScrollBar(self) -> QScrollBar:
        """Return the surface-owned scrollbar that owns prompt viewport state."""

        projection = self._mounted_projection_or_none()
        if projection is not None:
            return projection.surface.verticalScrollBar()
        return cast(QScrollBar, super().verticalScrollBar())

    def document(self) -> QTextDocument:
        """Return the source-backed compatibility document used by geometry helpers."""

        projection = self._mounted_projection_or_none()
        if projection is not None:
            return projection.surface.document()
        return cast(QTextDocument, super().document())

    def lineHeight(self) -> int:  # noqa: N802
        """Return the live single-line text height used by the grow policy."""
        return self._runtime.shell.sizing.line_height()

    def minimumEditorHeight(self) -> int:  # noqa: N802
        """Return the shell height for one visible line inside the QFluent host."""
        return self._runtime.shell.sizing.minimum_editor_height()

    def manualScrollHeight(self) -> int | None:  # noqa: N802
        """Return the user-requested durable manual prompt height."""
        return self._runtime.shell.sizing.manual_scroll_height()

    def setManualScrollHeight(self, height: int | None) -> None:  # noqa: N802
        """Apply a user-requested durable manual prompt height."""
        self._runtime.shell.sizing.set_manual_scroll_height(height)

    def sizeHint(self) -> QSize:
        """Return a size hint whose height tracks the current fixed shell height."""
        return self._runtime.shell.sizing.size_hint()

    def minimumSizeHint(self) -> QSize:
        """Return a minimum size hint whose height tracks the current shell height."""

        return self._runtime.shell.sizing.minimum_size_hint()

    def toPlainText(self) -> str:
        """Return the raw prompt source text owned by the projection surface."""

        return self._runtime.projection.surface.toPlainText()

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the full prompt source text without touching the host document."""

        self._runtime.features.document.set_plain_text(text)

    def setSourceText(self, text: str) -> None:  # noqa: N802
        """Replace the full prompt source text exactly."""

        self._runtime.features.document.set_source_text(text)

    def replaceBaselineText(self, text: str) -> None:  # noqa: N802
        """Replace restored prompt text and make it the editor undo baseline."""

        self._runtime.features.document.replace_baseline_text(text)

    def replaceBaselineSourceText(self, text: str) -> None:  # noqa: N802
        """Replace restored exact source text and make it the undo baseline."""

        self._runtime.features.document.replace_baseline_text(text, exact_source=True)

    def replaceBaselineSourceDocument(  # noqa: N802
        self,
        text: str,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Atomically replace document semantics, exact source, and undo baseline."""

        self._runtime.features.document.replace_baseline_document(
            text,
            document_semantics,
        )

    def replaceConditioningContext(  # noqa: N802
        self,
        conditioning_context: PromptConditioningContext,
    ) -> bool:
        """Replace graph-derived conditioning semantics and invalidate old diagnostics."""

        return self._runtime.features.document.replace_conditioning_context(
            conditioning_context
        )

    def preloadVisibleLoraBanners(  # noqa: N802
        self,
        *,
        on_complete: Callable[[], None],
    ) -> bool:
        """Preload visible LoRA banner pixmaps without blocking the GUI thread."""

        return self._runtime.projection.surface.preload_visible_lora_banners(
            on_complete=on_complete
        )

    def canUndo(self) -> bool:  # noqa: N802
        """Return whether the prompt editor has a custom undo transaction."""

        return self._runtime.projection.surface.history.can_undo()

    def canRedo(self) -> bool:  # noqa: N802
        """Return whether the prompt editor has a custom redo transaction."""

        return self._runtime.projection.surface.history.can_redo()

    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible prompt projection rects for source logical lines."""

        return self._runtime.projection.surface.source_line_rects()

    def current_source_line_index(self) -> int:
        """Return the source logical line containing the current cursor."""

        return self._runtime.projection.surface.current_source_line_index()

    def set_source_line_chrome_enabled(self, enabled: bool) -> None:
        """Toggle source logical line backgrounds inside the projection surface."""

        self._runtime.projection.surface.set_source_line_chrome_enabled(enabled)

    def set_source_line_content_left_inset(self, inset: float) -> None:
        """Reserve left-side prompt viewport space for source line chrome."""

        self._runtime.projection.surface.set_source_line_content_left_inset(inset)

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Render the supplied normalized scene keys as invalid scene titles."""

        self._runtime.projection.surface.set_scene_error_keys(scene_error_keys)

    def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
        """Replace workflow scene titles offered by line-start autocomplete."""

        self._runtime.core.scene.set_autocomplete_titles(titles)

    def set_queueable_scene_keys(self, scene_keys: frozenset[str]) -> None:
        """Replace normalized scene keys that may be queued from this editor."""

        self._runtime.core.scene.set_queueable_keys(scene_keys)

    def textCursor(self) -> PromptCursorAdapter:
        """Return the source-backed cursor wrapper used by controller seams."""

        return self._runtime.projection.surface.textCursor()

    def setTextCursor(self, cursor: object) -> None:  # noqa: N802
        """Persist one source-backed cursor selection onto the projection surface."""

        self._runtime.projection.surface.setTextCursor(cursor)

    def cursorRect(self) -> QRect:  # noqa: N802
        """Return the viewport-local caret rect from the projection surface."""

        return self._runtime.projection.surface.cursorRect()

    def has_pending_projection_update(self) -> bool:
        """Return whether projected presentation is waiting to catch up."""

        return self._runtime.projection.surface.has_pending_projection_update()

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Synchronously apply pending projected presentation work."""

        self._runtime.projection.surface.flush_pending_projection_update(reason=reason)

    def commit_lora_autocomplete_replacement(self) -> None:
        """Publish and collapse projection state after a LoRA autocomplete accept."""

        self._runtime.core.syntax.interaction_controller.flush_pending_semantic_refresh(
            reason="lora_autocomplete_accept"
        )
        self._runtime.projection.surface.force_collapse_expanded_token()

    def set_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace the active projection-owned autocomplete preview state."""

        self._runtime.projection.surface.autocomplete_preview.set_preview_state(
            preview_state
        )

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        active_index: int | None,
        *,
        query_identity: Hashable | None = None,
    ) -> None:
        """Render one transient set of search matches on the projection surface."""

        self._runtime.core.services.search_feature_controller.set_search_matches(
            matches,
            active_index=active_index,
            query_identity=query_identity,
        )

    def clear_search_matches(self) -> None:
        """Clear any transient search highlight state from the prompt projection."""

        self._runtime.core.services.search_feature_controller.clear_search_matches()

    def displayMode(self) -> PromptProjectionDisplayMode:  # noqa: N802
        """Return the current visible prompt display mode."""

        return self._runtime.core.rendering.display_mode

    def setDisplayMode(self, display_mode: PromptProjectionDisplayMode) -> None:  # noqa: N802
        """Replace the visible prompt display mode without changing source text."""

        self._runtime.core.rendering.set_display_mode(display_mode)

    def richPromptRenderingEnabled(self) -> bool:  # noqa: N802
        """Return whether rich projected prompt rendering is enabled."""

        return self._runtime.core.rendering.rich_rendering_enabled

    def field_action_entries(
        self,
        context: FieldActionContext,
    ) -> tuple[MenuEntry, ...]:
        """Return prompt-domain actions for the aggregate node menu."""

        return self._runtime.host.menu.shell.field_action_entries(context)

    def field_actions_available(self) -> bool:
        """Return whether this prompt field contributes node-menu actions."""

        return True

    def setRichPromptRenderingEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Toggle rich prompt rendering and exact source editing."""

        self._runtime.core.rendering.set_rich_rendering_enabled(enabled)

    def source_range_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return the wrapped viewport fragments for one raw source range."""

        return self._runtime.projection.surface.source_range_fragments(
            start=start,
            end=end,
        )

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

        self._runtime.core.syntax.wheel_controller.set_token_weight_handlers(
            token_pointer_moved=token_pointer_moved,
            token_wheel_ready=token_wheel_ready,
            token_wheel_allowed=token_wheel_allowed,
            token_wheel_activated=token_wheel_activated,
            token_range_changed=(
                self._runtime.projection.surface.emphasis.set_wheel_intent_accent_range
            ),
        )

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the syntax span currently owned by the surface caret model."""
        return self._runtime.projection.surface.active_syntax_span()

    def cursorForPosition(self, position: QPoint) -> PromptCursorAdapter:  # noqa: N802
        """Return the cursor located at one viewport-local point."""

        return self._runtime.projection.surface.cursorForPosition(position)

    def replace_document_text(self, text: str) -> None:
        """Replace the document text through one grouped edit."""

        self._runtime.features.document.replace_document_text(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace document text using a known semantic prompt snapshot."""

        self._runtime.features.document.replace_document_text_with_prompt_state(
            text,
            document_view=document_view,
            render_plan=render_plan,
        )

    def copy(self) -> None:
        """Copy the selected raw prompt source text."""

        self._runtime.projection.clipboard_history_controller.copy()

    def selectAll(self) -> None:  # noqa: N802
        """Select the full raw prompt source text."""

        self._runtime.projection.clipboard_history_controller.select_all()

    def cut(self) -> None:
        """Cut the selected raw prompt source text."""

        self._runtime.projection.clipboard_history_controller.cut()

    def paste(self) -> None:
        """Paste clipboard text into the prompt source."""

        self._runtime.projection.clipboard_history_controller.paste()

    def canInsertFromMimeData(self, source: QMimeData) -> bool:  # noqa: N802
        """Return whether external MIME data may become prompt source text."""

        return self._runtime.core.external_input.can_insert(source)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """Insert prompt-safe MIME text through the source command boundary."""

        self._runtime.core.external_input.insert(source)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept only prompt-safe plain text drag payloads."""

        self._runtime.core.external_input.accept_or_ignore_drag(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep rejecting non-text drag payloads while the pointer moves."""

        self._runtime.core.external_input.accept_or_ignore_drag(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Insert prompt-safe dropped text and reject rich/file payloads."""

        self._runtime.core.external_input.drop(event)

    def undo(self) -> None:
        """Undo the previous prompt edit."""

        self._runtime.projection.clipboard_history_controller.undo()

    def redo(self) -> None:
        """Redo the next prompt edit."""

        self._runtime.projection.clipboard_history_controller.redo()

    def modify_emphasis(self, delta: float) -> None:
        """Adjust the emphasis weight around the current selection."""

        if not self._runtime.core.services.feature_profile_controller.emphasis_enabled:
            return
        self._runtime.core.syntax.weight_interaction.modify_emphasis(delta)

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        """Store placeholder text while keeping the host document visually empty."""

        self._runtime.shell.chrome.set_placeholder_text(text)

    def setReadOnly(self, read_only: bool) -> None:  # noqa: N802
        """Apply read-only state to both the QFluent shell and projection surface."""

        super().setReadOnly(read_only)
        projection = self._mounted_projection_or_none()
        if projection is not None:
            projection.surface.set_editing_enabled(not read_only)

    def placeholderText(self) -> str:  # noqa: N802
        """Return the configured placeholder text for the prompt editor shell."""

        return self._runtime.shell.chrome.placeholder_text()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Refresh dirty LoRA metadata when a visible editor gains focus."""

        super().focusInEvent(event)
        self._runtime.shell.chrome.handle_focus_in()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Clear autocomplete after focus leaves the editor interaction flow."""

        self._runtime.shell.chrome.finish_pending_focus_out_edit_block()
        super().focusOutEvent(event)
        self._runtime.shell.chrome.schedule_focus_out_cleanup(event.reason())

    def changeEvent(self, event: QEvent) -> None:
        """Keep the projection surface aligned to host font and palette changes."""

        super().changeEvent(event)
        if self._mounted_projection_or_none() is None:
            return
        self._runtime.shell.chrome.handle_change_event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route viewport-owned geometry and context-menu events back to the host."""

        if self._mounted_projection_or_none() is None:
            return bool(super().eventFilter(watched, event))
        routed = self._runtime.host.events.route(watched, event)
        if routed is not None:
            return routed
        return bool(super().eventFilter(watched, event))

    def hideEvent(self, event: QHideEvent) -> None:
        """Close autocomplete when the prompt editor itself is hidden."""

        self._runtime.shell.chrome.handle_hide()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh dirty LoRA metadata after a hidden editor becomes visible."""

        super().showEvent(event)
        self._runtime.shell.chrome.handle_show()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Route prompt-editor key handling through the interaction controller."""

        self._handle_prompt_key_press(event)

    def _handle_prompt_key_press(self, event: QKeyEvent) -> None:
        """Route one physical key press through prompt interaction ownership."""

        self._runtime.core.key_router.handle_key_press(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Commit segment reorder mode when Alt is released."""

        self._handle_prompt_key_release(event)

    def _handle_prompt_key_release(self, event: QKeyEvent) -> None:
        """Route one physical key release through prompt interaction ownership."""

        self._runtime.core.key_router.handle_key_release(event)

    def setFocus(  # noqa: N802
        self,
        reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason,
    ) -> None:
        """Focus the projection surface while preserving the public editor facade."""

        projection = self._mounted_projection_or_none()
        if projection is not None:
            projection.surface.setFocus(reason)
            return
        super().setFocus(reason)

    def hasFocus(self) -> bool:  # noqa: N802
        """Return whether the public editor facade or projection surface has focus."""

        projection = self._mounted_projection_or_none()
        return super().hasFocus() or (
            projection is not None and projection.surface.hasFocus()
        )

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002
        """Keep Tab inside the prompt editor so autocomplete acceptance can own it."""

        return self._runtime.shell.chrome.focus_next_prev_child(next)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Refresh manual layout and schedule shell geometry after resizing."""

        super().resizeEvent(event)
        self._runtime.shell.chrome.handle_resize()

    def moveEvent(self, event: QMoveEvent) -> None:
        """Reposition autocomplete surfaces when layouts move the prompt editor."""

        super().moveEvent(event)
        self._runtime.shell.chrome.handle_move()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Refresh autocomplete after caret movement caused by mouse interaction."""

        super().mouseReleaseEvent(event)
        self._runtime.core.syntax.interaction_controller.handle_mouse_release()

    def _source_position_for_global_pos(self, global_pos: QPoint) -> int:
        """Return the prompt source position under one global menu point."""

        cursor = self.cursorForPosition(self.viewport().mapFromGlobal(global_pos))
        return int(cursor.position())

    def mark_lora_metadata_dirty(self) -> None:
        """Mark this editor's catalog-backed LoRA metadata as stale."""

        self._runtime.features.catalog_refresh.mark_lora_metadata_dirty()

    def refresh_lora_metadata_if_visible(self) -> bool:
        """Refresh dirty LoRA metadata when this editor is currently visible."""

        return self._runtime.features.catalog_refresh.refresh_lora_metadata_if_visible()

    def clear_lora_thumbnail_cache(self) -> None:
        """Discard decoded LoRA thumbnails after stored thumbnail assets change."""

        self._runtime.features.catalog_refresh.clear_lora_thumbnail_cache()

    def refresh_prompt_segment_presets(self, *, reason: str) -> None:
        """Refresh saved prompt segments from prepared panel model context."""

        self._runtime.features.catalog_refresh.refresh_prompt_segment_presets(
            reason=reason
        )

    def _set_context_menu_insert_state_for_tests(
        self,
        *,
        insert_position: int | None,
        should_replace_selection: bool | None = None,
    ) -> None:
        """Set shell-owned context-menu insert state for compatibility tests."""

        self._runtime.host.menu.shell.set_context_insert_state(
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
        self._runtime.host.menu.prompt_requests.prepare_prompt_menu_selection(
            selected_text=selected_text,
            selection_snapshot=selection_snapshot if had_selection else None,
            reason="test_context_menu_selection_state",
        )
        self._runtime.host.menu.shell.set_selection_press_state(
            had_selection=had_selection,
            selection_snapshot=selection_snapshot,
        )


__all__ = ["PromptEditor"]
