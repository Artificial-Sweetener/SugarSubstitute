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

from .exact_weight_editor import PromptExactWeightEditorHost

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
from ..core.editing.source_commands import PromptSourceEditOrigin
from ..interactions.cursor_adapter import (
    PromptCursorAdapter,
)
from ..interactions.pointer_ports import PromptSurfacePointerInteractions
from ..interactions.text_mutation_controller import (
    PromptProjectionTextMutationContext,
)
from ..interactions import (
    PromptSurfaceKeyHost,
    PromptSurfaceMouseHost,
    PromptSurfaceWheelHost,
    PromptWheelScrollResult,
    prompt_word_bounds,
)
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from ..qt_lifecycle import qt_object_is_alive
from .autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionOwner,
)
from .caret_movement_controller import (
    PromptProjectionCaretMovementHost,
)
from .caret_visual import PromptSurfaceCaretVisualController
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .emphasis_projection_owner import PromptProjectionEmphasisOwner
from .editing_runtime import PromptProjectionEditingRuntimeFactory
from .fill_band_cache import (
    PromptFillBandRect,
)
from .frame_state import (
    PromptProjectionEditorState,
)
from .freshness_controller import (
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .geometry_reuse_warmer import PromptProjectionGeometryReuseWarmer
from .history_owner import PromptProjectionHistoryOwner
from .input_method_controller import PromptInputMethodHost
from ..layout.contracts import PromptLayoutDamage
from .lora_surface_features import (
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
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)
from .observability import (
    render_plan_lora_span_count,
)
from .region_chrome_state import PromptRegionChromeEditTarget
from .reorder_projection_owner import PromptReorderProjectionOwner
from ..geometry.models import PromptProjectionSourceLineRect
from .surface_foundation import (
    PromptProjectionSurfaceFoundationBindings,
    build_prompt_projection_surface_foundation,
)
from .surface_input_runtime import (
    PromptProjectionSurfaceInputBindings,
    build_prompt_projection_surface_input_runtime,
)
from .surface_interaction_runtime import (
    PromptProjectionSurfaceInteractionBindings,
    build_prompt_projection_surface_interaction_runtime,
)
from .surface_graph_effects import (
    PromptProjectionSurfaceGraphEffects,
    bind_prompt_projection_surface_graph_effects,
)
from .surface_presentation_runtime import (
    PromptProjectionSurfacePresentationBindings,
    PromptProjectionSurfacePresentationRuntime,
    build_prompt_projection_surface_presentation_runtime,
)
from .refresh_geometry_signature import PromptRefreshGeometryPaintSignature
from .source_state_wiring import (
    PromptProjectionSourceStateBindings,
    build_prompt_projection_source_state_owners,
)
from .source_lifecycle_effects import (
    PromptProjectionSourceLifecycleEffects,
    bind_prompt_projection_source_lifecycle_effects,
)
from .surface_lifecycle_runtime import (
    PromptProjectionSurfaceLifecycleBindings,
    build_prompt_projection_surface_lifecycle_runtime,
)
from .theme import qcolor_from_rgb, semantic_palette_from_theme
from .undo_payload import PromptProjectionUndoPayload
from ..interactions.deletion_controller import (
    PromptDeletionContext,
    PromptDeletionContextProvider,
    PromptDeletionProjectionEffects,
)

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
        foundation = build_prompt_projection_surface_foundation(
            PromptProjectionSurfaceFoundationBindings(
                host=cast(PromptSurfaceLoraFeatureHost, self),
                editing_session=editing_session,
                document_semantics=document_semantics,
                lora_thumbnail_cache=lora_thumbnail_cache,
                lora_thumbnail_preloader=lora_thumbnail_preloader,
                publish_thumbnail_media=self._publish_lora_thumbnail_media,
                publish_context_menu=(
                    lambda token, global_pos: self.loraContextMenuRequested.emit(
                        token,
                        global_pos,
                    )
                ),
            )
        )
        self._projection_applicator = foundation.applicator
        thumbnail_cache = foundation.thumbnail_cache
        self._session = foundation.session
        self._layout = foundation.layout
        self._content_media_owner = foundation.content_media
        self._lora_feature_delegate = foundation.lora_features
        self._editor_state = foundation.editor_state
        self._frame_state = foundation.frame_state
        self._source_line_chrome = foundation.source_line_chrome
        self._search_highlight_layer = foundation.search_highlight
        self._caret_state_owner = foundation.caret_state
        self._transient_edit_overlays = foundation.transient_overlays
        graph_effects = PromptProjectionSurfaceGraphEffects()
        self._presentation_runtime: PromptProjectionSurfacePresentationRuntime
        interaction_runtime = build_prompt_projection_surface_interaction_runtime(
            PromptProjectionSurfaceInteractionBindings(
                surface=self,
                exact_weight_host=cast(PromptExactWeightEditorHost, self),
                mouse_host=cast(PromptSurfaceMouseHost, self),
                editing_session=self._editing_session,
                editor_state=self._editor_state,
                caret_state=self._caret_state_owner,
                transient_overlays=self._transient_edit_overlays,
                session=self._session,
                layout=self._layout,
                graph_effects=graph_effects,
                scroll_offset=self._scroll_offset,
                selection=self._selection,
                collapse_expanded_token=self._collapse_expanded_token_if_possible,
                emit_cursor_position_changed=self.cursorPositionChanged.emit,
                flush_pending_projection=(
                    lambda reason: self._flush_pending_projection_update(reason=reason)
                ),
                request_update=self.viewport().update,
                surface_state=lambda: surface_probe_state(self),
                request_lora_context_menu=(
                    self._lora_feature_delegate.request_context_menu
                ),
            )
        )
        self.exact_weight_editor = interaction_runtime.exact_weight
        self._caret_geometry = interaction_runtime.caret_geometry
        self._caret_publication = interaction_runtime.caret_publication
        self._autocomplete_preview_projection_owner = (
            interaction_runtime.autocomplete_preview
        )
        self._focus_owner = interaction_runtime.focus
        self._mouse_handler = interaction_runtime.mouse
        self._exact_source_editing_enabled = False
        self._reorder: PromptReorderProjectionOwner
        self._caret_visual_controller: PromptSurfaceCaretVisualController
        self._projection_freshness_controller: PromptProjectionFreshnessController
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
            request_update=graph_effects.diagnostic_layer_changed,
        )
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
        input_runtime = build_prompt_projection_surface_input_runtime(
            PromptProjectionSurfaceInputBindings(
                input_method_host=cast(PromptInputMethodHost, self),
                deletion_context_provider=cast(PromptDeletionContextProvider, self),
                deletion_projection_effects=cast(PromptDeletionProjectionEffects, self),
                key_host=cast(PromptSurfaceKeyHost, self),
                wheel_host=cast(PromptSurfaceWheelHost, self),
                viewport=self.viewport(),
                layout=self._layout,
                mouse=self._mouse_handler,
                history=self._history,
                editing_runtime=editing_runtime,
                external_text_insertion=self._insert_external_mime_text,
                finish_pending_key_edit_block=(
                    lambda reason: self._finish_pending_key_edit_block(reason=reason)
                ),
                publish_render_frame=self._publish_render_frame,
                request_update=self.viewport().update,
                input_method_hints=self.inputMethodHints,
                viewport_rect=lambda: QRectF(self.viewport().rect()),
                parent=self,
            )
        )
        self._input_runtime = input_runtime
        self._geometry_reuse_warmer = PromptProjectionGeometryReuseWarmer(
            is_available=lambda: qt_object_is_alive(self),
            is_projected=graph_effects.is_projected,
            prewarm=(
                lambda: (
                    self._layout.frame.output.snapshot.prewarm_inline_object_fragment_index()
                )
            ),
            parent=self,
        )
        source_lifecycle_effects = PromptProjectionSourceLifecycleEffects()
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
                deferred_feedback_context=self,
                prompt_state_host=self,
                fact_context=self,
                source_presentation_sink=self,
                caret_publication=self._caret_publication,
                caret_geometry=self._caret_geometry,
                transient_edit_overlays=self._transient_edit_overlays,
                set_cursor_positions=(
                    lambda cursor, anchor: self.set_cursor_positions(
                        cursor_position=cursor,
                        anchor_position=anchor,
                    )
                ),
                active_span_range=self._active_span_range,
                lifecycle_effects=source_lifecycle_effects,
                projection_freshness_blockers=self._projection_freshness_blockers,
                input_method_source_changed=self._input_runtime.input_method.source_changed,
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
        self._source_change_publication = source_state_owners.source_change_publication
        self._projection_freshness_controller = source_state_owners.freshness_controller
        self._transient_edit_presentation = (
            source_state_owners.transient_edit_presentation
        )
        self._caret_visibility_prompt_state_revision: int | None = None
        lifecycle_runtime = build_prompt_projection_surface_lifecycle_runtime(
            PromptProjectionSurfaceLifecycleBindings(
                surface=self,
                viewport=self.viewport(),
                applicator=self._projection_applicator,
                thumbnail_cache=thumbnail_cache,
                editor_state=self._editor_state,
                layout=self._layout,
                freshness=self._projection_freshness_controller,
                caret_state=self._caret_state_owner,
                caret_publication=self._caret_publication,
                caret_geometry=self._caret_geometry,
                caret_movement_host=cast(PromptProjectionCaretMovementHost, self),
                focus=self._focus_owner,
                session=self._session,
                scroll_offset=self._scroll_offset,
                flush_pending_projection=(
                    lambda reason: self._flush_pending_projection_update(reason=reason)
                ),
                synchronize_layout=self._sync_layout_state,
                publish_render_frame=self._publish_render_frame,
                request_update=self.viewport().update,
                selection=self._selection,
                surface_is_visible=self.isVisible,
                visible_scroll_bar=self._visible_scroll_bar,
                is_projected=graph_effects.is_projected,
                tokens=lambda: self._editor_state.projection.document.tokens,
                apply_session_paint_state=graph_effects.apply_session_paint_state,
                apply_accent_paint_state=self._apply_decoration_accent_paint_state,
                rebuild_projection=graph_effects.rebuild_projection,
                publish_caret=(
                    lambda cursor_state, anchor_state: self._caret_publication.publish(
                        cursor_state=cursor_state,
                        anchor_state=anchor_state,
                    )
                ),
                parent=self,
            )
        )
        self._layout_width_resolver = lifecycle_runtime.layout_width
        self._reorder = lifecycle_runtime.reorder
        self._selection_layer_owner = lifecycle_runtime.selection_layer
        self._caret_visual_controller = lifecycle_runtime.caret_visual
        self._emphasis = lifecycle_runtime.emphasis
        self._caret_movement_controller = lifecycle_runtime.caret_movement
        self._edit_pipeline = source_state_owners.edit_pipeline
        self._prompt_state_applier = source_state_owners.prompt_state_applier
        presentation_runtime = build_prompt_projection_surface_presentation_runtime(
            PromptProjectionSurfacePresentationBindings(
                surface=self,
                viewport=self.viewport(),
                applicator=self._projection_applicator,
                editor_state=self._editor_state,
                session=self._session,
                layout=self._layout,
                frame_state=self._frame_state,
                freshness=self._projection_freshness_controller,
                width_resolver=self._layout_width_resolver,
                source_document=self._source_document_adapter,
                source_line_chrome=self._source_line_chrome,
                search_highlight=self._search_highlight_layer,
                input_method=self._input_runtime.input_method,
                content_media=self._content_media_owner,
                selection_layer=self._selection_layer_owner,
                diagnostics=self._diagnostic_layer_owner,
                transient_overlays=self._transient_edit_overlays,
                reorder=self._reorder,
                caret_state=self._caret_state_owner,
                caret_publication=self._caret_publication,
                caret_geometry=self._caret_geometry,
                live_source_text=self.toPlainText,
                viewport_rect=lambda: QRectF(self.viewport().rect()),
                scroll_offset=self._scroll_offset,
                cursor_position=lambda: self.cursor_position,
                focus_active=self._focus_owner_has_focus,
                selection=self._selection,
                active_span_range=self._active_span_range,
                decoration_accent_ranges=self._decoration_accent_ranges,
                flush_pending_projection=(
                    lambda reason: self._flush_pending_projection_update(reason=reason)
                ),
                cancel_pending_projection=self._cancel_pending_projection_update,
                clear_hovered_token=(
                    lambda: self._mouse_handler.clear_hovered_token(update=False)
                ),
                hovered_token_id=lambda: self._mouse_handler.hovered_token_id,
                prewarm_visible_banners=(
                    lambda: self._lora_feature_delegate.prewarm_visible_banners(
                        self._layout.frame.geometry
                    )
                ),
                font=self.font,
                palette=self.palette,
                should_paint_caret=(self._caret_visual_controller.should_paint_caret),
                current_caret_rect=self._caret_geometry.current_viewport_rect,
                scroll_range_sink=(
                    lambda page_step, scroll_range: (
                        self._input_runtime.wheel.sync_external_scroll_range(
                            page_step=page_step,
                            scroll_range=scroll_range,
                        )
                    )
                ),
                content_height_sink=self.contentHeightChanged.emit,
                invalidate_backing=self.backingFillInvalidated.emit,
                ensure_caret_visible=(
                    self._caret_visual_controller.ensure_caret_visible
                ),
                emit_cursor_position_changed=self.cursorPositionChanged.emit,
                request_update=self.viewport().update,
                surface_state=lambda: surface_probe_state(self),
            )
        )
        self._presentation_runtime = presentation_runtime
        bind_prompt_projection_surface_graph_effects(
            graph_effects,
            freshness=self._projection_freshness_controller,
            autocomplete=self._autocomplete_preview_projection_owner,
            lifecycle=lifecycle_runtime,
            presentation=presentation_runtime,
        )
        bind_prompt_projection_source_lifecycle_effects(
            source_lifecycle_effects,
            lifecycle=lifecycle_runtime,
            presentation=presentation_runtime,
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
        self.viewport().installEventFilter(self._input_runtime.viewport_events)
        self._lora_feature_delegate.install_tooltip_filter()
        self._sync_layout_state()
        self._presentation_runtime.rebuild.rebuild()

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

        return self._input_runtime.edit_execution

    @property
    def source_commands(
        self,
    ) -> PromptSourceCommandService[PromptProjectionUndoPayload]:
        """Return the focused source command service."""

        return self._input_runtime.source_commands

    @property
    def history(self) -> PromptProjectionHistoryOwner:
        """Return the owner of undo payloads and clipboard history actions."""

        return self._history

    def attach_external_scroll_bar(self, scroll_bar: QScrollBar) -> None:
        """Mirror layout range and scroll offset onto one host-owned scrollbar."""

        self._input_runtime.wheel.attach_external_scroll_bar(scroll_bar)

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
        self._presentation_runtime.render_publication.viewport_scrolled()
        self._input_runtime.wheel.refresh_scroll()

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

        return self._presentation_runtime.rebuild.display_mode

    def set_display_mode(self, display_mode: PromptProjectionDisplayMode) -> None:
        """Replace the visible prompt display mode without changing source text."""

        self._presentation_runtime.rebuild.set_display_mode(display_mode)

    def changeEvent(self, event: QEvent) -> None:
        """Invalidate reorder preview caches when visual metrics may have changed."""

        if event.type() in {
            QEvent.Type.FontChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }:
            self._reorder.clear_projection_and_geometry(reason="visual_style_changed")
            self._presentation_runtime.render_publication.visual_style_changed()
        super().changeEvent(event)

    def projection_document(self) -> PromptProjectionDocument:
        """Return the committed token-aware projection document."""

        return self._presentation_runtime.queries.projection_document

    def active_projection_document(self) -> PromptProjectionDocument:
        """Return the current geometry-bearing projection document."""

        return self._presentation_runtime.queries.active_projection_document

    def content_height(self) -> float:
        """Return the current laid-out projection content height."""

        return self._presentation_runtime.queries.content_height()

    def text_line_height(self) -> float:
        """Return the row height owned by the current prepared layout."""

        return self._presentation_runtime.queries.text_line_height()

    def source_range_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return the wrapped viewport fragments covering one raw source range."""

        return self._presentation_runtime.queries.source_range_fragments(
            start=start, end=end
        )

    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible source logical line rects aligned to prompt projection."""

        return self._presentation_runtime.queries.source_line_rects()

    def visible_prompt_fill_band_rects(self) -> tuple[PromptFillBandRect, ...]:
        """Return visible prompt fill band rows in projection viewport coordinates."""

        return self._presentation_runtime.queries.visible_fill_band_rects()

    def prompt_fill_band_color(self) -> QColor:
        """Return the alternating prompt fill color used beneath projection painting."""

        return self._presentation_runtime.queries.fill_band_color()

    def current_source_line_index(self) -> int:
        """Return the newline-delimited source line containing the cursor."""

        return self._presentation_runtime.queries.current_source_line_index()

    def set_source_line_chrome_enabled(self, enabled: bool) -> None:
        """Enable source logical line backgrounds for wrapper-provided editor chrome."""

        self._presentation_runtime.source_line.set_enabled(enabled)

    def set_source_line_content_left_inset(self, inset: float) -> None:
        """Reserve viewport-local space for source line numbers."""

        self._presentation_runtime.source_line.set_content_left_inset(inset)

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Replace scene keys that should render as title-level diagnostics."""

        self._presentation_runtime.scene_diagnostics.set_keys(scene_error_keys)

    def scene_error_keys(self) -> frozenset[str]:
        """Return scene keys currently included in projection builds."""

        return self._presentation_runtime.scene_diagnostics.keys

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Replace the transient search matches rendered by the projection surface."""

        self._presentation_runtime.search.set_matches(
            matches, active_index=active_index
        )

    def clear_search_matches(self) -> None:
        """Clear transient search highlights from the projection surface."""

        self._presentation_runtime.search.clear_matches()

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the syntax span currently owned by the caret or token focus."""

        return self._presentation_runtime.queries.active_syntax_span()

    def hovered_token(self) -> PromptProjectionToken | None:
        """Return the token currently under the pointer when present."""

        return self._presentation_runtime.queries.hovered_token()

    def focused_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning caret focus when present."""

        return self._presentation_runtime.queries.focused_token()

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projected token painted under one viewport-local point."""

        return self._presentation_runtime.queries.token_at_viewport_position(position)

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor rect used by any token controls."""

        return self._presentation_runtime.queries.token_anchor_rect(token)

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local projection-owned weight slot for one emphasis token."""

        return self._presentation_runtime.queries.token_weight_text_rect(token)

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

        self._input_runtime.edit_execution.begin_edit_block(finish_typing=finish_typing)

    def cursor_adapter_end_edit_block(self) -> None:
        """End an edit block requested by the source cursor adapter."""

        self._input_runtime.edit_execution.end_edit_block()

    def cursor_adapter_delete_selection(self) -> None:
        """Delete the live selection requested by the source cursor adapter."""

        self._delete_viewport_selection()

    def cursor_adapter_insert_text(
        self,
        text: str,
    ) -> None:
        """Insert text requested by the source cursor adapter."""

        self._input_runtime.text_mutations.insert_text(
            text,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            command_name="cursor_insert_text",
        )

    def cursorRect(self) -> QRect:  # noqa: N802
        """Return the current viewport-local caret rect."""

        self._visible_scroll_bar()
        self.has_pending_projection_update()
        transient_rect = self._caret_geometry.transient_document_rect()
        if transient_rect is not None:
            rect = transient_rect.translated(
                0.0, -self._scroll_offset()
            ).toAlignedRect()
            return rect
        self._flush_pending_projection_update(reason="cursor_rect")
        rect = self._caret_geometry.current_viewport_rect().toAlignedRect()
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
            display_mode=self._presentation_runtime.rebuild.display_mode.value,
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
            display_mode=self._presentation_runtime.rebuild.display_mode,
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

        return self._presentation_runtime.pointer_interactions

    def set_region_hovered(self, region_index: int | None) -> None:
        """Publish transient regional chrome without changing prompt selection."""

        self._presentation_runtime.region_chrome.set_hovered_region(region_index)

    def region_edit_target(
        self,
        region_index: int,
    ) -> PromptRegionChromeEditTarget | None:
        """Return prepared document-local geometry for one separator editor."""

        return self._presentation_runtime.region_chrome.edit_target(region_index)

    def set_region_editing(self, region_index: int | None) -> None:
        """Publish label suppression while an inline editor owns one separator."""

        self._presentation_runtime.region_chrome.set_editing_region(region_index)

    def set_region_editing_draft(self, region_index: int, text: str) -> None:
        """Publish live separator geometry without mutating prompt source text."""

        self._presentation_runtime.region_chrome.set_editing_region_draft(
            region_index, text
        )

    def force_collapse_expanded_token(self) -> None:
        """Collapse any expanded projection token after an explicit syntax commit."""

        if self._session.expanded_source_range is None:
            return
        self._session.expanded_source_range = None
        self._presentation_runtime.rebuild.rebuild()

    def has_stale_projection_geometry(self) -> bool:
        """Return whether layout metrics still describe an older source snapshot."""

        return self._projection_freshness_controller.has_stale_projection_geometry()

    def set_wheel_scroll_permission(
        self,
        permission: Callable[[QWheelEvent], bool] | None,
    ) -> None:
        """Set the callback that decides whether this surface may wheel-scroll."""

        self._input_runtime.wheel.set_wheel_scroll_permission(permission)

    def set_active_span(
        self,
        active_span: PromptSyntaxSpanView | None,
        *,
        cursor_position: int,
    ) -> None:
        """Track active syntax ownership without rebuilding projection geometry."""

        _ = cursor_position
        focused_or_hovered_token = (
            self._presentation_runtime.queries.focused_or_hovered_token(
                prefer_hovered=False
            )
        )
        next_active_span_range = (
            (focused_or_hovered_token.source_start, focused_or_hovered_token.source_end)
            if focused_or_hovered_token is not None
            else (
                (active_span.start, active_span.end)
                if active_span is not None
                else None
            )
        )
        self._presentation_runtime.active_projection.reconcile_active_span(
            next_active_span_range
        )

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
            display_mode=self._presentation_runtime.rebuild.display_mode,
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
        self._input_runtime.source_commands.replace_source_range(
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

        self._input_runtime.text_mutations.insert_text(
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
        self._presentation_runtime.rebuild.rebuild()
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
            self._presentation_runtime.rebuild.rebuild()
        cursor_state = PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=anchor_position,
        ).clamped(len(self.toPlainText()))
        self._caret_geometry.clear_transient()
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
        self._caret_publication.publish(
            cursor_state=next_cursor_state,
            anchor_state=next_anchor_state,
        )
        return self._editing_session.cursor_state

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

        self._input_runtime.input_method.dispatch_event(event)

    def inputMethodQuery(self, query: Qt.InputMethodQuery) -> object:  # noqa: N802
        """Expose source, selection, and caret state to the platform input method."""

        value = self._input_runtime.input_method.query(query)
        if value is not None:
            return value
        return super().inputMethodQuery(query)

    def _handle_key_press_event(self, event: QKeyEvent) -> None:
        """Delegate one key press after the public Qt entrypoint receives it."""

        if self._input_runtime.key.handle_key_press(event):
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Delegate key release handling while preserving Qt fallback behavior."""

        if self._input_runtime.key.handle_key_release(event):
            return
        super().keyReleaseEvent(event)

    def _finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Commit any pending key-owned edit block."""

        self._input_runtime.edit_execution.finish_pending_key_edit_block(reason=reason)

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
        self._input_runtime.wheel.clear_boundary_spill()
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

        return self._input_runtime.wheel.handle_prompt_wheel_scroll(event)

    def viewportEvent(self, event: QEvent) -> bool:
        """Track viewport hover updates even when Qt keeps events on the inner viewport."""

        if not hasattr(self, "_input_runtime"):
            return super().viewportEvent(event)
        router = self._input_runtime.viewport_events
        handled = router.handle_viewport_event(event)
        if handled is not None:
            return handled
        return super().viewportEvent(event)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:  # noqa: N802
        """Return whether external MIME data may become prompt source text."""

        return self._input_runtime.external_text.can_insert(source)

    def insertFromMimeData(self, source: QMimeData) -> None:  # noqa: N802
        """Insert prompt-safe MIME text through the source mutation owner."""

        self._input_runtime.external_text.insert(source)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept only prompt-safe plain text drag payloads."""

        self._input_runtime.external_text.accept_or_ignore_drag(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Keep rejecting non-text drag payloads while the pointer moves."""

        self._input_runtime.external_text.accept_or_ignore_drag(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Insert prompt-safe dropped text and reject rich/file payloads."""

        self._input_runtime.external_text.drop(
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
            self._caret_geometry.clear_transient()
        self._reorder.clear_projection_and_geometry(reason="resize")
        self._presentation_runtime.render_publication.viewport_resized()
        self.refresh_geometry()
        self.viewport().update()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Restart caret blinking when the surface itself gains focus ownership."""

        super().focusInEvent(event)
        self._presentation_runtime.render_publication.focus_changed()
        self._caret_visual_controller.schedule_caret_blink_sync(
            reset_cycle=True,
            cursor_flash_time_ms=self._caret_visual_controller.cursor_flash_time_ms,
        )

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Stop caret blinking when the surface itself loses focus ownership."""

        self._input_runtime.input_method.focus_out()
        super().focusOutEvent(event)
        self._presentation_runtime.render_publication.focus_changed()
        self._caret_visual_controller.schedule_caret_blink_sync(
            reset_cycle=False,
            cursor_flash_time_ms=self._caret_visual_controller.cursor_flash_time_ms,
        )

    def showEvent(self, event: QShowEvent) -> None:
        """Resume caret blinking when the surface becomes visible again."""

        super().showEvent(event)
        self._caret_visual_controller.schedule_caret_blink_sync(
            reset_cycle=False,
            cursor_flash_time_ms=self._caret_visual_controller.cursor_flash_time_ms,
        )
        self._lora_feature_delegate.prewarm_visible_banners(self._layout.frame.geometry)

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop caret blinking while the surface is hidden."""

        previous_caret_rect = self._caret_geometry.current_viewport_rect()
        self._caret_visual_controller.stop_caret_blink_cycle()
        self._caret_visual_controller.update_caret_paint(previous_caret_rect)
        super().hideEvent(event)

    def _publish_render_frame(self) -> None:
        """Delegate complete render-frame publication to its state owner."""

        if hasattr(self, "_presentation_runtime"):
            self._presentation_runtime.render_publication.publish()

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
            frame = self._presentation_runtime.render_frame.frame
            result = self._presentation_runtime.render_compositor.draw(
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

    def _focus_owner_has_focus(self) -> bool:
        """Return whether the prompt editor focus owner is active."""

        return self._focus_owner.focus_owner_has_focus()

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

    def _selection(self) -> PromptProjectionSelection:
        """Return the current source-backed selection model."""

        selection = self._editing_session.selection()
        return PromptProjectionSelection(
            anchor_position=selection.anchor_position,
            cursor_position=selection.cursor_position,
        )

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

        self._presentation_runtime.active_projection.refresh_paint_state()

    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Keep layout metrics in sync and optionally commit rebuilt projection freshness."""

        self._presentation_runtime.layout_publication.sync(
            commit_projection=commit_projection
        )

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
        self._caret_publication.publish(
            cursor_state=caret_state,
            anchor_state=next_anchor_state,
            caret_rect_override=caret_rect_override,
        )

    def _collapse_expanded_token_if_possible(self) -> None:
        """Collapse the expanded token once caret ownership has left a still-valid span."""

        collapsed = self._session.collapse_if_cursor_left_token(
            self._editor_state.projection_semantic.document,
            selection_start=min(self.cursor_position, self.anchor_position),
            selection_end=max(self.cursor_position, self.anchor_position),
        )
        if collapsed:
            self._presentation_runtime.rebuild.rebuild()

    def _active_span_range(self) -> tuple[int, int] | None:
        """Return the syntax range that should render as active in the projection."""

        return self._presentation_runtime.queries.active_span_range()

    def _visible_scroll_bar(self) -> QScrollBar:
        """Return the scrollbar that currently owns the visible scroll offset."""

        return self._input_runtime.wheel.visible_scroll_bar()

    def _scroll_offset(self) -> float:
        """Return the active vertical scroll offset used by layout and paint."""

        return self._input_runtime.wheel.scroll_offset()

    def _clear_pending_segment_word_selection(self) -> None:
        """Delegate pending segment-word selection clearing to pointer routing."""

        self._mouse_handler.clear_pending_segment_word_selection()

    def _emit_mouse_interaction_finished(self) -> None:
        """Emit the public signal after pointer selection has finished."""

        self.mouseInteractionFinished.emit()


__all__ = ["PromptProjectionSurface"]
