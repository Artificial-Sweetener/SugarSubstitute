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

"""Provide the custom token-aware editing surface used by the rebuilt prompt editor."""

from __future__ import annotations

from .exact_weight_editor import PromptExactWeightEditor, PromptExactWeightEditorHost

from typing import Callable, cast

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFocusEvent,
    QHideEvent,
    QInputMethodEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
    QTextCursor,
    QTextDocument,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QScrollBar,
    QWidget,
)

from substitute.application.prompt_editor.document.semantics import (
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSyntaxAction,
)
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
)

from ..commands.execution import PromptEditExecution
from ..commands.source_service import PromptSourceCommandService
from ..core.state.semantic_state import PromptEditorSemanticSnapshot
from ..debug_probe import (
    log_prompt_editor_probe,
    prompt_editor_probe_enabled,
    surface_probe_state,
)
from ..core.editing.commit import PromptEditCommit
from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_buffer import PromptSourceSnapshot
from ..core.editing.source_commands import PromptSourceEditOrigin
from ..interactions.cursor_adapter import (
    PromptCursorAdapter,
)
from ..interactions.pointer_ports import PromptSurfacePointerInteractions
from ..interactions.text_mutation_controller import (
    PromptProjectionTextMutationContext,
)
from ..interactions import (
    PromptExternalTextInputOwner,
    PromptSurfaceKeyHandler,
    PromptSurfaceKeyHost,
    PromptSurfaceMouseHandler,
    PromptSurfaceMouseHost,
    PromptSurfaceWheelHandler,
    PromptSurfaceWheelHost,
    PromptWheelScrollResult,
    prompt_word_bounds,
)
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..qt_lifecycle import qt_object_is_alive
from .applicator import PromptProjectionApplicator, PromptProjectionRebuildResult
from .autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionOwner,
)
from .caret_movement_controller import (
    PromptProjectionCaretMovementController,
    PromptProjectionCaretMovementHost,
)
from .caret_state_owner import PromptProjectionCaretStateOwner
from .caret_visual import (
    PromptSurfaceCaretVisualController,
    PromptSurfaceCaretVisualHost,
)
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .display_mode_layout_cache import (
    PromptProjectionDisplayModeLayoutCache,
    PromptProjectionDisplayModeLayoutIdentity,
)
from .emphasis_projection_owner import PromptProjectionEmphasisOwner
from .editing_runtime import PromptProjectionEditingRuntimeFactory
from .fill_band_cache import (
    PromptFillBandRect,
)
from .fill_band_owner import PromptProjectionFillBandOwner
from .frame_state import (
    PromptProjectionEditorState,
    PromptProjectionFrameStatePublisher,
    PromptProjectionLayoutWidthResolver,
    build_initial_prompt_projection_state,
)
from .focus_owner import PromptProjectionFocusOwner
from .frame_synchronizer import PromptProjectionFrameSynchronizer
from .freshness_controller import (
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .geometry_reuse_warmer import PromptProjectionGeometryReuseWarmer
from .history_owner import PromptProjectionHistoryOwner
from .input_method_controller import (
    PromptInputMethodController,
    PromptInputMethodHost,
)
from ..layout.contracts import PromptLayoutDamage
from .edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from .lora_surface_features import (
    PromptSurfaceLoraFeatureDelegate,
    PromptSurfaceLoraFeatureHost,
    PromptSurfaceLoraThumbnailPreloader,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionInlinePreview,
    PromptProjectionTransientState,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from .observability import (
    log_projection_timing,
    projection_observability_started_at,
    render_plan_lora_span_count,
)
from .content_media_owner import PromptProjectionContentMediaOwner
from .region_chrome_presentation import PromptRegionChromePresentationOwner
from .region_chrome_state import PromptRegionChromeEditTarget
from .reorder_geometry import reorder_geometry_state
from .reorder_projection_owner import PromptReorderProjectionOwner
from .render_compositor import PromptProjectionRenderCompositor
from .render_frame_owner import PromptProjectionRenderFrameOwner
from .render_publication_owner import PromptProjectionRenderPublicationOwner
from ..geometry.models import PromptProjectionSourceLineRect
from ..geometry.selection import selection_paints_changed
from .session import PromptProjectionSession
from .source_line_chrome import PromptSourceLineChrome
from .search_highlight_owner import PromptSearchHighlightLayerOwner
from .refresh_geometry_signature import PromptRefreshGeometryPaintSignature
from .content_selection_owner import PromptProjectionSelectionLayerOwner
from .source_state_wiring import (
    PromptProjectionSourceStateBindings,
    build_prompt_projection_source_state_owners,
)
from .theme import qcolor_from_rgb, semantic_palette_from_theme
from substitute.presentation.editor.prompt_editor.projection.emphasis_renderer import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.lora_renderer import (
    PromptLoraInlineObjectRenderer,
)
from substitute.presentation.editor.prompt_editor.projection.inline_renderer_registry import (
    PromptProjectionInlineObjectRendererRegistry,
)
from substitute.presentation.editor.prompt_editor.projection.wildcard_renderer import (
    PromptWildcardInlineObjectRenderer,
)
from .undo_payload import PromptProjectionUndoPayload
from .viewport_event_router import PromptProjectionViewportEventRouter
from ..interactions.deletion_controller import (
    PromptDeletionContext,
    PromptDeletionContextProvider,
    PromptDeletionProjectionEffects,
    PromptSurfaceDeletionController,
)
from .builder import PromptProjectionBuilder

_LOGGER = get_logger("presentation.editor.prompt_editor.projection_surface")


class PromptProjectionSurface(QAbstractScrollArea):
    """Own prompt projection editing inside a host-provided shell and scrollbar."""

    _viewport_event_router: PromptProjectionViewportEventRouter | None = None

    textChanged = Signal()
    cursorPositionChanged = Signal()
    contentHeightChanged = Signal(float)
    undoAvailableChanged = Signal(bool)
    redoAvailableChanged = Signal(bool)
    emphasisShortcutTriggered = Signal(float)
    syntaxActionTriggered = Signal(object)
    mouseInteractionFinished = Signal()
    loraContextMenuRequested = Signal(object, QPoint)
    backingFillInvalidated = Signal(QRect)
    implicitParenthesisAuthored = Signal(int)

    def notify_implicit_parenthesis_authored(self, nesting_depth: int) -> None:
        """Publish nested implicit syntax without owning education behavior."""

        self.implicitParenthesisAuthored.emit(nesting_depth)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        editing_session: PromptEditingSession[PromptProjectionUndoPayload],
        editing_runtime_factory: PromptProjectionEditingRuntimeFactory[
            "PromptProjectionSurface",
            PromptProjectionUndoPayload,
        ],
        document_semantics: PromptDocumentSemantics | None = None,
        lora_thumbnail_cache: PromptLoraThumbnailCache | None = None,
        lora_thumbnail_preloader: PromptSurfaceLoraThumbnailPreloader | None = None,
    ) -> None:
        """Initialize the custom prompt editing surface."""

        super().__init__(parent)
        self._editing_session = editing_session
        self._projection_applicator = PromptProjectionApplicator(
            PromptProjectionBuilder(document_semantics=document_semantics)
        )
        thumbnail_cache = lora_thumbnail_cache or PromptLoraThumbnailCache()
        self._session = PromptProjectionSession()
        self.exact_weight_editor = PromptExactWeightEditor(
            cast(PromptExactWeightEditorHost, self)
        )
        self._display_mode = PromptProjectionDisplayMode.PROJECTED
        self._exact_source_editing_enabled = False
        self._layout = PromptLayoutEditToFrameCoordinator(
            PromptProjectionInlineObjectRendererRegistry(
                (
                    PromptEmphasisPrefixRenderer(),
                    PromptEmphasisSuffixRenderer(),
                    PromptLoraInlineObjectRenderer(thumbnail_cache),
                    PromptWildcardInlineObjectRenderer(),
                )
            )
        )
        self._content_media_owner = PromptProjectionContentMediaOwner()
        self._display_mode_layout_cache = PromptProjectionDisplayModeLayoutCache()
        self._lora_feature_delegate = PromptSurfaceLoraFeatureDelegate(
            cast(PromptSurfaceLoraFeatureHost, self),
            thumbnail_cache=thumbnail_cache,
            thumbnail_preloader=lora_thumbnail_preloader,
            publish_thumbnail_media=self._publish_lora_thumbnail_media,
            publish_context_menu=(
                lambda token, global_pos: self.loraContextMenuRequested.emit(
                    token,
                    global_pos,
                )
            ),
        )
        update_lora_thumbnail = self._lora_feature_delegate.update_lora_thumbnail_pixmap
        thumbnail_cache.pixmap_ready.connect(
            lambda key: update_lora_thumbnail(self._layout.frame.geometry, key)
        )
        self._scene_error_keys: frozenset[str] = frozenset()
        self._editor_state = build_initial_prompt_projection_state(
            source=self._editing_session.source_snapshot(),
            applicator=self._projection_applicator,
            document_semantics=document_semantics,
            display_mode=self._display_mode,
            session=self._session,
            scene_error_keys=self._scene_error_keys,
        )
        self._frame_state = PromptProjectionFrameStatePublisher(self._editor_state)
        self._source_line_chrome = PromptSourceLineChrome()
        self._search_highlight_layer = PromptSearchHighlightLayerOwner()
        self._diagnostic_layer_owner = PromptDiagnosticLayerOwner(
            parent=self,
            diagnostics=lambda: self._session.diagnostics,
            replace_diagnostics=self._session.set_diagnostics,
            clear_diagnostics=self._session.clear_diagnostics,
            selection=self._selection,
            geometry=lambda: self._layout.frame.geometry,
            layout_identity=lambda: self._frame_state.current_layout_identity(
                self._layout.frame.output
            ),
            viewport_rect=lambda: QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset,
            color_rgba=lambda: int(
                qcolor_from_rgb(semantic_palette_from_theme().error_foreground).rgba()
            ),
            device_pixel_ratio=lambda: float(self.viewport().devicePixelRatioF()),
            is_alive=lambda: qt_object_is_alive(self),
            request_update=self._diagnostic_layer_published,
        )
        self._projection_freshness_controller: PromptProjectionFreshnessController
        self._autocomplete_preview_projection_owner = PromptAutocompletePreviewProjectionOwner(
            session=self._session,
            flush_pending_projection=(
                lambda: self._flush_pending_projection_update(
                    reason="autocomplete_preview"
                )
            ),
            base_projection_is_stale=(
                lambda: (
                    self._projection_freshness_controller.has_stale_projection_geometry()
                )
            ),
            rebuild_base_projection=self._rebuild_projection,
            rebuild_active_projection=self._rebuild_active_projection,
            request_repaint=self.viewport().update,
            surface_state=lambda: surface_probe_state(self),
        )
        self._focus_owner = PromptProjectionFocusOwner(
            surface=self,
            prepare_source_line_chrome=self._prepare_source_line_chrome_layer,
            schedule_caret_blink=(
                lambda reset_cycle: self._schedule_caret_blink_sync(
                    reset_cycle=reset_cycle
                )
            ),
            parent=self,
        )
        self._mouse_handler = PromptSurfaceMouseHandler(
            cast(PromptSurfaceMouseHost, self),
            ensure_pointer_focus=self._focus_owner.ensure_pointer_focus,
            clear_autocomplete_preview=(
                self._autocomplete_preview_projection_owner.clear_preview_state
            ),
            request_lora_context_menu=(
                self._lora_feature_delegate.request_context_menu
            ),
        )
        self._external_text_input = PromptExternalTextInputOwner(
            self._insert_external_mime_text
        )
        self._geometry_reuse_warmer = PromptProjectionGeometryReuseWarmer(
            is_available=lambda: qt_object_is_alive(self),
            is_projected=(
                lambda: self._display_mode is PromptProjectionDisplayMode.PROJECTED
            ),
            prewarm=(
                lambda: (
                    self._layout.frame.output.snapshot.prewarm_inline_object_fragment_index()
                )
            ),
            parent=self,
        )
        source_state_owners = build_prompt_projection_source_state_owners(
            PromptProjectionSourceStateBindings(
                applicator=self._projection_applicator,
                editor_state=self._editor_state,
                layout=self._layout,
                source_line_chrome=self._source_line_chrome,
                session=self._session,
                pointer_sink=self._mouse_handler,
                publication_sink=self,
                build_context=self,
                direct_feedback_context=self,
                deferred_feedback_context=self,
                prompt_state_host=self,
                fact_context=self,
                source_effect_sink=self,
                source_caret_sink=self,
                document_scroll_bar=self.verticalScrollBar(),
                schedule_geometry_reuse_warm=(
                    lambda reason: self._geometry_reuse_warmer.schedule(reason=reason)
                ),
                diagnostics=self._diagnostic_layer_owner,
                autocomplete_preview=self._autocomplete_preview_projection_owner,
                transient_viewport=self.viewport(),
                transient_scroll_offset=self._scroll_offset,
                transient_publish_render_frame=self._publish_render_frame,
            ),
            parent=self,
            frame_state=self._frame_state,
        )
        self._source_document_adapter = source_state_owners.source_document
        self._source_commit_application = source_state_owners.source_commit_application
        self._active_projection_document = self._editor_state.projection.document
        self._layout_width_resolver: PromptProjectionLayoutWidthResolver
        self._reorder = PromptReorderProjectionOwner(
            surface=self,
            viewport=self.viewport(),
            applicator=self._projection_applicator,
            thumbnail_cache=thumbnail_cache,
            editor_state=self._editor_state,
            layout=self._layout,
            layout_width=lambda: self._layout_width_resolver.resolve(),
            scroll_offset=self._scroll_offset,
            flush_pending_projection=(
                lambda reason: self._flush_pending_projection_update(reason=reason)
            ),
            synchronize_layout=self._sync_layout_state,
            publish_render_frame=self._publish_render_frame,
            request_update=self.viewport().update,
        )
        self._selection_layer_owner = PromptProjectionSelectionLayerOwner(
            frame=lambda: self._layout.frame,
            selection=self._selection,
            viewport_rect=lambda: QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset,
            preview_active=self._reorder.is_active,
        )
        initial_state = (
            self._editor_state.projection.document.caret_map.state_for_source_position(
                0
            )
        )
        self._caret_state_owner = PromptProjectionCaretStateOwner(initial_state)
        self._editing_enabled = True
        self._history = PromptProjectionHistoryOwner(
            editing_session=self._editing_session,
            caret_state=self._caret_state_owner,
            projection_session=self._session,
            editor_state=self._editor_state,
            layout=self._layout,
            set_cursor_positions=(
                lambda cursor, anchor: self.set_cursor_positions(
                    cursor_position=cursor,
                    anchor_position=anchor,
                )
            ),
            publish_undo_available=self.undoAvailableChanged.emit,
            publish_redo_available=self.redoAvailableChanged.emit,
        )
        editing_runtime = editing_runtime_factory(self)
        self._edit_execution = editing_runtime.execution
        self._source_commands = editing_runtime.source_commands
        self._text_mutations = editing_runtime.text_mutations
        self._history.bind_clipboard_history(editing_runtime.clipboard_history)
        self._undo_coalescing_actions = editing_runtime.undo_coalescing
        self._input_method_controller: PromptInputMethodController[
            PromptProjectionUndoPayload
        ] = PromptInputMethodController(
            cast(PromptInputMethodHost, self),
            text_mutations=self._text_mutations,
        )
        self._deletion_controller = PromptSurfaceDeletionController(
            context_provider=cast(PromptDeletionContextProvider, self),
            projection_effects=cast(PromptDeletionProjectionEffects, self),
            source_commands=self._source_commands,
        )
        self._key_handler = PromptSurfaceKeyHandler(
            cast(PromptSurfaceKeyHost, self),
            deletion_controller=self._deletion_controller,
            text_mutations=self._text_mutations,
            clipboard_history_actions=lambda: self._history.clipboard_history_actions,
            undo_coalescing_actions=lambda: self._undo_coalescing_actions,
        )
        self._wheel_handler = PromptSurfaceWheelHandler(
            cast(PromptSurfaceWheelHost, self)
        )
        self._viewport_event_router = PromptProjectionViewportEventRouter(
            viewport=self.viewport(),
            layout=self._layout,
            mouse=self._mouse_handler,
            wheel=self._wheel_handler,
            external_text=self._external_text_input,
            parent=self,
        )
        self._caret_visual_controller = PromptSurfaceCaretVisualController(
            cast(PromptSurfaceCaretVisualHost, self),
            is_alive=qt_object_is_alive,
            reorder_preview_active=self._reorder.is_active,
            parent=self,
        )
        self._transient_edit_overlays = source_state_owners.transient_edit_overlays
        self._transient_edit_presentation = (
            source_state_owners.transient_edit_presentation
        )
        self._last_rendered_active_span_range: tuple[int, int] | None = None
        self._emphasis = PromptProjectionEmphasisOwner(
            session=self._session,
            is_projected=(
                lambda: self._display_mode is PromptProjectionDisplayMode.PROJECTED
            ),
            tokens=lambda: self._editor_state.projection.document.tokens,
            apply_session_paint_state=(
                lambda: self._try_apply_current_session_projection_paint_state()
            ),
            apply_accent_paint_state=(
                lambda: self._apply_decoration_accent_paint_state()
            ),
            rebuild_projection=lambda: self._rebuild_projection(),
            publish_caret=(
                lambda cursor_state, anchor_state: self._set_caret_states(
                    cursor_state=cursor_state,
                    anchor_state=anchor_state,
                )
            ),
            parent=self,
        )
        self._caret_visibility_prompt_state_revision: int | None = None
        self._projection_freshness_controller = source_state_owners.freshness_controller
        self._layout_width_resolver = PromptProjectionLayoutWidthResolver(
            host=self,
            viewport=self.viewport(),
            freshness=self._projection_freshness_controller,
        )
        self._caret_movement_controller = PromptProjectionCaretMovementController(
            cast(PromptProjectionCaretMovementHost, self),
            state=self._caret_state_owner,
        )
        self._edit_pipeline = source_state_owners.edit_pipeline
        self._prompt_state_applier = source_state_owners.prompt_state_applier
        self._fill_band_owner = PromptProjectionFillBandOwner(
            freshness=self._projection_freshness_controller,
            display_mode=lambda: self._display_mode,
            current_source_identity=lambda: self._editor_state.source_identity,
            committed_source_text=(
                lambda: self._editor_state.projection.document.source_text
            ),
            live_source_text=self.toPlainText,
            viewport_rect=lambda: QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset,
            content_width=(
                lambda: self._layout.frame.output.snapshot.content_size.width()
            ),
            content_left_inset=lambda: self._source_line_chrome.content_left_inset,
            reorder_geometry=self._reorder.geometry_owner.projection_geometry,
            geometry_state=lambda: reorder_geometry_state(self._layout.frame.geometry),
        )
        self._pointer_interactions = PromptSurfacePointerInteractions()
        self._region_chrome_presentation = PromptRegionChromePresentationOwner(
            publish_render_frame=self._publish_render_frame,
            request_update=self.viewport().update,
        )
        self._render_frame_owner = PromptProjectionRenderFrameOwner()
        self._render_publication = PromptProjectionRenderPublicationOwner(
            surface=self,
            viewport=self.viewport(),
            layout=self._layout,
            editor_state=self._editor_state,
            session=self._session,
            reorder_preview=self._reorder.preview,
            input_method=self._input_method_controller,
            content_media=self._content_media_owner,
            selection_layer=self._selection_layer_owner,
            source_line_chrome=self._source_line_chrome,
            region_chrome=self._region_chrome_presentation.chrome,
            reorder_visual_state=self._reorder.presentation.visual_state,
            search_highlight=self._search_highlight_layer,
            diagnostics=self._diagnostic_layer_owner,
            transient_overlays=self._transient_edit_overlays,
            freshness=self._projection_freshness_controller,
            frame_owner=self._render_frame_owner,
            scroll_offset=self._scroll_offset,
            should_paint_caret=self._should_paint_caret,
            current_caret_rect=self._current_caret_rect,
            preview_visible_region=self._reorder.presentation.preview_visible_region,
            reorder_preview_generation=self._reorder.preview_generation,
        )
        self._render_compositor = PromptProjectionRenderCompositor()
        self._layout.frame.set_semantic_palette(semantic_palette_from_theme())
        self._frame_synchronizer = PromptProjectionFrameSynchronizer(
            host=self,
            layout=self._layout,
            applicator=self._projection_applicator,
            reorder_preview=self._reorder.preview,
            frame_state=self._frame_state,
            width_resolver=self._layout_width_resolver,
            freshness=self._projection_freshness_controller,
            region_chrome=self._region_chrome_presentation.chrome,
            source_document=self._source_document_adapter,
            source_line_chrome=self._source_line_chrome,
            scroll_offset=self._scroll_offset,
            scroll_range_sink=lambda page_step, scroll_range: (
                self._wheel_handler.sync_external_scroll_range(
                    page_step=page_step,
                    scroll_range=scroll_range,
                )
            ),
            content_height_sink=self.contentHeightChanged.emit,
        )

        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().setAcceptDrops(True)
        self.viewport().setAutoFillBackground(False)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.viewport().installEventFilter(self._viewport_event_router)
        self._lora_feature_delegate.install_tooltip_filter()
        self._sync_layout_state()
        self._rebuild_projection()

    @property
    def cursor_position(self) -> int:
        """Return the editing-session-owned raw source cursor position."""

        return self._editing_session.cursor_position

    @property
    def editor_state(self) -> PromptProjectionEditorState:
        """Return the shared revisioned state owner used by composition."""

        return self._editor_state

    @property
    def reorder(self) -> PromptReorderProjectionOwner:
        """Return the focused reorder projection owner for composition wiring."""

        return self._reorder

    @property
    def emphasis(self) -> PromptProjectionEmphasisOwner:
        """Return the focused emphasis projection owner for interaction wiring."""

        return self._emphasis

    @property
    def diagnostics(self) -> PromptDiagnosticLayerOwner:
        """Return the owner of diagnostic state and render-layer publication."""

        return self._diagnostic_layer_owner

    @property
    def autocomplete_preview(self) -> PromptAutocompletePreviewProjectionOwner:
        """Return the owner of autocomplete preview projection lifecycle."""

        return self._autocomplete_preview_projection_owner

    @property
    def anchor_position(self) -> int:
        """Return the editing-session-owned raw source selection anchor."""

        return self._editing_session.anchor_position

    def document(self) -> QTextDocument:
        """Return the plain-text source document kept for compatibility helpers."""

        return self._source_document_adapter.document()

    @property
    def edit_execution(
        self,
    ) -> PromptEditExecution[PromptProjectionUndoPayload]:
        """Return the construction-owned editing execution service."""

        return self._edit_execution

    @property
    def source_commands(
        self,
    ) -> PromptSourceCommandService[PromptProjectionUndoPayload]:
        """Return the focused source command service."""

        return self._source_commands

    @property
    def history(self) -> PromptProjectionHistoryOwner:
        """Return the owner of undo payloads and clipboard history actions."""

        return self._history

    def attach_external_scroll_bar(self, scroll_bar: QScrollBar) -> None:
        """Mirror layout range and scroll offset onto one host-owned scrollbar."""

        self._wheel_handler.attach_external_scroll_bar(scroll_bar)

    def attach_focus_host(self, focus_host: QWidget) -> None:
        """Store the widget whose focus should drive caret and accent visibility."""

        self._focus_owner.attach(focus_host)

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_REFRESH_SCROLL)
    def refresh_scroll(self) -> None:
        """Repaint after the host scrollbar moves the visible projection window."""

        self._frame_state.publish_widget_viewport(
            self.viewport(),
            horizontal_scroll=int(self.horizontalScrollBar().value()),
            vertical_scroll=int(round(self._scroll_offset())),
        )
        self._frame_state.publish_prepared_paint(
            self._layout.frame.output,
            self._layout.frame.paint_state,
        )
        self._selection_layer_owner.refresh()
        self._diagnostic_layer_owner.refresh(reason="viewport_scrolled")
        self._prepare_source_line_chrome_layer()
        self._prepare_search_highlight_layer()
        self._input_method_controller.refresh_render_layer()
        self._publish_render_frame()
        self._wheel_handler.refresh_scroll()

    def set_editing_enabled(self, editing_enabled: bool) -> None:
        """Enable or disable source mutations while keeping navigation active."""

        if self._editing_enabled != editing_enabled:
            self._finish_pending_key_edit_block(reason="editing_enabled_changed")
        self._editing_enabled = editing_enabled

    def editing_enabled(self) -> bool:
        """Return whether clipboard/history owners may mutate source text."""

        return self._editing_enabled

    def exact_source_editing_enabled(self) -> bool:
        """Return whether user edits bypass prompt source normalization."""

        return self._exact_source_editing_enabled

    def set_exact_source_editing_enabled(self, enabled: bool) -> None:
        """Enable or disable exact source preservation for user edits."""

        self._exact_source_editing_enabled = enabled

    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return the current visible prompt display mode."""

        return self._display_mode

    def set_display_mode(self, display_mode: PromptProjectionDisplayMode) -> None:
        """Replace the visible prompt display mode without changing source text."""

        if display_mode is self._display_mode:
            return
        self._flush_pending_projection_update(reason="set_display_mode")
        layout_identity = (
            PromptProjectionDisplayModeLayoutIdentity.from_projection_state(
                semantic_identity=self._editor_state.projection_semantic.identity,
                session=self._session,
                decoration_accent_ranges=self._decoration_accent_ranges(),
                scene_error_keys=self._scene_error_keys,
            )
        )
        self._display_mode_layout_cache.remember(
            self._display_mode,
            self._layout.frame.output,
            self._layout.frame.paint_input,
            identity=layout_identity,
        )
        previous_cursor_state = self._caret_state_owner.cursor_state
        previous_anchor_state = self._caret_state_owner.anchor_state
        self._display_mode = display_mode
        self._reorder.clear_projection_and_geometry(reason="display_mode_changed")
        self._mouse_handler.clear_hovered_token(update=False)
        restored_projection = self._display_mode_layout_cache.try_restore(
            display_mode,
            self._layout.frame.output,
            self._layout.frame.paint_input,
            identity=layout_identity,
            expected_source_text=(
                self._editor_state.projection_semantic.document.source_text
            ),
            previous_cursor_state=previous_cursor_state,
            previous_anchor_state=previous_anchor_state,
        )
        if restored_projection is None:
            self._build_and_publish_projection()
        else:
            self._layout.frame.restore(restored_projection.layout_output)
            self._publish_projection_rebuild_result(
                restored_projection.projection_rebuild,
                invalidation_reason="display_mode_layout_restored",
            )
        self._ensure_caret_visible()
        self.cursorPositionChanged.emit()
        if not self._active_projection_requires_layout():
            self._restore_base_projection_layout_after_transient_state()

    def changeEvent(self, event: QEvent) -> None:
        """Invalidate reorder preview caches when visual metrics may have changed."""

        if event.type() in {
            QEvent.Type.FontChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }:
            self._reorder.clear_projection_and_geometry(reason="visual_style_changed")
            self._input_method_controller.refresh_render_layer()
            self._publish_render_frame()
        super().changeEvent(event)

    def projection_document(self) -> PromptProjectionDocument:
        """Return the committed token-aware projection document."""

        return self._editor_state.projection.document

    def active_projection_document(self) -> PromptProjectionDocument:
        """Return the current geometry-bearing projection document."""

        return self._active_projection_document

    def content_height(self) -> float:
        """Return the current laid-out projection content height."""

        preview_frame = self._reorder.preview.preview_frame
        if preview_frame is not None:
            return preview_frame.output.snapshot.content_size.height()
        committed_metrics = self._projection_freshness_controller.committed_metrics
        if self._projection_freshness_controller.can_use_committed_passive_metrics():
            assert committed_metrics is not None
            return committed_metrics.content_height
        self._flush_pending_projection_update(
            reason="content_height_initial_or_unavailable"
        )
        return self._layout.frame.output.snapshot.content_size.height()

    def text_line_height(self) -> float:
        """Return the row height owned by the current prepared layout."""

        return self._layout.frame.output.configuration.metrics.text_line_height

    def source_range_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return the wrapped viewport fragments covering one raw source range."""

        self._flush_pending_projection_update(reason="source_range_fragments")
        return self._layout.frame.geometry.selection.source_range_fragments(
            start,
            end,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
        )

    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible source logical line rects aligned to prompt projection."""

        self.has_pending_projection_update()
        self._flush_pending_projection_update(reason="source_line_rects")
        rects = self._source_line_chrome.source_line_rects(
            geometry=self._layout.frame.geometry,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
        )
        return rects

    def visible_prompt_fill_band_rects(self) -> tuple[PromptFillBandRect, ...]:
        """Return visible prompt fill band rows in projection viewport coordinates."""

        return self._fill_band_owner.visible_rects()

    def prompt_fill_band_color(self) -> QColor:
        """Return the alternating prompt fill color used beneath projection painting."""

        return self._fill_band_owner.color()

    def current_source_line_index(self) -> int:
        """Return the newline-delimited source line containing the cursor."""

        self._flush_pending_projection_update(reason="current_source_line_index")
        return self._source_line_chrome.current_source_line_index(
            geometry=self._layout.frame.geometry,
            cursor_position=self.cursor_position,
        )

    def set_source_line_chrome_enabled(self, enabled: bool) -> None:
        """Enable source logical line backgrounds for wrapper-provided editor chrome."""

        if not self._source_line_chrome.set_enabled(enabled):
            return
        self._prepare_source_line_chrome_layer()
        self.viewport().update()

    def set_source_line_content_left_inset(self, inset: float) -> None:
        """Reserve viewport-local space for source line numbers."""

        inset = max(0.0, inset)
        if abs(self._source_line_chrome.content_left_inset - inset) < 0.01:
            return
        self._flush_pending_projection_update(
            reason="set_source_line_content_left_inset"
        )
        self._source_line_chrome.set_content_left_inset(inset)
        self._sync_layout_state()
        self.viewport().update()

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Replace scene keys that should render as title-level diagnostics."""

        if self._scene_error_keys == scene_error_keys:
            return
        self._flush_pending_projection_update(reason="set_scene_error_keys")
        self._scene_error_keys = scene_error_keys
        self._mouse_handler.clear_hovered_token(update=False)
        self._rebuild_projection()

    def _rebuild_active_projection(self, *, commit_projection: bool = False) -> None:
        """Build an explicit layout-affecting preview projection when required."""

        if not qt_object_is_alive(self):
            return
        log_prompt_editor_probe(
            "surface.rebuild_active_projection.begin",
            commit_projection=commit_projection,
            requires_layout=self._active_projection_requires_layout(),
            surface=surface_probe_state(self),
        )
        if not self._active_projection_requires_layout():
            self._restore_base_projection_layout_after_transient_state()
            self._refresh_projection_paint_state()
            if commit_projection:
                self._sync_layout_state(commit_projection=True)
            log_prompt_editor_probe(
                "surface.rebuild_active_projection.paint_state_only",
                commit_projection=commit_projection,
                surface=surface_probe_state(self),
            )
            return
        transient_state = self._active_projection_transient_state()
        active_span_range = (
            None
            if self._display_mode is PromptProjectionDisplayMode.RAW
            else self._active_span_range()
        )
        self._last_rendered_active_span_range = active_span_range
        self._active_projection_document = self._projection_applicator.build_projection(
            self._editor_state.projection_semantic.document,
            self._editor_state.projection_semantic.render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=active_span_range,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            transient_state=transient_state,
        )
        self._layout.set_projection(
            self._active_projection_document,
            prompt_document_view=self._editor_state.projection_semantic.document,
        )
        self._sync_layout_state(commit_projection=commit_projection)
        self.viewport().update()
        log_prompt_editor_probe(
            "surface.rebuild_active_projection.end",
            commit_projection=commit_projection,
            surface=surface_probe_state(self),
        )

    def _refresh_projection_paint_state(self) -> None:
        """Refresh geometry-neutral projection paint state from session state."""

        if not qt_object_is_alive(self):
            return
        self._restore_base_projection_layout_after_transient_state()
        log_prompt_editor_probe(
            "surface.refresh_projection_paint_state.begin",
            surface=surface_probe_state(self),
        )
        active_span_range = (
            None
            if self._display_mode is PromptProjectionDisplayMode.RAW
            else self._active_span_range()
        )
        result = self._projection_applicator.apply_reusable_projection_paint_state(
            self._editor_state.projection_semantic.document,
            self._editor_state.projection_semantic.render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=active_span_range,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            frame=self._layout.frame,
        )
        if result is None:
            log_prompt_editor_probe(
                "surface.refresh_projection_paint_state.noop",
                surface=surface_probe_state(self),
            )
            return
        self._last_rendered_active_span_range = result.active_span_range
        self._active_projection_document = self._editor_state.projection.document
        self._frame_state.publish_prepared_paint(
            self._layout.frame.output,
            self._layout.frame.paint_state,
        )
        self._publish_render_frame()
        self.viewport().update()
        log_prompt_editor_probe(
            "surface.refresh_projection_paint_state.end",
            surface=surface_probe_state(self),
        )

    def _restore_base_projection_layout_after_transient_state(self) -> None:
        """Restore canonical projection geometry after layout-affecting transient state."""

        if (
            self._layout.frame.output.projection_document
            is self._editor_state.projection.document
        ):
            self._active_projection_document = self._editor_state.projection.document
            return
        log_prompt_editor_probe(
            "surface.restore_base_projection_layout.begin",
            surface=surface_probe_state(self),
        )
        self._layout.set_projection(
            self._editor_state.projection.document,
            prompt_document_view=self._editor_state.projection_semantic.document,
        )
        self._active_projection_document = self._editor_state.projection.document
        self._sync_layout_state()
        self.viewport().update()
        log_prompt_editor_probe(
            "surface.restore_base_projection_layout.end",
            surface=surface_probe_state(self),
        )

    def _active_projection_requires_layout(self) -> bool:
        """Return whether current temporary projection state changes geometry."""

        transient_state = self._active_projection_transient_state()
        return (
            transient_state.autocomplete_preview is not None
            or self._session.exact_weight_edit is not None
            or self._session.expanded_source_range is not None
            or self._session.transient_neutral_emphasis is not None
        )

    def _active_projection_transient_state(self) -> PromptProjectionTransientState:
        """Return projection-owned transient state valid for active painting."""

        preview = self._session.autocomplete_preview
        if (
            preview is None
            or not preview.suffix_text
            or not self._selection().is_empty
            or preview.source_position != self.cursor_position
            or self._reorder.is_active()
        ):
            return PromptProjectionTransientState()
        return PromptProjectionTransientState(
            autocomplete_preview=PromptProjectionInlinePreview(
                source_position=preview.source_position,
                suffix_text=preview.suffix_text,
            )
        )

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Replace the transient search matches rendered by the projection surface."""

        self._session.set_search_matches(matches, active_index=active_index)
        self._prepare_search_highlight_layer()
        self._publish_render_frame()
        self.viewport().update()

    def clear_search_matches(self) -> None:
        """Clear transient search highlights from the projection surface."""

        self._session.clear_search_matches()
        self._search_highlight_layer.clear()
        self._publish_render_frame()
        self.viewport().update()

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the syntax span currently owned by the caret or token focus."""

        token = self._focused_or_hovered_token(prefer_hovered=False)
        if token is not None:
            return next(
                (
                    span
                    for span in reversed(
                        self._editor_state.projection_semantic.render_plan.syntax_spans
                    )
                    if span.start == token.source_start and span.end == token.source_end
                ),
                None,
            )
        position = self.cursor_position
        for span in reversed(
            self._editor_state.projection_semantic.render_plan.syntax_spans
        ):
            if span.start < position < span.end:
                return span
        return None

    def hovered_token(self) -> PromptProjectionToken | None:
        """Return the token currently under the pointer when present."""

        hovered_token_id = self._mouse_handler.hovered_token_id
        if hovered_token_id is None:
            return None
        return self._layout.frame.paint_input.effective_token(hovered_token_id)

    def focused_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning caret focus when present."""

        return self._editor_state.projection.document.token_by_id(
            self._caret_state_owner.cursor_state.token_id
        )

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projected token painted under one viewport-local point."""

        return self._layout.frame.geometry.tokens.token_at_viewport_position(
            position,
            scroll_offset=self._scroll_offset(),
        )

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor rect used by any token controls."""

        return self._layout.frame.geometry.tokens.token_anchor_rect(
            token,
            scroll_offset=self._scroll_offset(),
        )

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local projection-owned weight slot for one emphasis token."""

        return self._layout.frame.geometry.tokens.token_weight_text_rect(
            token,
            scroll_offset=self._scroll_offset(),
        )

    def toPlainText(self) -> str:
        """Return the current raw prompt source text."""

        return self._editing_session.source_text

    def prompt_document_view(self) -> PromptDocumentView:
        """Return the current prepared prompt document view."""

        return self._editor_state.edit_semantic.document

    def set_defer_source_rebuilds_until_prompt_state(self, enabled: bool) -> None:
        """Set whether source edits wait for controller-owned prompt snapshots."""

        self._projection_freshness_controller.set_defer_source_rebuilds_until_prompt_state(
            enabled
        )

    def apply_edit_commit(
        self,
        commit: PromptEditCommit[PromptProjectionUndoPayload],
    ) -> None:
        """Apply the sole committed editing result to projection state."""

        self._source_commit_application.apply_edit_commit(commit)

    def textCursor(self) -> PromptCursorAdapter:  # noqa: N802
        """Return a Qt-like cursor wrapper backed by the surface state."""

        return PromptCursorAdapter(self, self._editing_session.cursor_state)

    def setTextCursor(self, cursor: object) -> None:  # noqa: N802
        """Apply a Qt-compatible source cursor snapshot to the editor."""

        self.cursor_adapter_commit_state(
            self._cursor_state_from_compatible_cursor(cursor),
            reason="set_text_cursor",
        )

    def _cursor_state_from_compatible_cursor(self, cursor: object) -> PromptCursorState:
        """Return source cursor state from a QTextCursor-like public cursor object."""

        if isinstance(cursor, PromptCursorAdapter):
            return cursor.cursor_state()
        cursor_state_method = getattr(cursor, "cursor_state", None)
        if callable(cursor_state_method):
            cursor_state = cursor_state_method()
            if isinstance(cursor_state, PromptCursorState):
                return cursor_state
        position_method = getattr(cursor, "position", None)
        selection_start_method = getattr(cursor, "selectionStart", None)
        selection_end_method = getattr(cursor, "selectionEnd", None)
        if not (
            callable(position_method)
            and callable(selection_start_method)
            and callable(selection_end_method)
        ):
            raise TypeError("Cursor must expose position and selection bounds.")
        cursor_position = int(position_method())
        selection_start = int(selection_start_method())
        selection_end = int(selection_end_method())
        anchor_position = (
            selection_end if cursor_position == selection_start else selection_start
        )
        return PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=anchor_position,
        )

    def cursorForPosition(self, position: QPoint) -> PromptCursorAdapter:  # noqa: N802
        """Return a cursor wrapper after hit-testing one viewport-local point."""

        self._flush_pending_projection_update(reason="cursor_for_position")
        caret_state = self._layout.frame.geometry.hit_testing.hit_test(
            QPointF(position),
            scroll_offset=self._scroll_offset(),
        )
        self._set_cursor_from_projection_hit(
            caret_state,
            keep_anchor=False,
        )
        return self.textCursor()

    def cursor_adapter_source_text(self) -> str:
        """Return source text for the editing-session cursor adapter."""

        return self.toPlainText()

    def cursor_adapter_state(self) -> PromptCursorState:
        """Return the current source cursor state for a cursor adapter."""

        return self._editing_session.cursor_state

    def cursor_adapter_commit_state(
        self,
        cursor_state: PromptCursorState,
        *,
        reason: str,
    ) -> PromptCursorState:
        """Commit a cursor adapter state through projection-aware cursor placement."""

        _ = reason
        self.set_cursor_positions(
            cursor_position=cursor_state.cursor_position,
            anchor_position=cursor_state.anchor_position,
        )
        return self._editing_session.cursor_state

    def cursor_adapter_is_keep_anchor_mode(self, mode: object | None) -> bool:
        """Return whether an opaque cursor mode is QTextCursor KeepAnchor."""

        return mode == QTextCursor.MoveMode.KeepAnchor

    def cursor_adapter_finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Flush key-owned edit groups before cursor-adapter mutations."""

        self._finish_pending_key_edit_block(reason=reason)

    def cursor_adapter_begin_edit_block(self, *, finish_typing: bool = True) -> None:
        """Begin an edit block requested by the source cursor adapter."""

        self._edit_execution.begin_edit_block(finish_typing=finish_typing)

    def cursor_adapter_end_edit_block(self) -> None:
        """End an edit block requested by the source cursor adapter."""

        self._edit_execution.end_edit_block()

    def cursor_adapter_delete_selection(self) -> None:
        """Delete the live selection requested by the source cursor adapter."""

        self._delete_viewport_selection()

    def cursor_adapter_insert_text(
        self,
        text: str,
    ) -> None:
        """Insert text requested by the source cursor adapter."""

        self._text_mutations.insert_text(
            text,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            command_name="cursor_insert_text",
        )

    def cursorRect(self) -> QRect:  # noqa: N802
        """Return the current viewport-local caret rect."""

        self._visible_scroll_bar()
        self.has_pending_projection_update()
        transient_rect = self._valid_transient_caret_document_rect()
        if transient_rect is not None:
            self._log_transient_caret_used(operation="cursor_rect")
            rect = transient_rect.translated(
                0.0, -self._scroll_offset()
            ).toAlignedRect()
            return rect
        self._flush_pending_projection_update(reason="cursor_rect")
        rect = self._current_caret_rect().toAlignedRect()
        return rect

    def input_method_caret_rect(self, source_position: int) -> QRectF:
        """Return a viewport-local caret rectangle for input-method geometry."""

        self._flush_pending_projection_update(reason="input_method_caret_rect")
        caret_state = (
            self._editor_state.projection.document.caret_map.state_for_source_position(
                min(max(0, source_position), len(self.toPlainText()))
            )
        )
        return self._layout.frame.geometry.caret.cursor_rect(
            caret_state,
            scroll_offset=self._scroll_offset(),
        )

    def set_prompt_state(
        self,
        snapshot: PromptEditorSemanticSnapshot,
    ) -> None:
        """Replace the source snapshot and rebuild the token-aware projection."""

        if not qt_object_is_alive(self):
            return
        self._prompt_state_applier.set_prompt_state(snapshot)

    def _log_projection_state_event(
        self,
        event_name: str,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        source_changed: bool,
        can_schedule_safe_typing: bool,
        can_schedule_metadata: bool,
        apply_path: str,
        update_source_revision: int | None = None,
    ) -> None:
        """Emit one prompt projection state transition diagnostic event."""

        log_debug(
            _LOGGER,
            event_name,
            source_changed=source_changed,
            source_revision=self._editor_state.source.source_revision,
            update_source_revision=update_source_revision,
            display_mode=self._display_mode.value,
            expanded_source_range_present=(
                self._session.expanded_source_range is not None
            ),
            can_schedule_safe_typing=can_schedule_safe_typing,
            can_schedule_metadata=can_schedule_metadata,
            apply_path=apply_path,
            document_lora_span_count=len(document_view.lora_spans),
            render_plan_lora_span_count=render_plan_lora_span_count(render_plan),
        )

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return active projection state that can block deferred freshness work."""

        return PromptProjectionFreshnessBlockers(
            display_mode=self._display_mode,
            reorder_preview_active=self._reorder.is_active(),
            autocomplete_preview_active=self._session.autocomplete_preview is not None,
            exact_weight_edit_active=self._session.exact_weight_edit is not None,
            expanded_source_range_active=(
                self._session.expanded_source_range is not None
            ),
        )

    def _flush_pending_projection_update(self, *, reason: str) -> None:
        """Apply scheduled projection work before exact geometry is read."""

        if not qt_object_is_alive(self):
            return
        self._projection_freshness_controller.flush_pending_update(reason=reason)

    def _cancel_stale_safe_projection_update(self, *, reason: str) -> bool:
        """Drop stale safe-typing projection work before superseding source edits."""

        if not qt_object_is_alive(self):
            return False
        cancelled = (
            self._projection_freshness_controller.cancel_stale_safe_projection_update(
                source_text=self._editor_state.projection.document.source_text
            )
        )
        return cancelled

    def _cancel_pending_projection_update(self) -> None:
        """Cancel stale scheduled projection work before immediate rebuild paths."""

        if not qt_object_is_alive(self):
            return
        self._projection_freshness_controller.cancel_pending_projection_update()

    def _mark_source_text_changed(
        self,
        *,
        deferrable_projection: bool,
        source_snapshot: PromptSourceSnapshot,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> None:
        """Record source revision and whether the next prompt state can be scheduled."""

        self._input_method_controller.source_changed()
        if not deferrable_projection:
            self._clear_transient_caret_geometry()
        source_identity = self._editor_state.publish_source(source_snapshot)
        self._reorder.clear_for_source_change()
        if clear_diagnostic_fragment_cache:
            self._diagnostic_layer_owner.clear_fragment_cache(reason="source_changed")
        self._projection_freshness_controller.mark_source_text_changed(
            deferrable_projection=deferrable_projection,
            source_revision=source_identity.source_revision,
        )

    def _clear_transient_caret_geometry(self) -> None:
        """Discard stale temporary caret geometry."""

        self._transient_edit_overlays.clear()

    def _valid_transient_caret_document_rect(self) -> QRectF | None:
        """Return the temporary document-local caret rect when it is valid."""

        return self._transient_edit_overlays.valid_caret_document_rect(
            freshness_is_stale_safe=(
                self._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_identity=self._editor_state.source_identity,
            cursor_position=self.cursor_position,
            anchor_position=self.anchor_position,
        )

    def _log_transient_caret_used(self, *, operation: str) -> None:
        """Preserve the removed transient-caret diagnostic hook."""

        del operation

    def has_pending_projection_update(self) -> bool:
        """Return whether a safe projection rebuild is waiting to flush."""

        return self._projection_freshness_controller.has_pending_update()

    def flush_pending_projection_update(self, *, reason: str) -> None:
        """Synchronously apply pending projected presentation work."""

        self._flush_pending_projection_update(reason=reason)

    def projection_scroll_offset(self) -> float:
        """Return the current document-to-viewport vertical offset."""

        return self._scroll_offset()

    @property
    def pointer_interactions(self) -> PromptSurfacePointerInteractions:
        """Return the focused owner of pointer and regional intent ports."""

        return self._pointer_interactions

    def set_region_hovered(self, region_index: int | None) -> None:
        """Publish transient regional chrome without changing prompt selection."""

        self._region_chrome_presentation.set_hovered_region(region_index)

    def region_edit_target(
        self,
        region_index: int,
    ) -> PromptRegionChromeEditTarget | None:
        """Return prepared document-local geometry for one separator editor."""

        return self._region_chrome_presentation.edit_target(region_index)

    def set_region_editing(self, region_index: int | None) -> None:
        """Publish label suppression while an inline editor owns one separator."""

        self._region_chrome_presentation.set_editing_region(region_index)

    def set_region_editing_draft(self, region_index: int, text: str) -> None:
        """Publish live separator geometry without mutating prompt source text."""

        self._region_chrome_presentation.set_editing_region_draft(region_index, text)

    def force_collapse_expanded_token(self) -> None:
        """Collapse any expanded projection token after an explicit syntax commit."""

        if self._session.expanded_source_range is None:
            return
        self._session.expanded_source_range = None
        self._rebuild_projection()

    def has_stale_projection_geometry(self) -> bool:
        """Return whether layout metrics still describe an older source snapshot."""

        return self._projection_freshness_controller.has_stale_projection_geometry()

    def set_wheel_scroll_permission(
        self,
        permission: Callable[[QWheelEvent], bool] | None,
    ) -> None:
        """Set the callback that decides whether this surface may wheel-scroll."""

        self._wheel_handler.set_wheel_scroll_permission(permission)

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Track active syntax ownership without rebuilding projection geometry."""

        _ = cursor_position
        focused_or_hovered_token = self._focused_or_hovered_token(prefer_hovered=False)
        next_active_span_range = (
            (focused_or_hovered_token.source_start, focused_or_hovered_token.source_end)
            if focused_or_hovered_token is not None
            else (
                (active_span.start, active_span.end)
                if active_span is not None
                else None
            )
        )
        if next_active_span_range == self._last_rendered_active_span_range:
            return
        if self._display_mode is not PromptProjectionDisplayMode.PROJECTED:
            self._last_rendered_active_span_range = next_active_span_range
            return
        self._refresh_projection_paint_state()
        self.viewport().update()

    def _try_apply_current_session_projection_paint_state(self) -> bool:
        """Apply session-only projection changes when layout geometry is unchanged."""

        result = self._projection_applicator.apply_reusable_projection_paint_state(
            self._editor_state.projection_semantic.document,
            self._editor_state.projection_semantic.render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=self._active_span_range(),
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            frame=self._layout.frame,
        )
        if result is None:
            return False
        self._projection_freshness_controller.clear_pending_after_immediate_apply()
        self._editor_state.publish_projection(result.projection_document)
        self._last_rendered_active_span_range = result.active_span_range
        self._active_projection_document = self._editor_state.projection.document
        self._frame_state.publish_prepared_paint(
            self._layout.frame.output,
            self._layout.frame.paint_state,
        )
        self._clear_transient_caret_geometry()
        self._publish_render_frame()
        self.viewport().update()
        return True

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_REFRESH_GEOMETRY)
    def refresh_geometry(self) -> None:
        """Refresh layout width, scrollbars, and viewport painting."""

        if (
            self.has_stale_projection_geometry()
            and self.has_pending_projection_update()
        ):
            self.viewport().update()
            return
        previous_signature = self._refresh_geometry_paint_signature()
        self._sync_layout_state()
        next_signature = self._refresh_geometry_paint_signature()
        if previous_signature == next_signature:
            return
        self.viewport().update()

    def _refresh_geometry_paint_signature(
        self,
    ) -> PromptRefreshGeometryPaintSignature:
        """Return visual state used to decide whether refresh_geometry repaints."""

        active_frame = self._reorder.active_frame
        content_size = active_frame.output.snapshot.content_size
        scroll_bar = self.verticalScrollBar()
        return PromptRefreshGeometryPaintSignature(
            content_height=round(float(content_size.height()), 3),
            content_width=round(float(content_size.width()), 3),
            viewport_width=self.viewport().width(),
            viewport_height=self.viewport().height(),
            scroll_value=scroll_bar.value(),
            scroll_maximum=scroll_bar.maximum(),
            page_step=scroll_bar.pageStep(),
            display_mode=self._display_mode,
            projection_freshness=self._projection_freshness_controller.freshness,
            source_line_content_left_inset=round(
                float(self._source_line_chrome.content_left_inset),
                3,
            ),
            source_line_chrome_enabled=self._source_line_chrome.enabled,
            font_key=self.font().toString(),
            palette_key=int(self.palette().cacheKey()),
        )

    def clear_transient_state(self) -> None:
        """Clear transient hover state without affecting caret-owned token focus."""

        self._mouse_handler.clear_hovered_token()

    def hit_test_action(self, position: object) -> PromptSyntaxAction | None:
        """Return no inline syntax action because controls are hosted separately."""

        _ = position
        return None

    def _delete_viewport_selection(self) -> None:
        """Delete the currently selected raw prompt source text."""

        if not self._editing_enabled:
            return
        selection = self._editing_session.selection()
        if selection.is_empty:
            return
        self._finish_pending_key_edit_block(reason="delete_selection")
        self._source_commands.replace_source_range(
            start=selection.start,
            end=selection.end,
            replacement_text="",
            origin=PromptSourceEditOrigin.TYPED,
            command_name="cursor_delete_selection",
        )

    def projection_text_mutation_context(
        self,
    ) -> PromptProjectionTextMutationContext:
        """Return authoritative projection state for a direct text mutation."""

        return PromptProjectionTextMutationContext(
            selection=self._selection(),
            cursor_state=self._caret_state_owner.cursor_state,
            anchor_state=self._caret_state_owner.anchor_state,
            tokens=tuple(self._editor_state.projection.document.tokens),
            editing_enabled=self._editing_enabled,
        )

    def insert_external_text(self, text: str, *, command_name: str) -> None:
        """Insert external plain text through projection boundary ownership."""

        self._text_mutations.insert_text(
            text,
            origin=PromptSourceEditOrigin.PASTE,
            command_name=command_name,
        )

    def deletion_context(self) -> PromptDeletionContext:
        """Capture the immutable state consumed by deletion resolution."""

        token = self.focused_token()
        return PromptDeletionContext(
            source_text=self._editing_session.source_text,
            cursor_position=self.cursor_position,
            cursor_state=self._caret_state_owner.cursor_state,
            anchor_state=self._caret_state_owner.anchor_state,
            selection=self._selection(),
            projection_document=self._editor_state.projection.document,
            focused_token=token,
            focused_token_expanded=(
                token is not None and self._session.is_expanded(token)
            ),
            stale_projection_geometry=(
                self._projection_freshness_controller.has_stale_projection_geometry()
            ),
        )

    def synchronize_deletion_projection(
        self,
        *,
        reason: str,
        cancel_stale_safe_first: bool,
    ) -> None:
        """Make projection state authoritative for one deletion decision."""

        if cancel_stale_safe_first and self._cancel_stale_safe_projection_update(
            reason=reason
        ):
            return
        self._flush_pending_projection_update(reason=reason)

    def expand_token_for_deletion(self, token: PromptProjectionToken) -> None:
        """Expand and select one structural token targeted by deletion."""

        self._session.expand_token(token)
        self._rebuild_projection()
        self.set_cursor_positions(
            cursor_position=token.source_end,
            anchor_position=token.source_start,
        )

    def set_cursor_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> PromptCursorState:
        """Replace the raw cursor positions by resolving them into caret states."""

        self._flush_pending_projection_update(reason="set_cursor_positions")
        if self._projection_freshness_controller.has_stale_projection_geometry():
            self._rebuild_projection()
        cursor_state = PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=anchor_position,
        ).clamped(len(self.toPlainText()))
        self._clear_transient_caret_geometry()
        next_cursor_state = (
            self._editor_state.projection.document.caret_map.state_for_source_position(
                cursor_state.cursor_position
            )
        )
        next_anchor_state = (
            self._editor_state.projection.document.caret_map.state_for_source_position(
                cursor_state.anchor_position
            )
        )
        self._set_caret_states(
            cursor_state=next_cursor_state,
            anchor_state=next_anchor_state,
        )
        return self._editing_session.cursor_state

    def _sync_editing_session_to_caret_states(self) -> PromptCursorState:
        """Synchronize source cursor ownership from projection caret metadata."""

        return self._editing_session.set_cursor_positions(
            cursor_position=self._caret_state_owner.cursor_state.source_position,
            anchor_position=self._caret_state_owner.anchor_state.source_position,
        )

    def _mark_source_edit_horizontal_movement_origin(self) -> None:
        """Make the next horizontal move leave same-source wrap affinity after edits."""

        self._caret_state_owner.mark_source_edit_horizontal_movement_origin()

    def _set_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        reset_preferred_x: bool = True,
        caret_rect_override: QRectF | None = None,
        collapse_expanded_token: bool = True,
        preserve_unmapped_source_positions: bool = False,
        reason: str = "generic",
    ) -> None:
        """Persist logical source positions with projection-backed caret geometry."""

        log_prompt_editor_probe(
            "surface.set_caret_states.begin",
            reason=reason,
            requested_cursor_position=cursor_state.source_position,
            requested_anchor_position=anchor_state.source_position,
            surface=surface_probe_state(self),
        )
        previous_caret_rect = self._current_caret_rect()
        previous_selection = self._selection()
        resolved_cursor_state = (
            self._editor_state.projection.document.caret_map.resolve_state(cursor_state)
        )
        resolved_anchor_state = (
            self._editor_state.projection.document.caret_map.resolve_state(anchor_state)
        )
        if (
            preserve_unmapped_source_positions
            and resolved_cursor_state.source_position != cursor_state.source_position
        ):
            resolved_cursor_state = cursor_state
        if (
            preserve_unmapped_source_positions
            and resolved_anchor_state.source_position != anchor_state.source_position
        ):
            resolved_anchor_state = anchor_state
        next_editing_session_state = PromptCursorState(
            cursor_position=resolved_cursor_state.source_position,
            anchor_position=resolved_anchor_state.source_position,
        ).clamped(len(self.toPlainText()))
        if (
            self._caret_state_owner.matches(
                cursor_state=resolved_cursor_state,
                anchor_state=resolved_anchor_state,
                caret_rect_override=caret_rect_override,
            )
            and self._editing_session.cursor_state == next_editing_session_state
        ):
            self._ensure_caret_visible()
            self._update_caret_paint(previous_caret_rect)
            log_prompt_editor_probe(
                "surface.set_caret_states.end",
                reason=reason,
                changed=False,
                surface=surface_probe_state(self),
            )
            return
        self._clear_transient_caret_geometry()
        self._editing_session.set_cursor_state(next_editing_session_state)
        self._caret_state_owner.publish(
            cursor_state=resolved_cursor_state,
            anchor_state=resolved_anchor_state,
            caret_rect_override=caret_rect_override,
            reset_preferred_x=reset_preferred_x,
        )
        if collapse_expanded_token and self._session.expanded_source_range is not None:
            self._collapse_expanded_token_if_possible()
        self._autocomplete_preview_projection_owner.reconcile_after_caret_state_change(
            cursor_position=resolved_cursor_state.source_position,
            selection_is_empty=self._selection().is_empty,
        )
        self._refresh_active_projection_for_caret_state()
        self._ensure_caret_visible()
        self._selection_layer_owner.refresh()
        self._diagnostic_layer_owner.refresh(reason="selection_changed")
        self._prepare_source_line_chrome_layer()
        self._restart_caret_blink_cycle()
        if selection_paints_changed(previous_selection, self._selection()):
            self.viewport().update()
        self._update_caret_paint(previous_caret_rect)
        self.cursorPositionChanged.emit()
        log_prompt_editor_probe(
            "surface.set_caret_states.end",
            reason=reason,
            changed=True,
            surface=surface_probe_state(self),
        )

    def _refresh_active_projection_for_caret_state(self) -> None:
        """Reconcile active-token paint with the current caret-owned syntax range."""

        next_active_span_range = (
            None
            if self._display_mode is PromptProjectionDisplayMode.RAW
            else self._active_span_range()
        )
        if next_active_span_range == self._last_rendered_active_span_range:
            return
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._refresh_projection_paint_state()
            return
        self._last_rendered_active_span_range = next_active_span_range

    def move_cursor_by_operation(
        self, operation: object, *, keep_anchor: bool
    ) -> PromptCursorState:
        """Move the caret according to one supported QTextCursor operation."""

        self._flush_pending_projection_update(reason="move_cursor_by_operation")
        if operation == QTextCursor.MoveOperation.End:
            target = len(self.toPlainText())
            return self.set_cursor_positions(
                cursor_position=target,
                anchor_position=self.anchor_position if keep_anchor else target,
            )
        if operation == QTextCursor.MoveOperation.Start:
            return self.set_cursor_positions(
                cursor_position=0,
                anchor_position=self.anchor_position if keep_anchor else 0,
            )
        if operation == QTextCursor.MoveOperation.Left:
            self._move_horizontally(-1, keep_anchor=keep_anchor)
            return self._editing_session.cursor_state
        if operation == QTextCursor.MoveOperation.Right:
            self._move_horizontally(+1, keep_anchor=keep_anchor)
            return self._editing_session.cursor_state
        if operation == QTextCursor.MoveOperation.Up:
            self._move_vertically(-1, keep_anchor=keep_anchor)
            return self._editing_session.cursor_state
        if operation == QTextCursor.MoveOperation.Down:
            self._move_vertically(+1, keep_anchor=keep_anchor)
            return self._editing_session.cursor_state
        return self._editing_session.cursor_state

    def select_by_mode(self, mode: object) -> PromptCursorState:
        """Select the supported logical range around the current cursor."""

        self._flush_pending_projection_update(reason="select_by_mode")
        if mode != QTextCursor.SelectionType.WordUnderCursor:
            return self._editing_session.cursor_state
        start, end = prompt_word_bounds(self.toPlainText(), self.cursor_position)
        if start == end:
            return self._editing_session.cursor_state
        return self.set_cursor_positions(
            cursor_position=end,
            anchor_position=start,
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Delegate prompt key routing while preserving Qt fallback behavior."""

        self._handle_key_press_event(event)

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:  # noqa: N802
        """Delegate platform IME composition without persisting preedit text."""

        self._finish_pending_key_edit_block(reason="input_method_event")
        self._input_method_controller.handle_event(event)
        self._publish_render_frame()
        event.accept()
        self.viewport().update()
        QApplication.inputMethod().update(Qt.InputMethodQuery.ImQueryAll)

    def inputMethodQuery(self, query: Qt.InputMethodQuery) -> object:  # noqa: N802
        """Expose source, selection, and caret state to the platform input method."""

        value = self._input_method_controller.query(
            query,
            font=self.font(),
            palette=self.palette(),
            input_method_hints=self.inputMethodHints(),
            viewport_rect=QRectF(self.viewport().rect()),
        )
        if value is not None:
            return value
        return super().inputMethodQuery(query)

    def _handle_key_press_event(self, event: QKeyEvent) -> None:
        """Delegate one key press after the public Qt entrypoint receives it."""

        if self._key_handler.handle_key_press(event):
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Delegate key release handling while preserving Qt fallback behavior."""

        if self._key_handler.handle_key_release(event):
            return
        super().keyReleaseEvent(event)

    def _finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Commit any pending key-owned edit block."""

        self._edit_execution.finish_pending_key_edit_block(reason=reason)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Delegate projection-aware pointer press handling."""

        if self._mouse_handler.handle_mouse_press(event, self._layout.frame):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Delegate projection-aware pointer move handling."""

        if self._mouse_handler.handle_mouse_move(event, self._layout.frame):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Delegate projection-aware pointer release handling."""

        if self._mouse_handler.handle_viewport_mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Delegate token-aware double-click handling."""

        if self._mouse_handler.handle_mouse_double_click(
            event,
            self._layout.frame,
        ):
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hovered token state once the pointer leaves the viewport."""

        self._mouse_handler.clear_hovered_token(update=False)
        self._wheel_handler.clear_boundary_spill()
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll the projection viewport for unhandled wheel input."""

        result = self.handle_prompt_wheel_scroll(event)
        if result is PromptWheelScrollResult.CONSUMED:
            event.accept()
            return
        event.ignore()

    def handle_prompt_wheel_scroll(
        self,
        event: QWheelEvent,
    ) -> PromptWheelScrollResult:
        """Handle policy-aware prompt wheel scrolling."""

        return self._wheel_handler.handle_prompt_wheel_scroll(event)

    def viewportEvent(self, event: QEvent) -> bool:
        """Track viewport hover updates even when Qt keeps events on the inner viewport."""

        router = self._viewport_event_router
        if router is None:
            return super().viewportEvent(event)
        handled = router.handle_viewport_event(event)
        if handled is not None:
            return handled
        return super().viewportEvent(event)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:  # noqa: N802
        """Return whether external MIME data may become prompt source text."""

        return self._external_text_input.can_insert(source)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """Insert prompt-safe MIME text through the source mutation owner."""

        self._external_text_input.insert(source)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept only prompt-safe plain text drag payloads."""

        self._external_text_input.accept_or_ignore_drag(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep rejecting non-text drag payloads while the pointer moves."""

        self._external_text_input.accept_or_ignore_drag(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Insert prompt-safe dropped text and reject rich/file payloads."""

        self._external_text_input.drop(
            event,
            viewport_position=self.viewport().mapFrom(
                self,
                event.position().toPoint(),
            ),
        )

    def _insert_external_mime_text(
        self,
        text: str,
        *,
        command_name: str,
        viewport_position: QPoint | None,
    ) -> None:
        """Commit accepted external text through projection source ownership."""
        if viewport_position is not None:
            self.cursorForPosition(viewport_position)
        self.insert_external_text(text, command_name=command_name)

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_RESIZE_EVENT)
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the projection layout width in sync with the viewport."""

        super().resizeEvent(event)
        self._caret_state_owner.clear_visual_affinity(reset_preferred_x=True)
        if not self._projection_freshness_controller.has_stale_projection_geometry():
            self._clear_transient_caret_geometry()
        self._reorder.clear_projection_and_geometry(reason="resize")
        self._diagnostic_layer_owner.clear_fragment_cache(reason="resize")
        self.refresh_geometry()
        self.viewport().update()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Restart caret blinking when the surface itself gains focus ownership."""

        super().focusInEvent(event)
        self._prepare_source_line_chrome_layer()
        self._publish_render_frame()
        self._schedule_caret_blink_sync(reset_cycle=True)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Stop caret blinking when the surface itself loses focus ownership."""

        QApplication.inputMethod().commit()
        self._input_method_controller.cancel()
        self._finish_pending_key_edit_block(reason="focus_out")
        super().focusOutEvent(event)
        self._prepare_source_line_chrome_layer()
        self._publish_render_frame()
        self._schedule_caret_blink_sync(reset_cycle=False)

    def showEvent(self, event: QShowEvent) -> None:
        """Resume caret blinking when the surface becomes visible again."""

        super().showEvent(event)
        self._schedule_caret_blink_sync(reset_cycle=False)
        self._lora_feature_delegate.prewarm_visible_banners(self._layout.frame.geometry)

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop caret blinking while the surface is hidden."""

        previous_caret_rect = self._current_caret_rect()
        self._stop_caret_blink_cycle()
        self._update_caret_paint(previous_caret_rect)
        super().hideEvent(event)

    def _publish_render_frame(self) -> None:
        """Delegate complete render-frame publication to its state owner."""

        if hasattr(self, "_render_publication"):
            self._render_publication.publish()

    def _diagnostic_layer_published(self) -> None:
        """Publish a changed diagnostic layer before requesting its repaint."""

        self._publish_render_frame()
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Delegate one prepared frame and event clip to the render compositor."""

        probe_enabled = prompt_editor_probe_enabled()
        if probe_enabled:
            log_prompt_editor_probe(
                "surface.paint.begin",
                event_rect=repr(event.rect()),
                surface=surface_probe_state(self),
            )
        painter = QPainter(self.viewport())
        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            frame = self._render_frame_owner.frame
            result = self._render_compositor.draw(
                painter,
                frame,
                event_clip=QRectF(event.rect()).intersected(frame.viewport_rect),
            )
            if probe_enabled:
                log_prompt_editor_probe(
                    "surface.paint_projection_content.end",
                    result=result,
                    clip_rect=repr(event.rect()),
                    viewport_rect=repr(frame.viewport_rect),
                )
        finally:
            painter.end()
            if probe_enabled:
                log_prompt_editor_probe(
                    "surface.paint.end",
                    surface=surface_probe_state(self),
                )

    def _publish_lora_thumbnail_media(self, storage_key: str) -> None:
        """Publish relevant ready-thumbnail identity before its repaint."""

        if not self._content_media_owner.publish_thumbnail(storage_key):
            return
        self._publish_render_frame()

    def refresh_lora_thumbnail_paint(self, *, reason: str) -> None:
        """Publish thumbnail-cache reset and repaint the visible viewport."""

        if not self._content_media_owner.publish_cache_reset(reason):
            return
        self._publish_render_frame()
        viewport = self.viewport()
        repaint_rect = viewport.rect()
        self.backingFillInvalidated.emit(repaint_rect)
        viewport.update(repaint_rect)
        viewport.repaint(repaint_rect)

    def _prepare_source_line_chrome_layer(self) -> None:
        """Prepare source-line commands against the active frame and viewport."""

        if not self._source_line_chrome.enabled:
            return
        frame = self._reorder.active_frame
        self._source_line_chrome.prepare(
            geometry=frame.geometry,
            geometry_identity=id(frame.output.snapshot),
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
            cursor_position=self.cursor_position,
            focus_active=self._focus_owner_has_focus(),
        )

    def _focus_owner_has_focus(self) -> bool:
        """Return whether the prompt editor focus owner is active."""

        return self._focus_owner.focus_owner_has_focus()

    def _caret_focus_owner_has_focus(self) -> bool:
        """Return whether the owner that permits caret painting is active."""

        return self._focus_owner.caret_focus_owner_has_focus()

    def _caret_visual_state_changed(self) -> None:
        """Publish custom caret state before its scheduled repaint."""

        self._publish_render_frame()

    def _prepare_search_highlight_layer(self) -> None:
        """Prepare search commands against the current layout and viewport."""

        layout_snapshot = self._editor_state.layout
        if (
            layout_snapshot is None
            or layout_snapshot.geometry is not self._layout.frame.output.snapshot
            or not self._session.search_match_ranges
        ):
            self._search_highlight_layer.clear()
            return
        self._search_highlight_layer.prepare(
            geometry=self._layout.frame.geometry,
            layout_identity=layout_snapshot.identity,
            match_ranges=self._session.search_match_ranges,
            active_match_index=self._session.active_search_match_index,
            palette=self.palette(),
        )

    def _update_incremental_plain_text_projection_paint(
        self,
        layout_result: PromptLayoutDamage,
    ) -> None:
        """Repaint only the visual lines changed by one accepted plain-text edit."""

        viewport_rect = QRectF(self.viewport().rect())
        repaint_rect = (
            self._layout.frame.geometry.viewport.visual_line_range_viewport_rect(
                first_line_index=layout_result.first_reflowed_line_index,
                line_count=max(1, layout_result.reflowed_line_count),
                viewport_rect=viewport_rect,
                scroll_offset=self._scroll_offset(),
            )
        )
        if repaint_rect is None:
            self.backingFillInvalidated.emit(self.viewport().rect())
            self.viewport().update()
            return
        update_rect = repaint_rect.toAlignedRect().adjusted(-2, -2, 2, 2)
        self.backingFillInvalidated.emit(update_rect)
        self.viewport().update(update_rect)

    def _set_deferred_source_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Preserve raw-source caret positions while wrap reflow is pending."""

        previous_caret_rect = self._current_caret_rect()
        previous_selection = self._selection()
        self._caret_state_owner.replace_states(
            cursor_state=cursor_state,
            anchor_state=anchor_state,
            clear_caret_rect_override=True,
            reset_preferred_x=True,
        )
        self._sync_editing_session_to_caret_states()
        self._ensure_caret_visible()
        self._selection_layer_owner.refresh()
        self._diagnostic_layer_owner.refresh(reason="selection_changed")
        self._restart_caret_blink_cycle()
        if selection_paints_changed(previous_selection, self._selection()):
            self.viewport().update()
        self._update_caret_paint(previous_caret_rect)
        self.cursorPositionChanged.emit()

    def _selection(self) -> PromptProjectionSelection:
        """Return the current source-backed selection model."""

        selection = self._editing_session.selection()
        return PromptProjectionSelection(
            anchor_position=selection.anchor_position,
            cursor_position=selection.cursor_position,
        )

    @prompt_editor_work_event(PromptEditorWorkEvent.PROJECTION_REBUILD)
    def _rebuild_projection(self) -> None:
        """Rebuild the visible projection and resynchronize layout and scrollbars."""

        self._display_mode_layout_cache.clear()
        self._build_and_publish_projection()

    def _build_and_publish_projection(self) -> None:
        """Build and publish one canonical projection without cache policy changes."""

        if not qt_object_is_alive(self):
            return
        self._cancel_pending_projection_update()
        previous_cursor_state = self._caret_state_owner.cursor_state
        previous_anchor_state = self._caret_state_owner.anchor_state
        rebuild_started_at = projection_observability_started_at()
        rebuild_result = self._projection_applicator.rebuild_projection(
            self._editor_state.edit_semantic.document,
            self._editor_state.edit_semantic.render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=None,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            transient_state=PromptProjectionTransientState(),
            layout=self._layout,
            font=self.font(),
            palette=self.palette(),
            semantic_palette=semantic_palette_from_theme(),
            previous_cursor_state=previous_cursor_state,
            previous_anchor_state=previous_anchor_state,
        )
        log_projection_timing(
            "surface.rebuild_projection",
            started_at=rebuild_started_at,
            text_length=len(self._editor_state.edit_semantic.document.source_text),
            display_mode=self._display_mode.value,
            token_count=len(rebuild_result.projection_document.tokens),
            run_count=len(rebuild_result.projection_document.runs),
        )
        self._publish_projection_rebuild_result(
            rebuild_result,
            invalidation_reason="projection_rebuilt",
        )

    def _publish_projection_rebuild_result(
        self,
        rebuild_result: PromptProjectionRebuildResult,
        *,
        invalidation_reason: str,
    ) -> None:
        """Publish one freshly built or exact-restored canonical projection."""

        self._editor_state.publish_projection(rebuild_result.projection_document)
        self._last_rendered_active_span_range = rebuild_result.active_span_range
        self._diagnostic_layer_owner.clear_fragment_cache(reason=invalidation_reason)
        self._caret_state_owner.replace_states(
            cursor_state=rebuild_result.cursor_state,
            anchor_state=rebuild_result.anchor_state,
            clear_caret_rect_override=True,
            reset_preferred_x=False,
        )
        self._sync_editing_session_to_caret_states()
        self._rebuild_active_projection(commit_projection=True)
        self._lora_feature_delegate.prewarm_visible_banners(self._layout.frame.geometry)
        self._clear_transient_caret_geometry()
        self.backingFillInvalidated.emit(self.viewport().rect())
        self.viewport().update()

    def preload_visible_lora_banners(self, *, on_complete: Callable[[], None]) -> bool:
        """Preload visible LoRA banners and notify when queued work is ready."""

        return self._lora_feature_delegate.preload_visible_banners(
            self._layout.frame.geometry, on_complete=on_complete
        )

    def _decoration_accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return the emphasis ranges whose decorative parens should use accent feedback."""

        return self._emphasis.accent_ranges()

    def _apply_decoration_accent_paint_state(self) -> None:
        """Apply emphasis decoration accent changes without rebuilding layout."""

        self._refresh_projection_paint_state()
        self.viewport().update()

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_SYNC_LAYOUT)
    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Keep layout metrics in sync and optionally commit rebuilt projection freshness."""

        self._reorder.synchronize_geometry_inputs()
        self._frame_synchronizer.sync(
            display_mode=self._display_mode,
            commit_projection=commit_projection,
        )
        self._selection_layer_owner.refresh()
        self._diagnostic_layer_owner.refresh(reason="layout_synchronized")
        self._prepare_source_line_chrome_layer()
        self._prepare_search_highlight_layer()
        self._input_method_controller.refresh_render_layer()
        self._publish_render_frame()

    def _move_horizontally(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret across plain text or collapsed token boundaries."""

        self._caret_movement_controller.move_horizontally(
            self._layout.frame.geometry,
            direction,
            keep_anchor=keep_anchor,
        )

    def _move_vertically(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret vertically by adjacent visual line and preferred column."""

        self._caret_movement_controller.move_vertically(
            self._layout.frame.geometry,
            direction,
            keep_anchor=keep_anchor,
        )

    def _set_cursor_from_projection_hit(
        self,
        caret_state: PromptProjectionCaretState,
        keep_anchor: bool,
        *,
        caret_rect_override: QRectF | None = None,
    ) -> None:
        """Persist one layout-resolved caret state as the live cursor position."""

        next_anchor_state = (
            self._caret_state_owner.anchor_state if keep_anchor else caret_state
        )
        self._set_caret_states(
            cursor_state=caret_state,
            anchor_state=next_anchor_state,
            caret_rect_override=caret_rect_override,
        )

    def _current_caret_document_rect(self) -> QRectF:
        """Return the current document-local caret rect including line-affinity override."""

        transient_rect = self._valid_transient_caret_document_rect()
        if transient_rect is not None:
            self._log_transient_caret_used(operation="document_rect")
            return transient_rect
        caret_rect_override = self._caret_state_owner.caret_rect_override
        if caret_rect_override is not None:
            return caret_rect_override
        return self._layout.frame.geometry.caret.cursor_rect(
            self._caret_state_owner.cursor_state,
            scroll_offset=0.0,
        )

    def _current_caret_rect(self) -> QRectF:
        """Return the viewport-local caret rect for the current logical caret state."""

        return self._current_caret_document_rect().translated(
            0.0, -self._scroll_offset()
        )

    def _cursor_flash_time_ms(self) -> int:
        """Return the current application caret flash period in milliseconds."""

        return self._caret_visual_controller.cursor_flash_time_ms()

    def _cursor_blink_interval_ms(self) -> int:
        """Return the timer interval used to toggle one full cursor flash cycle."""

        return self._caret_visual_controller.cursor_blink_interval_ms(
            self._cursor_flash_time_ms()
        )

    def _is_caret_blink_enabled(self) -> bool:
        """Return whether the current application setting allows caret blinking."""

        return self._caret_visual_controller.is_caret_blink_enabled(
            self._cursor_flash_time_ms()
        )

    def _set_caret_blink_visible(self, visible: bool) -> None:
        """Persist one caret blink phase and repaint only when it changes."""

        self._caret_visual_controller.set_caret_blink_visible(visible)

    def _restart_caret_blink_cycle(self) -> None:
        """Make the caret visible immediately and restart the blink timer."""

        self._caret_visual_controller.restart_caret_blink_cycle(
            cursor_flash_time_ms=self._cursor_flash_time_ms()
        )

    def _stop_caret_blink_cycle(self) -> None:
        """Stop blinking and hide the custom caret until it becomes paintable again."""

        self._caret_visual_controller.stop_caret_blink_cycle()

    def _toggle_caret_blink_visibility(self) -> None:
        """Advance the caret blink phase for one timer tick."""

        self._caret_visual_controller.toggle_caret_blink_visibility()

    def _schedule_caret_blink_sync(self, *, reset_cycle: bool) -> None:
        """Resolve caret blink state after Qt finishes the current focus transition."""

        self._caret_visual_controller.schedule_caret_blink_sync(
            reset_cycle=reset_cycle,
            cursor_flash_time_ms=self._cursor_flash_time_ms,
        )

    def _sync_caret_blink_state(self, *, reset_cycle: bool) -> None:
        """Apply caret blink visibility after one focus or visibility lifecycle event."""

        self._caret_visual_controller.sync_caret_blink_state(
            reset_cycle=reset_cycle,
            cursor_flash_time_ms=self._cursor_flash_time_ms(),
        )

    def _caret_can_paint(self) -> bool:
        """Return whether the surface currently owns a visible custom caret."""

        return self._caret_visual_controller.caret_can_paint()

    def _should_paint_caret(self) -> bool:
        """Return whether the custom caret should be painted in the current frame."""

        if self._session.exact_weight_edit is not None:
            return False
        return self._caret_visual_controller.should_paint_caret()

    def _update_caret_paint(self, previous_caret_rect: QRectF | None = None) -> None:
        """Repaint the current and previous caret bounds after one visibility change."""

        self._publish_render_frame()
        self._caret_visual_controller.update_caret_paint(previous_caret_rect)

    def _ensure_caret_visible(self) -> None:
        """Scroll the viewport vertically until the caret is visible."""

        self._caret_visual_controller.ensure_caret_visible()

    def _collapse_expanded_token_if_possible(self) -> None:
        """Collapse the expanded token once caret ownership has left a still-valid span."""

        collapsed = self._session.collapse_if_cursor_left_token(
            self._editor_state.projection_semantic.document,
            selection_start=min(self.cursor_position, self.anchor_position),
            selection_end=max(self.cursor_position, self.anchor_position),
        )
        if collapsed:
            self._rebuild_projection()

    def _focused_or_hovered_token(
        self,
        *,
        prefer_hovered: bool,
    ) -> PromptProjectionToken | None:
        """Return the hovered or focused token according to the supplied preference."""

        if prefer_hovered:
            hovered_token = self.hovered_token()
            if hovered_token is not None:
                return hovered_token
        focused_token = self.focused_token()
        if focused_token is not None:
            return focused_token
        if not prefer_hovered:
            return self.hovered_token()
        return None

    def _active_span_range(self) -> tuple[int, int] | None:
        """Return the syntax range that should render as active in the projection."""

        token = self._focused_or_hovered_token(prefer_hovered=False)
        if token is not None:
            return (token.source_start, token.source_end)
        active_span = self.active_syntax_span()
        if active_span is None:
            return None
        return (active_span.start, active_span.end)

    def _visible_scroll_bar(self) -> QScrollBar:
        """Return the scrollbar that currently owns the visible scroll offset."""

        return self._wheel_handler.visible_scroll_bar()

    def _scroll_offset(self) -> float:
        """Return the active vertical scroll offset used by layout and paint."""

        return self._wheel_handler.scroll_offset()

    def _clear_pending_segment_word_selection(self) -> None:
        """Delegate pending segment-word selection clearing to pointer routing."""

        self._mouse_handler.clear_pending_segment_word_selection()

    def _emit_mouse_interaction_finished(self) -> None:
        """Emit the public signal after pointer selection has finished."""

        self.mouseInteractionFinished.emit()


__all__ = ["PromptProjectionSurface"]
