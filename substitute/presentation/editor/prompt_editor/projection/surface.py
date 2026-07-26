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

from typing import Callable, cast

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFocusEvent,
    QFontMetricsF,
    QHideEvent,
    QInputMethodEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QRegion,
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

from substitute.application.prompt_editor.diagnostics.models import PromptDiagnostic
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
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
)

from ..autocomplete_preview_state import PromptAutocompletePreviewState
from ..commands.execution import PromptEditExecution
from ..commands.source_service import PromptSourceCommandService
from ..core.state.revisions import PromptLayoutIdentity
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
from ..interactions.clipboard_history_controller import PromptClipboardHistoryActions
from ..interactions import (
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
from ..mime_data_policy import (
    mime_data_has_prompt_plain_text,
    prompt_plain_text_from_mime_data,
)
from ..qt_lifecycle import qt_object_is_alive
from .applicator import PromptProjectionApplicator, PromptProjectionRebuildResult
from .autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionHost,
    PromptAutocompletePreviewProjectionOwner,
)
from .caret_autocomplete_preview_coordinator import (
    PromptCaretAutocompletePreviewCoordinator,
    PromptCaretAutocompletePreviewHost,
)
from .caret_movement_controller import (
    PromptProjectionCaretMovementController,
    PromptProjectionCaretMovementHost,
)
from .caret_visual import (
    PromptSurfaceCaretVisualController,
    PromptSurfaceCaretVisualHost,
)
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .display_mode_layout_cache import (
    PromptProjectionDisplayModeLayoutCache,
    PromptProjectionDisplayModeLayoutIdentity,
)
from .editing_runtime import PromptProjectionEditingRuntimeFactory
from .fill_band_cache import (
    PromptFillBandRect,
    PromptProjectionFillBandBuildRequest,
    PromptProjectionFillBandCache,
    PromptProjectionFillBandCacheKey,
)
from .frame_state import (
    PromptProjectionEditorState,
    PromptProjectionFrameStatePublisher,
    PromptProjectionLayoutWidthResolver,
    build_initial_prompt_projection_state,
)
from .frame_synchronizer import PromptProjectionFrameSynchronizer
from .freshness_controller import (
    PromptProjectionFreshnessBlockers,
)
from .input_method_controller import (
    PromptInputMethodController,
    PromptInputMethodHost,
)
from ..layout.checkpoints import capture_layout_checkpoint
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
    PromptProjectionCaretPlacement,
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
    PromptProjectionTokenKind,
    PromptWeightControlIdentity,
)
from .observability import (
    log_projection_timing,
    log_reorder_drag_event,
    log_reorder_drag_timing,
    projection_observability_started_at,
    render_plan_lora_span_count,
    reorder_drag_started_at,
)
from .content_media_owner import PromptProjectionContentMediaOwner
from .prepared_frame import PromptProjectionPreparedFrame
from .region_chrome import PromptRegionChrome
from .reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from .reorder_geometry_cache_keys import (
    ReorderGeometrySnapshot,
)
from .reorder_geometry import reorder_geometry_state
from .reorder_geometry_owner import (
    PromptReorderGeometryEnvironment,
    PromptReorderGeometryOwner,
)
from .reorder_paint_snapshot_builder import PromptReorderPaintSnapshotBuilder
from .reorder_paint_snapshot_reuse import reuse_reorder_paint_snapshots
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
    placement_for_drag_rect,
)
from .reorder_preview import (
    PromptReorderPreviewState,
)
from .reorder_preview_projection_contracts import (
    PromptReorderPreviewProjectionContext,
)
from .reorder_preview_projection_owner import PromptReorderPreviewProjectionOwner
from .reorder_surface_chrome import PromptReorderSurfaceChromeSnapshot
from .reorder_surface_visual_state import (
    PromptReorderSurfaceVisualContext,
    PromptReorderSurfaceVisualPublication,
    PromptReorderSurfaceVisualStateOwner,
    empty_reorder_surface_visual_publication,
)
from .render_compositor import PromptProjectionRenderCompositor
from .render_frame import (
    PromptProjectionContentPaintMode,
    PromptReorderRenderInstrumentation,
)
from .render_frame_owner import PromptProjectionRenderFrameOwner
from .reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)
from ..geometry.models import PromptProjectionSourceLineRect
from ..geometry.selection import selection_paints_changed
from .session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptProjectionSession,
    PromptTransientNeutralEmphasisOwner,
)
from .source_line_chrome import PromptSourceLineChrome
from .search_highlight_owner import PromptSearchHighlightLayerOwner
from .refresh_geometry_signature import PromptRefreshGeometryPaintSignature
from .content_selection_owner import PromptProjectionSelectionLayerOwner
from .source_state_wiring import (
    PromptProjectionSourceStateBindings,
    build_prompt_projection_source_state_owners,
)
from .theme import qcolor_from_rgb, scene_zebra_color, semantic_palette_from_theme
from .tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
    emphasis_weight_font,
)
from .transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientInsertionOverlay,
)
from .undo_payload import PromptProjectionUndoPayload
from ..interactions.deletion_controller import (
    PromptDeletionContext,
    PromptDeletionContextProvider,
    PromptDeletionProjectionEffects,
    PromptSurfaceDeletionController,
)
from .builder import PromptProjectionBuilder

_SLOW_REORDER_PROJECTION_LAYOUT_MS = 8.0
_LOGGER = get_logger("presentation.editor.prompt_editor.projection_surface")


class PromptProjectionSurface(QAbstractScrollArea):
    """Own prompt projection editing inside a host-provided shell and scrollbar."""

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

    _EMPHASIS_FEEDBACK_PULSE_MS = 220

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
        )
        update_lora_thumbnail = self._lora_feature_delegate.update_lora_thumbnail_pixmap
        thumbnail_cache.pixmap_ready.connect(
            lambda key: update_lora_thumbnail(self._layout.frame.geometry, key)
        )
        self._focus_host: QWidget | None = None
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
        self._mouse_handler = PromptSurfaceMouseHandler(
            cast(PromptSurfaceMouseHost, self)
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
                document_effect_sink=self,
            ),
            parent=self,
            frame_state=self._frame_state,
        )
        self._source_document_adapter = source_state_owners.source_document
        self._source_commit_application = source_state_owners.source_commit_application
        self._active_projection_document = self._editor_state.projection.document
        self._reorder_preview_projection = PromptReorderPreviewProjectionOwner(
            projection_applicator=self._projection_applicator,
            thumbnail_cache=thumbnail_cache,
        )
        self._reorder_geometry_owner = PromptReorderGeometryOwner(
            environment=self._reorder_geometry_environment,
            preview_projection=self._reorder_preview_projection,
        )
        self._selection_layer_owner = PromptProjectionSelectionLayerOwner(
            frame=lambda: self._layout.frame,
            selection=self._selection,
            viewport_rect=lambda: QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset,
            preview_active=self._reorder_preview_is_active,
        )
        self._reorder_preview_paint_snapshots_by_index: dict[
            int,
            PromptReorderProjectionPaintSnapshot,
        ] = {}
        self._reorder_live_paint_snapshots_by_index: dict[
            int,
            PromptReorderProjectionPaintSnapshot,
        ] = {}
        self._reorder_paint_snapshot_exact_reuse_count = 0
        self._reorder_paint_snapshot_scroll_reuse_count = 0
        self._reorder_paint_snapshot_rebuild_count = 0
        self._reorder_surface_visual_state = PromptReorderSurfaceVisualStateOwner()
        initial_state = (
            self._editor_state.projection.document.caret_map.state_for_source_position(
                0
            )
        )
        self._cursor_state = initial_state
        self._anchor_state = initial_state
        self._editing_enabled = True
        editing_runtime = editing_runtime_factory(self)
        self._edit_execution = editing_runtime.execution
        self._source_commands = editing_runtime.source_commands
        self._clipboard_history_actions = editing_runtime.clipboard_history
        self._undo_coalescing_actions = editing_runtime.undo_coalescing
        self._input_method_controller = PromptInputMethodController(
            cast(PromptInputMethodHost, self),
            source_commands=self._source_commands,
        )
        self._deletion_controller = PromptSurfaceDeletionController(
            context_provider=cast(PromptDeletionContextProvider, self),
            projection_effects=cast(PromptDeletionProjectionEffects, self),
            source_commands=self._source_commands,
        )
        self._key_handler = PromptSurfaceKeyHandler(
            cast(PromptSurfaceKeyHost, self),
            deletion_controller=self._deletion_controller,
            clipboard_history_actions=lambda: self._clipboard_history_actions,
            undo_coalescing_actions=lambda: self._undo_coalescing_actions,
        )
        self._wheel_handler = PromptSurfaceWheelHandler(
            cast(PromptSurfaceWheelHost, self)
        )
        self._caret_visual_controller = PromptSurfaceCaretVisualController(
            cast(PromptSurfaceCaretVisualHost, self),
            is_alive=qt_object_is_alive,
            parent=self,
        )
        self._preferred_x: float | None = None
        self._caret_rect_override: QRectF | None = None
        self._skip_next_same_source_soft_wrap_move = False
        self._transient_edit_overlays = source_state_owners.transient_edit_overlays
        self._last_rendered_active_span_range: tuple[int, int] | None = None
        self._overlay_emphasis_accent_range: tuple[int, int] | None = None
        self._wheel_intent_emphasis_accent_range: tuple[int, int] | None = None
        self._pulsed_emphasis_accent_range: tuple[int, int] | None = None
        self._emphasis_feedback_timer = QTimer(self)
        self._emphasis_feedback_timer.setSingleShot(True)
        self._emphasis_feedback_timer.setInterval(self._EMPHASIS_FEEDBACK_PULSE_MS)
        self._emphasis_feedback_timer.timeout.connect(
            self._clear_pulsed_emphasis_accent_range
        )
        self._caret_visibility_prompt_state_revision: int | None = None
        self._projection_freshness_controller = source_state_owners.freshness_controller
        self._layout_width_resolver = PromptProjectionLayoutWidthResolver(
            host=self,
            viewport=self.viewport(),
            freshness=self._projection_freshness_controller,
        )
        self._autocomplete_preview_projection_owner = (
            PromptAutocompletePreviewProjectionOwner(
                cast(PromptAutocompletePreviewProjectionHost, self)
            )
        )
        self._caret_autocomplete_preview_coordinator = (
            PromptCaretAutocompletePreviewCoordinator(
                cast(PromptCaretAutocompletePreviewHost, self)
            )
        )
        self._caret_movement_controller = PromptProjectionCaretMovementController(
            cast(PromptProjectionCaretMovementHost, self)
        )
        self._edit_pipeline = source_state_owners.edit_pipeline
        self._prompt_state_applier = source_state_owners.prompt_state_applier
        self._fill_band_cache = PromptProjectionFillBandCache()
        self._diagnostic_layer_owner = PromptDiagnosticLayerOwner(
            parent=self,
            diagnostics=lambda: self._session.diagnostics,
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
        self._projection_geometry_reuse_warm_timer = QTimer(self)
        self._projection_geometry_reuse_warm_timer.setSingleShot(True)
        self._projection_geometry_reuse_warm_timer.setInterval(0)
        self._projection_geometry_reuse_warm_timer.timeout.connect(
            self._warm_projection_geometry_reuse_indexes
        )
        self._projection_geometry_reuse_warm_requested = False
        self._weight_click_handler: Callable[[QPointF], bool] | None = None
        self._weight_double_click_handler: Callable[[QPointF], bool] | None = None
        self._region_chrome = PromptRegionChrome()
        self._render_frame_owner = PromptProjectionRenderFrameOwner()
        self._render_compositor = PromptProjectionRenderCompositor()
        self._layout.frame.set_semantic_palette(semantic_palette_from_theme())
        self._frame_synchronizer = PromptProjectionFrameSynchronizer(
            host=self,
            layout=self._layout,
            applicator=self._projection_applicator,
            reorder_preview=self._reorder_preview_projection,
            frame_state=self._frame_state,
            width_resolver=self._layout_width_resolver,
            freshness=self._projection_freshness_controller,
            region_chrome=self._region_chrome,
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
        self.viewport().installEventFilter(self)
        self._install_lora_tooltip_filter()
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
    def reorder_geometry_owner(self) -> PromptReorderGeometryOwner:
        """Return the focused geometry owner for direct composition wiring."""

        return self._reorder_geometry_owner

    @property
    def anchor_position(self) -> int:
        """Return the editing-session-owned raw source selection anchor."""

        return self._editing_session.anchor_position

    def document(self) -> QTextDocument:
        """Return the plain-text source document kept for compatibility helpers."""

        return self._source_document_adapter.document()

    def can_undo(self) -> bool:
        """Return whether the custom prompt undo stack can restore a prior edit."""

        return self._editing_session.can_undo()

    def can_redo(self) -> bool:
        """Return whether the custom prompt redo stack can restore a reverted edit."""

        return self._editing_session.can_redo()

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
    def clipboard_history_actions(self) -> PromptClipboardHistoryActions:
        """Return the composed clipboard/history action owner."""

        return self._clipboard_history_actions

    def attach_external_scroll_bar(self, scroll_bar: QScrollBar) -> None:
        """Mirror layout range and scroll offset onto one host-owned scrollbar."""

        self._wheel_handler.attach_external_scroll_bar(scroll_bar)

    def attach_focus_host(self, focus_host: QWidget) -> None:
        """Store the widget whose focus should drive caret and accent visibility."""

        if self._focus_host is focus_host:
            return
        if self._focus_host is not None:
            self._focus_host.removeEventFilter(self)
        self._focus_host = focus_host
        focus_host.installEventFilter(self)
        self._schedule_caret_blink_sync(reset_cycle=False)

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
        previous_cursor_state = self._cursor_state
        previous_anchor_state = self._anchor_state
        self._display_mode = display_mode
        self._clear_reorder_projection_and_geometry_caches(
            reason="display_mode_changed"
        )
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
            self._clear_reorder_projection_and_geometry_caches(
                reason="visual_style_changed"
            )
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

        preview_frame = self._reorder_preview_projection.preview_frame
        if preview_frame is not None:
            content_height = preview_frame.output.snapshot.content_size.height()
            self._log_passive_metric_read(
                metric="content_height",
                returned_height=content_height,
                exact_reorder_preview=True,
            )
            return content_height
        committed_metrics = self._projection_freshness_controller.committed_metrics
        if self._projection_freshness_controller.can_use_committed_passive_metrics():
            assert committed_metrics is not None
            self._log_passive_metric_read(
                metric="content_height",
                committed_revision=committed_metrics.source_revision,
                returned_height=committed_metrics.content_height,
            )
            return committed_metrics.content_height
        self._flush_pending_projection_update(
            reason="content_height_initial_or_unavailable"
        )
        content_height = self._layout.frame.output.snapshot.content_size.height()
        self._log_passive_metric_read(
            metric="content_height",
            returned_height=content_height,
            forced_unavailable=True,
        )
        return content_height

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

        if self._display_mode is PromptProjectionDisplayMode.RAW:
            self._log_passive_metric_read(
                metric="visible_prompt_fill_band_rects",
                rect_count=0,
            )
            return ()
        key = PromptProjectionFillBandCacheKey(
            source_identity=(
                self._projection_freshness_controller.fill_band_source_identity(
                    current_source_identity=self._editor_state.source_identity
                )
            ),
            display_mode=self._display_mode,
            viewport_width=self.viewport().width(),
            viewport_height=self.viewport().height(),
            scroll_offset=int(round(self._scroll_offset())),
            content_width=(
                self._projection_freshness_controller.fill_band_content_width(
                    current_content_width=(
                        self._layout.frame.output.snapshot.content_size.width()
                    )
                )
            ),
            content_left_inset=self._source_line_chrome.content_left_inset,
        )
        cached_rects = self._fill_band_cache.cached_rects(key)
        rects = cached_rects
        if rects is None:
            rects = self._fill_band_cache.build_and_store(
                key,
                PromptProjectionFillBandBuildRequest(
                    source_text=(
                        self._projection_freshness_controller.fill_band_source_text(
                            committed_source_text=self._editor_state.projection.document.source_text,
                            live_source_text=self.toPlainText(),
                        )
                    ),
                    viewport_rect=QRectF(self.viewport().rect()),
                    scroll_offset=self._scroll_offset(),
                ),
                reorder_geometry=self._reorder_geometry_owner.projection_geometry,
                geometry_state=reorder_geometry_state(self._layout.frame.geometry),
            )
        self._log_passive_metric_read(
            metric="visible_prompt_fill_band_rects",
            committed_revision=key.source_identity.source_revision,
            rect_count=len(rects),
        )
        return rects

    def prompt_fill_band_color(self) -> QColor:
        """Return the alternating prompt fill color used beneath projection painting."""

        return scene_zebra_color()

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

    def set_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace the active projection-owned autocomplete preview state."""

        log_prompt_editor_probe(
            "surface.set_autocomplete_preview_state.begin",
            requested_preview=repr(preview_state),
            surface=surface_probe_state(self),
        )
        self._autocomplete_preview_projection_owner.set_preview_state(preview_state)
        log_prompt_editor_probe(
            "surface.set_autocomplete_preview_state.end",
            surface=surface_probe_state(self),
        )

    def clear_autocomplete_preview_state(self) -> None:
        """Clear any active projection-owned autocomplete preview."""

        self.set_autocomplete_preview_state(None)

    def current_autocomplete_preview_state(
        self,
    ) -> PromptAutocompletePreviewState | None:
        """Return the projection session's autocomplete preview state."""

        return self._session.autocomplete_preview

    def set_session_autocomplete_preview_state(
        self,
        preview_state: PromptAutocompletePreviewState | None,
    ) -> None:
        """Replace autocomplete preview state inside the projection session."""

        log_prompt_editor_probe(
            "surface.set_session_autocomplete_preview_state.begin",
            requested_preview=repr(preview_state),
            surface=surface_probe_state(self),
        )
        self._session.set_autocomplete_preview(preview_state)
        log_prompt_editor_probe(
            "surface.set_session_autocomplete_preview_state.end",
            surface=surface_probe_state(self),
        )

    def flush_pending_projection_for_autocomplete_preview(self) -> None:
        """Flush pending projection before autocomplete preview is applied."""

        self._flush_pending_projection_update(reason="autocomplete_preview")

    def base_projection_is_stale_for_autocomplete_preview(self) -> bool:
        """Return whether autocomplete preview would layer over stale geometry."""

        return self._projection_freshness_controller.has_stale_projection_geometry()

    def rebuild_base_projection_for_autocomplete_preview(self) -> None:
        """Rebuild base projection before autocomplete preview is applied."""

        self._rebuild_projection()

    def rebuild_active_projection_for_autocomplete_preview(self) -> None:
        """Rebuild active projection after autocomplete preview changes."""

        log_prompt_editor_probe(
            "surface.rebuild_active_projection_for_autocomplete_preview",
            surface=surface_probe_state(self),
        )
        self._rebuild_active_projection()

    def invalidate_autocomplete_preview_paint(self) -> None:
        """Request repaint for pixels that may contain autocomplete preview text."""

        log_prompt_editor_probe(
            "surface.invalidate_autocomplete_preview_paint",
            surface=surface_probe_state(self),
        )
        self.viewport().update()

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
            or self._reorder_preview_projection.is_active()
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

    def set_diagnostics(
        self,
        diagnostics: tuple[PromptDiagnostic, ...],
    ) -> None:
        """Replace transient diagnostics rendered by the projection surface."""

        if diagnostics == self._session.diagnostics:
            return
        self._clear_diagnostic_fragment_cache(reason="diagnostics_changed")
        self._session.set_diagnostics(diagnostics)
        self._diagnostic_layer_owner.refresh(reason="diagnostics_changed")

    def clear_diagnostics(self) -> None:
        """Clear transient diagnostics from the projection surface."""

        if not self._session.diagnostics:
            return
        self._clear_diagnostic_fragment_cache(reason="diagnostics_cleared")
        self._session.clear_diagnostics()
        self._diagnostic_layer_owner.refresh(reason="diagnostics_cleared")

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

        self._session.set_emphasis_adjustment_session(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Remove any active emphasis-adjustment session from the projection surface."""

        self._session.clear_emphasis_adjustment_session()

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when one exists."""

        return self._session.emphasis_adjustment_session()

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range when present."""

        return self._session.emphasis_adjustment_session_range()

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active emphasis-adjustment session owns one range."""

        return self._session.emphasis_adjustment_session_matches_range(
            content_start=content_start,
            content_end=content_end,
        )

    def prompt_weight_wheel_identity(
        self,
        token: PromptProjectionToken,
    ) -> PromptWeightControlIdentity:
        """Return stable wheel ownership identity for one prompt weight token."""

        return self._session.prompt_weight_wheel_identity(token)

    def set_reorder_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
    ) -> None:
        """Replace the active reorder preview state through the projection service."""

        started_at = reorder_drag_started_at()
        if preview_state is None:
            self._reorder_preview_paint_snapshots_by_index = {}
            self._reorder_surface_visual_state.publish(
                empty_reorder_surface_visual_publication(),
                context=self._reorder_surface_visual_context(),
            )
        self._flush_pending_projection_update(reason="set_reorder_preview_state")
        invalidation = self._reorder_preview_projection.set_preview_state(
            preview_state,
            context=PromptReorderPreviewProjectionContext.from_preview_state(
                preview_state,
                source_revision=self._editor_state.source.source_revision,
                layout_width=self._layout_width_resolver.resolve(),
                viewport_width=self.viewport().width(),
            ),
            font=self.font(),
            palette=self.palette(),
            semantic_palette=semantic_palette_from_theme(),
            live_projection_document=self._editor_state.projection.document,
            live_projection_frame=self._layout.frame,
        )
        if invalidation.clear_all_geometry_reason is not None:
            self._clear_reorder_geometry_caches(
                reason=invalidation.clear_all_geometry_reason
            )
        if invalidation.clear_base_drag_geometry_reason is not None:
            self._clear_base_drag_geometry_caches(
                reason=invalidation.clear_base_drag_geometry_reason
            )
        self._sync_layout_state()
        self.viewport().update()
        log_reorder_drag_timing(
            "surface.set_reorder_preview_state",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            reason=(
                "" if preview_state is None else preview_state.instrumentation_reason
            ),
            has_preview_state=preview_state is not None,
            has_base_drag=(
                False
                if preview_state is None
                else preview_state.base_drag_snapshot is not None
            ),
            dragged_chip_index=(
                None if preview_state is None else preview_state.dragged_chip_index
            ),
            ordered_count=(
                0 if preview_state is None else len(preview_state.ordered_chip_indices)
            ),
        )

    def clear_reorder_preview_state(self) -> None:
        """Clear any active reorder preview state and resume live-text painting."""

        self.set_reorder_preview_state(None)

    def reset_reorder_geometry_cache_counters(self) -> None:
        """Reset per-gesture reorder geometry and projection cache counters."""

        self._reorder_geometry_owner.reset_counters()
        self._reorder_preview_projection.reset_counters()
        self._reorder_paint_snapshot_exact_reuse_count = 0
        self._reorder_paint_snapshot_scroll_reuse_count = 0
        self._reorder_paint_snapshot_rebuild_count = 0

    def reorder_geometry_cache_counters(self) -> dict[str, object]:
        """Return per-gesture reorder cache counters for diagnostics summaries."""

        return {
            **self._reorder_geometry_owner.counters(),
            **self._reorder_preview_projection.counters(),
            "paint_snapshot_exact_reuse_count": (
                self._reorder_paint_snapshot_exact_reuse_count
            ),
            "paint_snapshot_scroll_reuse_count": (
                self._reorder_paint_snapshot_scroll_reuse_count
            ),
            "paint_snapshot_rebuild_count": self._reorder_paint_snapshot_rebuild_count,
        }

    def _clear_reorder_geometry_caches(self, *, reason: str) -> None:
        """Invalidate all reorder geometry caches with prompt-safe diagnostics."""

        self._reorder_geometry_owner.clear_base_drag(reason=reason)
        self._reorder_geometry_owner.clear_preview(reason=reason)

    def _clear_reorder_projection_and_geometry_caches(self, *, reason: str) -> None:
        """Invalidate reorder projection and geometry caches after metric changes."""

        self._reorder_preview_projection.clear_projection_cache(reason=reason)
        self._reorder_geometry_owner.clear_live(reason=reason)
        self._clear_reorder_geometry_caches(reason=reason)

    def _clear_base_drag_geometry_caches(self, *, reason: str) -> None:
        """Invalidate stable drag-base chip and placement geometry caches."""

        self._reorder_geometry_owner.clear_base_drag(reason=reason)

    def _clear_preview_chip_geometry_cache(self, *, reason: str) -> None:
        """Invalidate cached preview chip geometry snapshots."""

        self._reorder_geometry_owner.clear_preview(reason=reason)

    def _reorder_geometry_environment(
        self,
        reason: str,
    ) -> PromptReorderGeometryEnvironment:
        """Publish one coherent live frame and viewport geometry environment."""

        if reason:
            self._flush_pending_projection_update(reason=reason)
        return PromptReorderGeometryEnvironment(
            live_source_text=(
                self._editor_state.projection_semantic.document.source_text
            ),
            live_frame=self._layout.frame,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
            layout_width=self._layout_width_resolver.resolve(),
        )

    def reorder_preview_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return wrapped preview fragments for one raw preview source range."""

        if self._reorder_preview_projection.preview_frame is None:
            return ()
        started_at = reorder_drag_started_at()
        self._flush_pending_projection_update(reason="reorder_preview_fragments")
        fragments = self._reorder_preview_projection.preview_fragments(
            start=start,
            end=end,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
        )
        preview_state = self._reorder_preview_projection.preview_state
        log_reorder_drag_timing(
            "surface.reorder_preview_fragments",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            start=start,
            end=end,
            range_length=end - start,
            fragment_count=len(fragments),
        )
        return fragments

    def reorder_live_chip_geometry_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Adapt the public surface query to the focused geometry owner."""

        return self._reorder_geometry_owner.live_chip_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Adapt the public surface query to the focused geometry owner."""

        return self._reorder_geometry_owner.preview_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned live paint snapshots for visible reorder chips."""

        self._flush_pending_projection_update(reason="reorder_live_chip_visuals")
        snapshots = self._reorder_chip_projection_paint_snapshots(
            projection_frame=self._layout.frame,
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            preview_generation=None,
            mode="live",
            previous_snapshots_by_chip_index=(
                self._reorder_live_paint_snapshots_by_index
            ),
            chip_indices=None,
        )
        self._reorder_live_paint_snapshots_by_index = snapshots
        return snapshots

    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        chip_indices: frozenset[int] | None = None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned preview paint snapshots for visible reorder chips."""

        preview_frame = self._reorder_preview_projection.preview_frame
        if preview_frame is None:
            return {}
        self._flush_pending_projection_update(reason="reorder_preview_chip_visuals")
        snapshots = self._reorder_chip_projection_paint_snapshots(
            projection_frame=preview_frame,
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            preview_generation=self._reorder_preview_generation(),
            mode="preview",
            previous_snapshots_by_chip_index=(
                self._reorder_preview_paint_snapshots_by_index
            ),
            chip_indices=chip_indices,
        )
        self._reorder_preview_paint_snapshots_by_index = snapshots
        return snapshots

    def _reorder_chip_projection_paint_snapshots(
        self,
        *,
        projection_frame: PromptProjectionPreparedFrame,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        preview_generation: int | None,
        mode: str,
        previous_snapshots_by_chip_index: dict[
            int,
            PromptReorderProjectionPaintSnapshot,
        ],
        chip_indices: frozenset[int] | None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Build projection paint snapshots using the current viewport identity."""

        viewport_rect = QRectF(self.viewport().rect())
        scroll_offset = self._scroll_offset()
        keys_by_chip_index: dict[int, PromptReorderProjectionSnapshotKey] = {}
        source_ranges_by_chip_index: dict[int, tuple[tuple[int, int], ...]] = {}
        for (
            segment_index,
            geometry,
        ) in chip_geometry_snapshot.geometries_by_chip_index.items():
            if chip_indices is not None and segment_index not in chip_indices:
                continue
            source_ranges = chip_owned_ranges_by_index.get(segment_index, ())
            if not source_ranges:
                continue
            keys_by_chip_index[segment_index] = PromptReorderProjectionSnapshotKey(
                source_revision=self._editor_state.source.source_revision,
                viewport_rect=self.viewport().rect(),
                scroll_offset=int(round(scroll_offset)),
                font_key=self.font().toString(),
                palette_key=int(self.palette().cacheKey()),
                preview_generation=preview_generation,
                geometry_generation=geometry.geometry_id.visual_revision,
                segment_index=segment_index,
                mode=mode,
            )
            source_ranges_by_chip_index[segment_index] = source_ranges
        reuse = reuse_reorder_paint_snapshots(
            keys_by_chip_index,
            previous_snapshots_by_chip_index=previous_snapshots_by_chip_index,
        )
        rebuilt_snapshots = PromptReorderPaintSnapshotBuilder(
            projection_frame.paint_input
        ).build_many(
            keys_by_chip_index=reuse.rebuild_keys_by_chip_index,
            source_ranges_by_chip_index=source_ranges_by_chip_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        snapshots = dict(reuse.snapshots_by_chip_index)
        snapshots.update(rebuilt_snapshots)
        self._reorder_paint_snapshot_exact_reuse_count += reuse.exact_reuse_count
        self._reorder_paint_snapshot_scroll_reuse_count += reuse.scroll_reuse_count
        self._reorder_paint_snapshot_rebuild_count += len(rebuilt_snapshots)
        return snapshots

    def _reorder_preview_generation(self) -> int | None:
        """Return the active preview identity used by visual snapshots."""

        preview_state = self._reorder_preview_projection.preview_state
        if preview_state is None:
            return None
        return id(preview_state.preview_snapshot)

    def reorder_preview_cursor_rect(self, position: int) -> QRectF:
        """Return the preview caret rect for one raw preview source position."""

        if (
            self._reorder_preview_projection.preview_frame is None
            or self._reorder_preview_projection.preview_document is None
        ):
            return QRectF()
        started_at = reorder_drag_started_at()
        self._flush_pending_projection_update(reason="reorder_preview_cursor_rect")
        cursor_rect = self._reorder_preview_projection.preview_cursor_rect(
            position=position,
            scroll_offset=self._scroll_offset(),
        )
        preview_state = self._reorder_preview_projection.preview_state
        log_reorder_drag_timing(
            "surface.reorder_preview_cursor_rect",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            position=position,
            rect_left=f"{cursor_rect.left():.2f}",
            rect_top=f"{cursor_rect.top():.2f}",
            rect_width=f"{cursor_rect.width():.2f}",
            rect_height=f"{cursor_rect.height():.2f}",
        )
        return cursor_rect

    def reorder_base_drag_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return wrapped fragments for one raw source range from the stable drag base."""

        if self._reorder_preview_projection.base_drag_frame is None:
            return ()
        started_at = reorder_drag_started_at()
        fragments = self._reorder_preview_projection.base_drag_fragments(
            start=start,
            end=end,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
        )
        preview_state = self._reorder_preview_projection.preview_state
        log_reorder_drag_timing(
            "surface.reorder_base_drag_fragments",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            start=start,
            end=end,
            range_length=end - start,
            fragment_count=len(fragments),
        )
        return fragments

    def reorder_base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Adapt the public surface query to the focused geometry owner."""

        return self._reorder_geometry_owner.base_drag_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_base_drag_cursor_rect(self, position: int) -> QRectF:
        """Return the stable drag-base caret rect for one raw preview source position."""

        if (
            self._reorder_preview_projection.base_drag_frame is None
            or self._reorder_preview_projection.base_drag_document is None
        ):
            return QRectF()
        started_at = reorder_drag_started_at()
        cursor_rect = self._reorder_preview_projection.base_drag_cursor_rect(
            position=position,
            scroll_offset=self._scroll_offset(),
        )
        preview_state = self._reorder_preview_projection.preview_state
        log_reorder_drag_timing(
            "surface.reorder_base_drag_cursor_rect",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            position=position,
            rect_left=f"{cursor_rect.left():.2f}",
            rect_top=f"{cursor_rect.top():.2f}",
            rect_width=f"{cursor_rect.width():.2f}",
            rect_height=f"{cursor_rect.height():.2f}",
        )
        return cursor_rect

    def reorder_base_drag_placement_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderPlacementSnapshot:
        """Adapt the public surface query to the focused geometry owner."""

        return self._reorder_geometry_owner.base_drag_placement_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def reorder_live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Adapt the public surface query to the focused geometry owner."""

        return self._reorder_geometry_owner.live_placement_snapshot(
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
        )

    def reorder_placement_at_rect(
        self,
        drag_rect: QRectF,
        *,
        snapshot: PromptReorderPlacementSnapshot,
        active_placement_id: PromptReorderPlacementId | None,
    ) -> PromptReorderPlacementGeometry | None:
        """Return the projection-owned placement selected by one drag intent rect."""

        preview_state = self._reorder_preview_projection.preview_state
        started_at = reorder_drag_started_at()
        placement = placement_for_drag_rect(
            snapshot,
            drag_rect,
            active_placement_id=active_placement_id,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
        )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_placement_at_rect",
            started_at=started_at,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            placement_count=len(snapshot.placements),
            selected=placement is not None,
        )
        if elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.placement_hit_test",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                placement_count=len(snapshot.placements),
                selected=placement is not None,
            )
        return placement

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
            self._cursor_state.token_id
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

        self._insert_viewport_text(
            text,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
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
            reorder_preview_active=self._reorder_preview_projection.is_active(),
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
        if self._reorder_preview_projection.preview_state is not None:
            self._clear_reorder_projection_and_geometry_caches(reason="source_changed")
        if clear_diagnostic_fragment_cache:
            self._clear_diagnostic_fragment_cache(reason="source_changed")
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

    def force_collapse_expanded_token(self) -> None:
        """Collapse any expanded projection token after an explicit syntax commit."""

        if self._session.expanded_source_range is None:
            return
        self._session.expanded_source_range = None
        self._rebuild_projection()

    def has_stale_projection_geometry(self) -> bool:
        """Return whether layout metrics still describe an older source snapshot."""

        return self._projection_freshness_controller.has_stale_projection_geometry()

    def _log_passive_metric_read(
        self,
        *,
        metric: str,
        committed_revision: int | None = None,
        returned_height: float | None = None,
        rect_count: int | None = None,
        exact_reorder_preview: bool = False,
        forced_unavailable: bool = False,
    ) -> None:
        """Preserve the removed passive-metric diagnostic hook."""

        del (
            metric,
            committed_revision,
            returned_height,
            rect_count,
            exact_reorder_preview,
            forced_unavailable,
        )

    def set_weight_double_click_handler(
        self,
        handler: Callable[[QPointF], bool] | None,
    ) -> None:
        """Register one number-only double-click interceptor before raw token expansion."""

        self._weight_double_click_handler = handler

    def set_weight_click_handler(
        self,
        handler: Callable[[QPointF], bool] | None,
    ) -> None:
        """Register one number-only click interceptor used to recognize exact-edit clicks."""

        self._weight_click_handler = handler

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

    def set_overlay_emphasis_accent_range(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Reflect overlay-owned emphasis visibility back into projected paren accenting."""

        if outer_range == self._overlay_emphasis_accent_range:
            return
        self._overlay_emphasis_accent_range = outer_range
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._apply_decoration_accent_paint_state()

    def set_wheel_intent_emphasis_accent_range(
        self,
        outer_range: tuple[int, int] | None,
    ) -> None:
        """Reflect hover dwell readiness back into projected paren accenting."""

        if outer_range == self._wheel_intent_emphasis_accent_range:
            return
        self._wheel_intent_emphasis_accent_range = outer_range
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._apply_decoration_accent_paint_state()

    def pulse_emphasis_feedback(
        self,
        *,
        outer_start: int,
        outer_end: int,
    ) -> None:
        """Accent one emphasis shell briefly after non-hover adjustments."""

        self._pulsed_emphasis_accent_range = (outer_start, outer_end)
        self._emphasis_feedback_timer.start()
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._apply_decoration_accent_paint_state()

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Project a temporary neutral emphasis shell over plain source content."""

        self._session.set_transient_neutral_emphasis(
            content_start=content_start,
            content_end=content_end,
            owner=owner,
        )
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            if not self._try_apply_current_session_projection_paint_state():
                self._rebuild_projection()

    def clear_transient_neutral_emphasis(self) -> None:
        """Remove any temporary neutral emphasis shell from the live projection."""

        if self._session.transient_neutral_emphasis is None:
            return
        self._session.clear_transient_neutral_emphasis()
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._rebuild_projection()

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Remove the transient neutral shell only when overlay interaction owns it."""

        if (
            self._session.transient_neutral_emphasis_owner()
            is not PromptTransientNeutralEmphasisOwner.OVERLAY
        ):
            return
        self._session.clear_overlay_owned_transient_neutral_emphasis()
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._rebuild_projection()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the content range currently owned by a temporary neutral shell."""

        return self._session.transient_neutral_emphasis_range()

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the current transient neutral shell when present."""

        return self._session.transient_neutral_emphasis_owner()

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

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Place the caret at one projected emphasis-content boundary when present."""

        token = next(
            (
                candidate
                for candidate in self._editor_state.projection.document.tokens
                if candidate.kind is PromptProjectionTokenKind.EMPHASIS
                and candidate.supports_text_content_navigation
                and candidate.content_range == (content_start, content_end)
            ),
            None,
        )
        if token is None:
            return False

        token_slot = content_end - content_start if prefer_end else 0
        source_position = content_end if prefer_end else content_start
        boundary_state = PromptProjectionCaretState(
            source_position=source_position,
            placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
            token_id=token.token_id,
            token_slot=token_slot,
        )
        self._set_caret_states(
            cursor_state=boundary_state,
            anchor_state=boundary_state,
        )
        return True

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start one projection-owned exact edit session for a weighted token."""

        if (
            token.kind
            not in {
                PromptProjectionTokenKind.EMPHASIS,
                PromptProjectionTokenKind.LORA,
            }
            or token.value_text is None
            or token.content_start is None
            or token.content_end is None
        ):
            return
        slot_width = self._exact_weight_edit_slot_width(token)
        self._session.start_exact_weight_edit(
            token_id=token.token_id,
            synthetic=token.synthetic,
            outer_start=token.source_start,
            outer_end=token.source_end,
            content_start=token.content_start,
            content_end=token.content_end,
            original_value_text=token.value_text,
            buffer_text=token.value_text,
            slot_width=slot_width,
            caret_index=len(token.value_text),
            select_all=True,
        )
        self._rebuild_projection()

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update the active projection-owned exact weight buffer and rebuild immediately."""

        if self._session.exact_weight_edit is None:
            return
        self._session.update_exact_weight_edit(
            buffer_text=buffer_text,
            caret_index=caret_index,
            select_all=select_all,
        )
        self._rebuild_projection()

    def clear_exact_weight_edit(self) -> None:
        """Clear any active projection-owned exact weight edit session."""

        if self._session.exact_weight_edit is None:
            return
        self._session.clear_exact_weight_edit()
        self._rebuild_projection()

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the currently projected weighted token that owns exact edit mode."""

        token_id = self._session.exact_weight_edit_token_id()
        if token_id is not None:
            token = self._editor_state.projection.document.token_by_id(token_id)
            if token is not None:
                return token
        edit_state = self._session.exact_weight_edit
        if edit_state is None:
            return None
        return next(
            (
                token
                for token in self._editor_state.projection.document.tokens
                if token.kind
                in {
                    PromptProjectionTokenKind.EMPHASIS,
                    PromptProjectionTokenKind.LORA,
                }
                and token.content_start == edit_state.content_start
                and token.content_end == edit_state.content_end
            ),
            None,
        )

    def exact_weight_edit_active(self) -> bool:
        """Return whether the surface currently owns an exact weight edit session."""

        return self._session.exact_weight_edit is not None

    def _exact_weight_edit_slot_width(self, token: PromptProjectionToken) -> float:
        """Capture the rendered width visible when exact edit begins."""

        weight_rect = self.token_weight_text_rect(token)
        if weight_rect is not None and weight_rect.width() > 0.0:
            return weight_rect.width()
        weight_metrics = QFontMetricsF(emphasis_weight_font(self.font()))
        return max(0.0, weight_metrics.horizontalAdvance(token.value_text or ""))

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

        active_frame = (
            self._reorder_preview_projection.preview_frame or self._layout.frame
        )
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

    def set_clipboard_history_cursor_state(
        self,
        cursor_state: PromptCursorState,
    ) -> None:
        """Apply a clipboard/history cursor state to projection caret state."""

        self.set_cursor_positions(
            cursor_position=cursor_state.cursor_position,
            anchor_position=cursor_state.anchor_position,
        )

    def _insert_viewport_text(
        self,
        text: str,
        *,
        origin: PromptSourceEditOrigin = PromptSourceEditOrigin.TYPED,
    ) -> None:
        """Replace the current raw selection with plain text."""

        if not self._editing_enabled:
            return
        if text == " ":
            self._move_space_at_emphasis_weight_boundary()
        selection = self._selection()
        self._replace_viewport_range(
            selection.start,
            selection.end,
            text,
            origin=origin,
        )

    def _move_space_at_emphasis_weight_boundary(self) -> None:
        """Place Space after an emphasis token when caret sits before its weight."""

        if (
            not self._selection().is_empty
            or self.cursor_position != self.anchor_position
        ):
            return
        for token in self._editor_state.projection.document.tokens:
            if (
                token.kind is PromptProjectionTokenKind.EMPHASIS
                and token.content_end == self.cursor_position
                and token.value_text is not None
            ):
                self.set_cursor_positions(
                    cursor_position=token.source_end,
                    anchor_position=token.source_end,
                )
                return

    def _delete_viewport_selection(self) -> None:
        """Delete the currently selected raw prompt source text."""

        if not self._editing_enabled:
            return
        selection = self._editing_session.selection()
        if selection.is_empty:
            return
        self._finish_pending_key_edit_block(reason="delete_selection")
        self._replace_viewport_range(selection.start, selection.end, "")

    def deletion_context(self) -> PromptDeletionContext:
        """Capture the immutable state consumed by deletion resolution."""

        token = self.focused_token()
        return PromptDeletionContext(
            source_text=self._editing_session.source_text,
            cursor_position=self.cursor_position,
            cursor_state=self._cursor_state,
            anchor_state=self._anchor_state,
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
            cursor_position=self._cursor_state.source_position,
            anchor_position=self._anchor_state.source_position,
        )

    def _mark_source_edit_horizontal_movement_origin(self) -> None:
        """Make the next horizontal move leave same-source wrap affinity after edits."""

        self._skip_next_same_source_soft_wrap_move = True

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
            self._cursor_state == resolved_cursor_state
            and self._anchor_state == resolved_anchor_state
            and self._caret_rect_override == caret_rect_override
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
        self._cursor_state = resolved_cursor_state
        self._anchor_state = resolved_anchor_state
        self._caret_rect_override = (
            QRectF(caret_rect_override) if caret_rect_override is not None else None
        )
        if reset_preferred_x:
            self._preferred_x = None
        self._skip_next_same_source_soft_wrap_move = False
        if collapse_expanded_token and self._session.expanded_source_range is not None:
            self._collapse_expanded_token_if_possible()
        self._caret_autocomplete_preview_coordinator.reconcile_after_caret_state_change(
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

        if event.type() == QEvent.Type.MouseMove:
            mouse_event = cast(QMouseEvent, event)
            self._mouse_handler.update_hovered_token(mouse_event.position())
        elif event.type() == QEvent.Type.DragEnter:
            self._accept_or_ignore_prompt_mime_event(cast(QDragEnterEvent, event))
            return True
        elif event.type() == QEvent.Type.DragMove:
            self._accept_or_ignore_prompt_mime_event(cast(QDragMoveEvent, event))
            return True
        elif event.type() == QEvent.Type.Drop:
            self._drop_prompt_mime_text(
                cast(QDropEvent, event),
                viewport_position=cast(QDropEvent, event).position().toPoint(),
            )
            return True
        elif event.type() == QEvent.Type.Leave:
            self._mouse_handler.clear_hovered_token(update=False)
            self._wheel_handler.clear_boundary_spill()
            self.viewport().update()
        return super().viewportEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Mirror hover tracking when tests send events directly to the inner viewport."""

        if watched is self.viewport():
            if event.type() == QEvent.Type.DragEnter:
                self._accept_or_ignore_prompt_mime_event(cast(QDragEnterEvent, event))
                return True
            if event.type() == QEvent.Type.DragMove:
                self._accept_or_ignore_prompt_mime_event(cast(QDragMoveEvent, event))
                return True
            if event.type() == QEvent.Type.Drop:
                self._drop_prompt_mime_text(
                    cast(QDropEvent, event),
                    viewport_position=cast(QDropEvent, event).position().toPoint(),
                )
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                return self._mouse_handler.handle_viewport_mouse_press(
                    cast(QMouseEvent, event),
                    self._layout.frame,
                    viewport_position=cast(QMouseEvent, event).position(),
                )
            if event.type() == QEvent.Type.MouseMove:
                return self._mouse_handler.handle_viewport_mouse_move(
                    cast(QMouseEvent, event),
                    self._layout.frame,
                    viewport_position=cast(QMouseEvent, event).position(),
                )
            if event.type() == QEvent.Type.MouseButtonRelease:
                return self._mouse_handler.handle_viewport_mouse_release(
                    cast(QMouseEvent, event)
                )
            if event.type() == QEvent.Type.MouseButtonDblClick:
                return self._mouse_handler.handle_viewport_mouse_double_click(
                    cast(QMouseEvent, event),
                    self._layout.frame,
                    viewport_position=cast(QMouseEvent, event).position(),
                )
            if event.type() == QEvent.Type.Wheel:
                wheel_event = cast(QWheelEvent, event)
                self._mouse_handler.update_hovered_token(wheel_event.position())
                result = self.handle_prompt_wheel_scroll(wheel_event)
                if result is PromptWheelScrollResult.CONSUMED:
                    wheel_event.accept()
                    return True
                wheel_event.ignore()
                return False
            elif event.type() == QEvent.Type.Leave:
                self._mouse_handler.clear_hovered_token(update=False)
                self._wheel_handler.clear_boundary_spill()
                self.viewport().update()
        elif watched is self._focus_host:
            if event.type() == QEvent.Type.FocusIn:
                self._prepare_source_line_chrome_layer()
                self._schedule_caret_blink_sync(reset_cycle=True)
            elif event.type() in {QEvent.Type.FocusOut, QEvent.Type.Hide}:
                self._prepare_source_line_chrome_layer()
                self._schedule_caret_blink_sync(reset_cycle=False)
            elif event.type() == QEvent.Type.Show:
                self._prepare_source_line_chrome_layer()
                self._schedule_caret_blink_sync(reset_cycle=False)
        return super().eventFilter(watched, event)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:  # noqa: N802
        """Return whether external MIME data may become prompt source text."""

        return mime_data_has_prompt_plain_text(source)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """Insert prompt-safe MIME text through the source mutation owner."""

        text = prompt_plain_text_from_mime_data(source)
        if text is None:
            return
        self._insert_viewport_text(text, origin=PromptSourceEditOrigin.PASTE)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept only prompt-safe plain text drag payloads."""

        self._accept_or_ignore_prompt_mime_event(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep rejecting non-text drag payloads while the pointer moves."""

        self._accept_or_ignore_prompt_mime_event(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Insert prompt-safe dropped text and reject rich/file payloads."""

        self._drop_prompt_mime_text(
            event,
            viewport_position=self.viewport().mapFrom(
                self,
                event.position().toPoint(),
            ),
        )

    def _accept_or_ignore_prompt_mime_event(
        self,
        event: QDragEnterEvent | QDragMoveEvent,
    ) -> None:
        """Accept one drag event only when it carries prompt-safe plain text."""

        if mime_data_has_prompt_plain_text(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def _drop_prompt_mime_text(
        self,
        event: QDropEvent,
        *,
        viewport_position: QPoint,
    ) -> None:
        """Insert dropped MIME text at one projection-viewport position."""

        text = prompt_plain_text_from_mime_data(event.mimeData())
        if text is None:
            event.ignore()
            return
        self.cursorForPosition(viewport_position)
        self._insert_viewport_text(text, origin=PromptSourceEditOrigin.PASTE)
        event.acceptProposedAction()

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_RESIZE_EVENT)
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the projection layout width in sync with the viewport."""

        super().resizeEvent(event)
        self._preferred_x = None
        self._caret_rect_override = None
        if not self._projection_freshness_controller.has_stale_projection_geometry():
            self._clear_transient_caret_geometry()
        self._clear_reorder_projection_and_geometry_caches(reason="resize")
        self._clear_diagnostic_fragment_cache(reason="resize")
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
        """Publish every prepared layer and cache input before repaint."""

        if not hasattr(self, "_render_frame_owner") or not qt_object_is_alive(self):
            return
        viewport = self.viewport()
        if not qt_object_is_alive(viewport):
            return
        viewport_rect = QRectF(viewport.rect())
        scroll_offset = self._scroll_offset()
        preview_frame = self._reorder_preview_projection.preview_frame
        paint_snapshot = self._editor_state.current_paint
        if preview_frame is not None:
            paint_input = preview_frame.paint_input
            metrics = preview_frame.output.configuration.metrics
            paint_identity = None
            content_mode = PromptProjectionContentPaintMode.DIRECT_REORDER_PREVIEW
            reorder_mode = "preview"
            preview_visible_region = self._preview_visible_region()
            preview_state = self._reorder_preview_projection.preview_state
            reorder_instrumentation = PromptReorderRenderInstrumentation(
                gesture_id=(
                    None
                    if preview_state is None
                    else preview_state.instrumentation_gesture_id
                ),
                event_id=(
                    None
                    if preview_state is None
                    else preview_state.instrumentation_event_id
                ),
                line_count=preview_frame.output.snapshot.line_count(),
                text_fragment_count=(
                    preview_frame.output.snapshot.text_fragment_count()
                ),
                inline_object_count=(
                    preview_frame.output.snapshot.inline_object_fragment_count()
                ),
            )
        else:
            paint_input = self._layout.frame.paint_input
            metrics = self._layout.frame.output.configuration.metrics
            paint_identity = None if paint_snapshot is None else paint_snapshot.identity
            if self._session.autocomplete_preview is not None:
                content_mode = (
                    PromptProjectionContentPaintMode.DIRECT_AUTOCOMPLETE_PREVIEW
                )
            elif paint_identity is None:
                content_mode = PromptProjectionContentPaintMode.DIRECT_UNPREPARED
            else:
                content_mode = PromptProjectionContentPaintMode.CACHED
            reorder_mode = "live"
            preview_visible_region = None
            reorder_instrumentation = None
        self._input_method_controller.refresh_render_layer()
        caret_visible = (
            preview_frame is None
            and not self._input_method_controller.is_composing
            and self._should_paint_caret()
        )
        caret_rect = self._current_caret_rect() if caret_visible else QRectF()
        self._render_frame_owner.publish(
            paint_input=paint_input,
            paint_identity=paint_identity,
            content_media_identity=self._content_media_owner.identity,
            content_mode=content_mode,
            selection_layer=self._selection_layer_owner.layer,
            source_line_layer=self._source_line_chrome.layer,
            region_layer=self._region_chrome.active_snapshot,
            reorder_layer=self._fresh_reorder_surface_chrome(reorder_mode),
            search_layer=self._search_highlight_layer.layer,
            diagnostic_layer=self._diagnostic_layer_owner.layer,
            input_method_layer=self._input_method_controller.render_layer,
            overlays=self._transient_edit_overlays,
            freshness_is_stale_safe=(
                self._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_identity=self._editor_state.source_identity,
            metrics=metrics,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            device_pixel_ratio=float(viewport.devicePixelRatioF()),
            font=self.font(),
            palette=self.palette(),
            caret_visible=caret_visible,
            caret_rect=caret_rect,
            preview_content_visible_region=preview_visible_region,
            reorder_instrumentation=reorder_instrumentation,
        )

    def _diagnostic_layer_published(self) -> None:
        """Publish a changed diagnostic layer before requesting its repaint."""

        self._publish_render_frame()
        self.viewport().update()

    def _fresh_reorder_surface_chrome(
        self,
        mode: str,
    ) -> PromptReorderSurfaceChromeSnapshot | None:
        """Return reorder chrome only when it matches the pending render frame."""

        snapshot = self._reorder_surface_visual_state.state.chrome_snapshot
        if snapshot is None or not snapshot.matches(
            source_revision=self._editor_state.source.source_revision,
            viewport_rect=self.viewport().rect(),
            scroll_offset=int(round(self._scroll_offset())),
            preview_generation=(
                self._reorder_preview_generation() if mode == "preview" else None
            ),
            mode=mode,
        ):
            return None
        return snapshot

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
        frame = self._reorder_preview_projection.preview_frame or self._layout.frame
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

        focus_owner = self._focus_host or self
        return focus_owner.hasFocus()

    def _caret_focus_owner_has_focus(self) -> bool:
        """Return whether the owner that permits caret painting is active."""

        focus_owner = self._focus_host or self.parentWidget() or self
        return focus_owner.hasFocus()

    def _caret_visual_state_changed(self) -> None:
        """Publish custom caret state before its scheduled repaint."""

        self._publish_render_frame()

    def _reorder_preview_is_active(self) -> bool:
        """Return whether a reorder preview currently suppresses the live caret."""

        return self._reorder_preview_projection.is_active()

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

    def _transient_insertion_overlay_viewport_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
    ) -> QRectF:
        """Return the viewport-local repaint rect for one transient text overlay."""

        return self._transient_edit_overlays.insertion_overlay_viewport_rect(
            overlay,
            metrics=self._layout.frame.output.configuration.metrics,
            scroll_offset=self._scroll_offset(),
        )

    def _transient_insertion_overlay_document_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
    ) -> QRectF:
        """Return the document-local paint rect for one transient text overlay."""

        return self._transient_edit_overlays.insertion_overlay_document_rect(
            overlay,
            metrics=self._layout.frame.output.configuration.metrics,
        )

    def _update_transient_insertion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
    ) -> None:
        """Repaint transient typed text whenever the overlay grows or clears."""

        repaint_rect = self._transient_edit_overlays.insertion_overlay_repaint_rect(
            previous_overlay=previous_overlay,
            next_overlay=next_overlay,
            metrics=self._layout.frame.output.configuration.metrics,
            scroll_offset=self._scroll_offset(),
        )
        self._publish_render_frame()
        if repaint_rect is None:
            return
        self.viewport().update(repaint_rect.toAlignedRect())

    def _transient_deletion_overlay_viewport_rects(
        self,
        overlay: PromptProjectionTransientDeletionOverlay,
    ) -> tuple[QRectF, ...]:
        """Return viewport-local erase rects for one transient deletion."""

        return self._transient_edit_overlays.deletion_overlay_viewport_rects(
            overlay,
            scroll_offset=self._scroll_offset(),
        )

    def _transient_deletion_overlay_erase_rects(
        self,
        overlay: PromptProjectionTransientDeletionOverlay,
    ) -> tuple[QRectF, ...]:
        """Return expanded viewport-local deletion erase bands grouped by visual row."""

        return self._transient_edit_overlays.deletion_overlay_erase_rects(
            overlay,
            scroll_offset=self._scroll_offset(),
        )

    def _update_transient_deletion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Repaint transient erased text whenever deletion state changes."""

        repaint_rect = self._transient_edit_overlays.deletion_overlay_repaint_rect(
            previous_overlay=previous_overlay,
            next_overlay=next_overlay,
            scroll_offset=self._scroll_offset(),
        )
        self._publish_render_frame()
        if repaint_rect is None:
            return
        self.viewport().update(repaint_rect.toAlignedRect())

    def _schedule_projection_geometry_reuse_warm(self, *, reason: str) -> None:
        """Queue emphasis geometry-reuse cache warming outside source replacement."""

        _ = reason
        if not qt_object_is_alive(self):
            return
        if self._display_mode is not PromptProjectionDisplayMode.PROJECTED:
            return
        if self._projection_geometry_reuse_warm_requested:
            return
        self._projection_geometry_reuse_warm_requested = True
        self._projection_geometry_reuse_warm_timer.start(0)

    def _warm_projection_geometry_reuse_indexes(self) -> None:
        """Populate layout indexes used by repeated emphasis geometry checks."""

        self._projection_geometry_reuse_warm_requested = False
        if not qt_object_is_alive(self):
            return
        self._layout.frame.output.snapshot.prewarm_inline_object_fragment_index()

    @prompt_editor_work_event(PromptEditorWorkEvent.DIAGNOSTIC_CACHE_CLEAR)
    def _clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Discard cached diagnostic underline fragments after geometry changes."""

        self._diagnostic_layer_owner.clear_fragment_cache(reason=reason)

    @prompt_editor_work_event(PromptEditorWorkEvent.DIAGNOSTIC_CACHE_PRESERVE)
    def _preserve_diagnostic_fragment_cache_for_incremental_edit(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity,
        next_layout_identity: PromptLayoutIdentity,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Keep unaffected diagnostic fragments after an accepted local edit."""

        self._diagnostic_layer_owner.preserve_fragment_cache_for_incremental_edit(
            diagnostics=self._session.diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
            previous_layout_identity=previous_layout_identity,
            next_layout_identity=next_layout_identity,
            fragment_y_delta=fragment_y_delta,
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
        self._cursor_state = cursor_state
        self._anchor_state = anchor_state
        self._sync_editing_session_to_caret_states()
        self._caret_rect_override = None
        self._preferred_x = None
        self._ensure_caret_visible()
        self._selection_layer_owner.refresh()
        self._diagnostic_layer_owner.refresh(reason="selection_changed")
        self._restart_caret_blink_cycle()
        if selection_paints_changed(previous_selection, self._selection()):
            self.viewport().update()
        self._update_caret_paint(previous_caret_rect)
        self.cursorPositionChanged.emit()

    def _replace_viewport_range(
        self,
        start: int,
        end: int,
        replacement_text: str,
        *,
        origin: PromptSourceEditOrigin = PromptSourceEditOrigin.TYPED,
    ) -> None:
        """Replace one raw source range and keep cursor state undo-safe."""

        self._visible_scroll_bar()
        syntax_replacement_range = (
            self._syntax_sensitive_token_selection_replacement_range(
                start=start,
                end=end,
                replacement_text=replacement_text,
            )
        )
        if syntax_replacement_range is not None:
            start, end = syntax_replacement_range
        self._source_commands.replace_source_range(
            start=start,
            end=end,
            replacement_text=replacement_text,
            origin=origin,
        )

    def _syntax_sensitive_token_selection_replacement_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> tuple[int, int] | None:
        """Return the outer token range for syntax edits over selected token content."""

        if not replacement_text or not any(
            character in "(){}<>:\\" for character in replacement_text
        ):
            return None
        token = self.focused_token()
        if (
            token is None
            or token.kind is not PromptProjectionTokenKind.EMPHASIS
            or token.content_start is None
            or token.content_end is None
            or (start, end) != (token.content_start, token.content_end)
        ):
            return None
        return token.source_start, token.source_end

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
        previous_cursor_state = self._cursor_state
        previous_anchor_state = self._anchor_state
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
        self._clear_diagnostic_fragment_cache(reason=invalidation_reason)
        self._cursor_state = rebuild_result.cursor_state
        self._anchor_state = rebuild_result.anchor_state
        self._sync_editing_session_to_caret_states()
        self._caret_rect_override = None
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

        ranges: list[tuple[int, int]] = []
        for outer_range in (
            self._overlay_emphasis_accent_range,
            self._wheel_intent_emphasis_accent_range,
            self._pulsed_emphasis_accent_range,
        ):
            if outer_range is None or outer_range in ranges:
                continue
            ranges.append(outer_range)
        return tuple(ranges)

    def _clear_pulsed_emphasis_accent_range(self) -> None:
        """Clear one completed emphasis-feedback pulse and refresh projected decoration state."""

        if self._pulsed_emphasis_accent_range is None:
            return
        self._pulsed_emphasis_accent_range = None
        if self._display_mode is PromptProjectionDisplayMode.PROJECTED:
            self._apply_decoration_accent_paint_state()

    def _apply_decoration_accent_paint_state(self) -> None:
        """Apply emphasis decoration accent changes without rebuilding layout."""

        self._refresh_projection_paint_state()
        self.viewport().update()

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_SYNC_LAYOUT)
    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Keep layout metrics in sync and optionally commit rebuilt projection freshness."""

        if self._reorder_preview_projection.preview_state is not None:
            layout_width = self._layout_width_resolver.resolve()
            font = self.font()
            if not self._reorder_preview_projection.geometry_inputs_match(
                layout_width=layout_width,
                font=font,
            ):
                invalidation = self._reorder_preview_projection.rebuild_geometry_inputs(
                    source_revision=self._editor_state.source.source_revision,
                    layout_width=layout_width,
                    viewport_width=self.viewport().width(),
                    font=font,
                    palette=self.palette(),
                    semantic_palette=semantic_palette_from_theme(),
                    live_projection_document=self._editor_state.projection.document,
                    live_projection_frame=self._layout.frame,
                )
                if invalidation.clear_base_drag_geometry_reason is not None:
                    self._clear_base_drag_geometry_caches(
                        reason=invalidation.clear_base_drag_geometry_reason
                    )
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

    def set_reorder_surface_visual_publication(
        self,
        publication: PromptReorderSurfaceVisualPublication,
    ) -> None:
        """Publish chrome and suppression atomically for one prepared frame."""

        if not self._reorder_surface_visual_state.publish(
            publication,
            context=self._reorder_surface_visual_context(),
        ):
            return
        self._publish_render_frame()
        self.viewport().update()

    def _reorder_surface_visual_context(self) -> PromptReorderSurfaceVisualContext:
        """Return the exact projection identity receiving reorder visuals."""

        return PromptReorderSurfaceVisualContext(
            source_revision=self._editor_state.source.source_revision,
            viewport_rect=self.viewport().rect(),
            scroll_offset=int(round(self._scroll_offset())),
            preview_generation=self._reorder_preview_generation(),
        )

    def _preview_visible_region(self) -> QRegion | None:
        """Return the viewport region that should remain visible during preview paint."""

        preview_state = self._reorder_preview_projection.preview_state
        preview_frame = self._reorder_preview_projection.preview_frame
        if preview_state is None or preview_frame is None:
            return None
        suppression_snapshots = (
            self._reorder_surface_visual_state.state.suppression_snapshots_by_index
        )
        if not suppression_snapshots:
            return None

        visible_region = QRegion(self.viewport().rect())
        for chip_index, snapshot in suppression_snapshots.items():
            if not self._reorder_suppression_snapshot_is_fresh(
                snapshot,
                chip_index=chip_index,
            ):
                continue
            for fragment_rect in snapshot.viewport_rects:
                visible_region = visible_region.subtracted(
                    QRegion(fragment_rect.toAlignedRect())
                )
        return visible_region

    def _reorder_suppression_snapshot_is_fresh(
        self,
        snapshot: PromptReorderProjectionPaintSnapshot,
        *,
        chip_index: int,
    ) -> bool:
        """Return whether an overlay snapshot matches the active preview paint."""

        key = snapshot.key
        return not (
            key.source_revision != self._editor_state.source.source_revision
            or key.viewport_rect != self.viewport().rect()
            or key.scroll_offset != int(round(self._scroll_offset()))
            or key.preview_generation != self._reorder_preview_generation()
            or key.segment_index != chip_index
            or key.mode != "preview"
        )

    def undo_restoration_payload(self) -> PromptProjectionUndoPayload:
        """Return passive projection state for controller-owned undo snapshots."""

        paint_input = self._layout.frame.paint_input
        return PromptProjectionUndoPayload(
            cursor_state=self._cursor_state,
            anchor_state=self._anchor_state,
            expanded_source_range=self._session.expanded_source_range,
            document_view=self._editor_state.projection_semantic.document,
            render_plan=self._editor_state.projection_semantic.render_plan,
            layout_checkpoint=capture_layout_checkpoint(
                self._layout.frame.output,
                palette_key=int(paint_input.palette.cacheKey()),
                semantic_palette=paint_input.semantic_palette,
            ),
        )

    def undo_comparison_payload(
        self,
    ) -> tuple[
        PromptProjectionCaretState,
        PromptProjectionCaretState,
        tuple[int, int] | None,
    ]:
        """Return projection state that contributes to undo snapshot equality."""

        return (
            self._cursor_state,
            self._anchor_state,
            self._session.expanded_source_range,
        )

    def emit_undo_available_changed(self, available: bool) -> None:
        """Emit an undo availability transition requested by the edit controller."""

        self.undoAvailableChanged.emit(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Emit a redo availability transition requested by the edit controller."""

        self.redoAvailableChanged.emit(available)

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

        next_anchor_state = self._anchor_state if keep_anchor else caret_state
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
        if self._caret_rect_override is not None:
            return QRectF(self._caret_rect_override)
        return self._layout.frame.geometry.caret.cursor_rect(
            self._cursor_state,
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

    def _install_lora_tooltip_filter(self) -> None:
        """Install delayed QFluent tooltips for inline LoRA chip labels."""

        self._lora_feature_delegate.install_tooltip_filter()

    def _lora_tooltip_for_hover_event(
        self,
        watched: object,
        event: object,
    ) -> str | None:
        """Return full page/version text for the hovered LoRA chip."""

        return self._lora_feature_delegate.tooltip_for_hover_event(watched, event)

    def _request_lora_context_menu(
        self,
        viewport_position: QPointF,
        global_pos: QPoint,
    ) -> bool:
        """Emit a LoRA context-menu request when the clicked token has actions."""

        return self._lora_feature_delegate.request_context_menu(
            viewport_position,
            global_pos,
        )

    def _emit_lora_context_menu_request(
        self,
        token: PromptProjectionToken,
        global_pos: QPoint,
    ) -> None:
        """Emit one prepared LoRA context-menu request from the feature delegate."""

        self.loraContextMenuRequested.emit(token, global_pos)

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
