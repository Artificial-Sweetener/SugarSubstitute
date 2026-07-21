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

import math
from dataclasses import dataclass
from typing import Callable, Protocol, cast

from PySide6.QtCore import (
    QEvent,
    QMimeData,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QObject,
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
    QKeyEvent,
    QFontMetricsF,
    QHideEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPalette,
    QResizeEvent,
    QRegion,
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
from substitute.application.prompt_editor import parse_prompt_scene_projection_document
from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptDiagnostic,
    PromptReorderLayoutView,
    PromptSyntaxAction,
    PromptSyntaxRenderPlan,
    PromptSyntaxSpanView,
)
from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptDocumentSemantics,
)
from substitute.presentation.widgets.text_caret import (
    paint_text_caret,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
)

from ..autocomplete_preview_state import PromptAutocompletePreviewState
from ..editing_session import (
    PromptCursorAdapter,
    PromptCursorState,
    PromptEditingSession,
    PromptEditingSessionRestoreResult,
    PromptSourceEditOrigin,
)
from ..editing_session.edit_controller import (
    PromptEditControllerResult,
)
from ..editing_session.undo_coalescing import PromptUndoCoalescingActions
from ..debug_probe import log_prompt_editor_probe, surface_probe_state
from ..mime_data_policy import (
    mime_data_has_prompt_plain_text,
    prompt_plain_text_from_mime_data,
)
from ..interactions import (
    PromptClipboardHistoryActions,
    PromptSurfaceMouseHandler,
    PromptSurfaceMouseHost,
    PromptSurfaceKeyHandler,
    PromptSurfaceKeyHost,
    PromptSurfaceWheelHandler,
    PromptSurfaceWheelHost,
    PromptWheelScrollResult,
    prompt_word_bounds,
)
from ..qt_lifecycle import qt_object_is_alive
from .applicator import PromptProjectionApplicator, PromptProjectionRebuildResult
from .autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionHost,
    PromptAutocompletePreviewProjectionOwner,
)
from .builder import PromptProjectionBuilder
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
from .diagnostics_painter import PromptDiagnosticPainter
from .display_mode_layout_cache import (
    PromptProjectionDisplayModeLayoutCache,
    PromptProjectionDisplayModeLayoutIdentity,
)
from .freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
)
from .layout_engine import (
    PromptProjectionIncrementalLayoutResult,
    PromptProjectionLayout,
)
from .layout_checkpoint import PromptProjectionLayoutCheckpoint
from .lora_surface_features import (
    PromptSurfaceLoraFeatureDelegate,
    PromptSurfaceLoraFeatureHost,
    PromptSurfaceLoraThumbnailPreloader,
)
from .paint_cache import PromptProjectionPaintCache
from .observability import (
    log_projection_timing,
    projection_observability_started_at,
    render_plan_lora_span_count,
)
from .model import (
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
    PromptProjectionInlinePreview,
    PromptProjectionSelection,
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTransientState,
    PromptWeightControlIdentity,
)
from .selection_geometry import (
    PromptProjectionSourceLineRect,
    selection_paints_changed,
)
from .session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptProjectionSession,
    PromptTransientNeutralEmphasisOwner,
)
from .source_change_applier import PromptProjectionSourceChangeApplier
from .source_state_wiring import build_prompt_projection_source_state_owners
from .source_line_chrome import PromptSourceLineChrome
from .tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
    emphasis_weight_font,
)
from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_geometry_cache import (
    PromptReorderChipGeometryCacheKey,
    PromptReorderGeometryCache,
    PromptReorderPlacementGeometryCacheKey,
    ReorderGeometrySnapshot,
    reorder_geometry_viewport_rect,
)
from .reorder_scroll_geometry import build_reorder_geometry_after_scroll
from .reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
    chip_geometry_snapshot_context,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
    duplicate_reorder_placement_targets,
    placement_for_drag_rect,
)
from .theme import qcolor_from_rgb, scene_zebra_color, semantic_palette_from_theme
from .reorder_preview import (
    PromptReorderPreviewState,
)
from .reorder_preview_projection import (
    PromptReorderPreviewProjectionContext,
    PromptReorderPreviewProjectionService,
)
from .reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
    PromptReorderProjectionSnapshotKey,
)
from .reorder_surface_chrome import (
    PromptReorderSurfaceChromeChip,
    PromptReorderSurfaceChromePainter,
    PromptReorderSurfaceChromeSnapshot,
)
from .reorder_paint_snapshot_reuse import reuse_reorder_paint_snapshots
from .transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientInsertionOverlay,
)

_MINIMUM_VALID_LAYOUT_WIDTH = 120
_SLOW_REORDER_PROJECTION_LAYOUT_MS = 8.0
_LOGGER = get_logger("presentation.editor.prompt_editor.projection_surface")


class PromptSurfaceSourceMutationActions(Protocol):
    """Replace viewport-local source ranges through the composed mutation owner."""

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
    ) -> object:
        """Replace one prepared source range through the command router."""


class PromptSurfaceEditBlockActions(Protocol):
    """Expose edit-block lifecycle operations owned outside the surface."""

    def begin_surface_edit_block(self, *, finish_typing: bool = True) -> None:
        """Start a grouped source edit block."""

    def end_surface_edit_block(self) -> None:
        """Finish a grouped source edit block."""

    def finish_surface_pending_key_edit_block(self, *, reason: str) -> None:
        """Commit any pending key-owned edit block."""


@dataclass(frozen=True, slots=True)
class PromptProjectionUndoPayload:
    """Carry passive projection restoration data beside an undo snapshot."""

    cursor_state: PromptProjectionCaretState
    anchor_state: PromptProjectionCaretState
    expanded_source_range: tuple[int, int] | None
    document_view: PromptDocumentView
    render_plan: PromptSyntaxRenderPlan
    layout_checkpoint: PromptProjectionLayoutCheckpoint | None


@dataclass(frozen=True, slots=True)
class PromptProjectionFillBandCacheKey:
    """Identify one committed projection view state for fill-band caching."""

    source_revision: int
    display_mode: PromptProjectionDisplayMode
    viewport_width: int
    viewport_height: int
    scroll_offset: int
    content_width: float
    content_left_inset: float


@dataclass(frozen=True, slots=True)
class PromptProjectionFillBandCache:
    """Cache visible fill-band rows for one committed projection view state."""

    key: PromptProjectionFillBandCacheKey
    rects: tuple["PromptFillBandRect", ...]


@dataclass(frozen=True, slots=True)
class _RefreshGeometryPaintSignature:
    """Describe visual state that decides whether geometry refresh must repaint."""

    content_height: float
    content_width: float
    viewport_width: int
    viewport_height: int
    scroll_value: int
    scroll_maximum: int
    page_step: int
    display_mode: PromptProjectionDisplayMode
    projection_freshness: ProjectionFreshness
    source_line_content_left_inset: float
    source_line_chrome_enabled: bool
    font_key: str
    palette_key: int


@dataclass(frozen=True, slots=True)
class PromptFillBandRect:
    """Describe one visible prompt fill band row in projection viewport coordinates."""

    rect: QRectF
    band_index: int


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
        document_semantics: PromptDocumentSemantics | None = None,
        lora_thumbnail_cache: PromptLoraThumbnailCache | None = None,
        lora_thumbnail_preloader: PromptSurfaceLoraThumbnailPreloader | None = None,
    ) -> None:
        """Initialize the custom prompt editing surface."""

        super().__init__(parent)
        self._projection_applicator = PromptProjectionApplicator(
            PromptProjectionBuilder(document_semantics=document_semantics)
        )
        thumbnail_cache = lora_thumbnail_cache or PromptLoraThumbnailCache()
        self._session = PromptProjectionSession()
        self._display_mode = PromptProjectionDisplayMode.PROJECTED
        self._exact_source_editing_enabled = False
        self._layout = PromptProjectionLayout(
            PromptProjectionInlineObjectRendererRegistry(
                (
                    PromptEmphasisPrefixRenderer(),
                    PromptEmphasisSuffixRenderer(),
                    PromptLoraInlineObjectRenderer(thumbnail_cache),
                    PromptWildcardInlineObjectRenderer(),
                )
            )
        )
        self._display_mode_layout_cache = PromptProjectionDisplayModeLayoutCache()
        self._lora_feature_delegate = PromptSurfaceLoraFeatureDelegate(
            cast(PromptSurfaceLoraFeatureHost, self),
            thumbnail_cache=thumbnail_cache,
            thumbnail_preloader=lora_thumbnail_preloader,
        )
        thumbnail_cache.pixmap_ready.connect(
            self._lora_feature_delegate.update_lora_thumbnail_pixmap
        )
        self._focus_host: QWidget | None = None
        source_state_owners = build_prompt_projection_source_state_owners(
            self,
            parent=self,
        )
        self._source_document_adapter = source_state_owners.source_document
        self._source_change_applier = cast(
            PromptProjectionSourceChangeApplier[PromptProjectionUndoPayload],
            source_state_owners.source_change_applier,
        )
        self._document_view = PromptDocumentView(
            source_text="",
            segments=(),
            emphasis_spans=(),
            wildcard_spans=(),
            lora_spans=(),
            syntax_spans=(),
            has_trailing_comma=False,
        )
        self._render_plan = PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
            document_semantics_identity=(
                document_semantics.identity
                if document_semantics is not None
                else "ordinary-prompt-v1"
            ),
        )
        self._scene_error_keys: frozenset[str] = frozenset()
        self._projection_document = self._projection_applicator.build_projection(
            self._document_view,
            self._render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=None,
            decoration_accent_ranges=(),
            scene_error_keys=self._scene_error_keys,
            transient_state=PromptProjectionTransientState(),
        )
        self._active_projection_document = self._projection_document
        self._reorder_preview_projection = PromptReorderPreviewProjectionService(
            projection_applicator=self._projection_applicator,
            thumbnail_cache=thumbnail_cache,
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
        self._reorder_overlay_suppression_snapshots_by_index: dict[
            int,
            PromptReorderProjectionPaintSnapshot,
        ] = {}
        self._reorder_surface_chrome_snapshot: (
            PromptReorderSurfaceChromeSnapshot | None
        ) = None
        self._reorder_surface_chrome_painter = PromptReorderSurfaceChromePainter()
        self._reorder_geometry_cache = PromptReorderGeometryCache()
        initial_state = self._projection_document.caret_map.state_for_source_position(0)
        self._cursor_state = initial_state
        self._anchor_state = initial_state
        self._editing_session = editing_session
        self._source_mutation_actions: PromptSurfaceSourceMutationActions | None = None
        self._edit_block_actions: PromptSurfaceEditBlockActions | None = None
        self._clipboard_history_actions: PromptClipboardHistoryActions | None = None
        self._undo_coalescing_actions: PromptUndoCoalescingActions | None = None
        self._key_handler = PromptSurfaceKeyHandler(
            cast(PromptSurfaceKeyHost, self),
            clipboard_history_actions=lambda: self._clipboard_history_actions,
            undo_coalescing_actions=lambda: self._undo_coalescing_actions,
        )
        self._mouse_handler = PromptSurfaceMouseHandler(
            cast(PromptSurfaceMouseHost, self)
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
        self._editing_enabled = True
        self._source_revision = self._editing_session.source_revision
        self._caret_visibility_prompt_state_revision: int | None = None
        self._projection_freshness_controller = source_state_owners.freshness_controller
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
        self._incremental_apply_controller = (
            source_state_owners.incremental_apply_controller
        )
        self._prompt_state_applier = source_state_owners.prompt_state_applier
        self._fill_band_cache: PromptProjectionFillBandCache | None = None
        self._diagnostic_painter = PromptDiagnosticPainter(
            parent=self,
            is_alive=lambda: qt_object_is_alive(self),
            request_update=self.viewport().update,
        )
        self._projection_geometry_reuse_warm_timer = QTimer(self)
        self._projection_geometry_reuse_warm_timer.setSingleShot(True)
        self._projection_geometry_reuse_warm_timer.setInterval(0)
        self._projection_geometry_reuse_warm_timer.timeout.connect(
            self._warm_projection_geometry_reuse_indexes
        )
        self._projection_geometry_reuse_warm_requested = False
        self._projection_paint_cache = PromptProjectionPaintCache()
        self._weight_click_handler: Callable[[QPointF], bool] | None = None
        self._weight_double_click_handler: Callable[[QPointF], bool] | None = None
        self._source_line_chrome = PromptSourceLineChrome()
        self._layout.set_semantic_palette(semantic_palette_from_theme())

        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
    def anchor_position(self) -> int:
        """Return the editing-session-owned raw source selection anchor."""

        return self._editing_session.anchor_position

    def attach_runtime_mutation_actions(
        self,
        *,
        source_mutation_actions: PromptSurfaceSourceMutationActions,
        edit_block_actions: PromptSurfaceEditBlockActions,
        clipboard_history_actions: PromptClipboardHistoryActions,
        undo_coalescing_actions: PromptUndoCoalescingActions,
    ) -> None:
        """Attach composition-owned mutation actions needed by viewport events."""

        self._source_mutation_actions = source_mutation_actions
        self._edit_block_actions = edit_block_actions
        self._clipboard_history_actions = clipboard_history_actions
        self._undo_coalescing_actions = undo_coalescing_actions

    def _require_source_mutation_actions(self) -> PromptSurfaceSourceMutationActions:
        """Return viewport source mutation actions after composition wiring."""

        if self._source_mutation_actions is None:
            raise RuntimeError(
                "Prompt projection source mutation actions are not wired."
            )
        return self._source_mutation_actions

    def _require_edit_block_actions(self) -> PromptSurfaceEditBlockActions:
        """Return edit-block actions after composition wiring."""

        if self._edit_block_actions is None:
            raise RuntimeError("Prompt projection edit-block actions are not wired.")
        return self._edit_block_actions

    def document(self) -> QTextDocument:
        """Return the plain-text source document kept for compatibility helpers."""

        return self._source_document_adapter.document()

    def can_undo(self) -> bool:
        """Return whether the custom prompt undo stack can restore a prior edit."""

        return self._editing_session.can_undo()

    def can_redo(self) -> bool:
        """Return whether the custom prompt redo stack can restore a reverted edit."""

        return self._editing_session.can_redo()

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

    def refresh_scroll(self) -> None:
        """Repaint after the host scrollbar moves the visible projection window."""

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
                source_revision=self._source_revision,
                document_view=self._document_view,
                render_plan=self._render_plan,
                session=self._session,
                decoration_accent_ranges=self._decoration_accent_ranges(),
                scene_error_keys=self._scene_error_keys,
            )
        )
        self._display_mode_layout_cache.remember(
            self._display_mode,
            self._layout,
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
            self._layout,
            identity=layout_identity,
            expected_source_text=self._document_view.source_text,
            previous_cursor_state=previous_cursor_state,
            previous_anchor_state=previous_anchor_state,
        )
        if restored_projection is None:
            self._build_and_publish_projection()
        else:
            self._publish_projection_rebuild_result(
                restored_projection,
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
        super().changeEvent(event)

    def projection_document(self) -> PromptProjectionDocument:
        """Return the committed token-aware projection document."""

        return self._projection_document

    def active_projection_document(self) -> PromptProjectionDocument:
        """Return the current geometry-bearing projection document."""

        return self._active_projection_document

    def content_height(self) -> float:
        """Return the current laid-out projection content height."""

        preview_layout = self._reorder_preview_projection.preview_layout
        if preview_layout is not None:
            content_height = preview_layout.content_size().height()
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
        content_height = self._layout.content_size().height()
        self._log_passive_metric_read(
            metric="content_height",
            returned_height=content_height,
            forced_unavailable=True,
        )
        return content_height

    def source_range_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return the wrapped viewport fragments covering one raw source range."""

        self._flush_pending_projection_update(reason="source_range_fragments")
        return self._layout.source_range_fragments(
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
            layout=self._layout,
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
        cache_key = self._fill_band_cache_key()
        cached_bands = self._fill_band_cache
        if cached_bands is not None and self._fill_band_cache_matches(
            cached_bands,
            cache_key,
        ):
            self._log_passive_metric_read(
                metric="visible_prompt_fill_band_rects",
                committed_revision=cached_bands.key.source_revision,
                rect_count=len(cached_bands.rects),
            )
            return cached_bands.rects

        source_text = self._fill_band_source_text()
        scene_document = parse_prompt_scene_projection_document(source_text)
        if not scene_document.has_scenes:
            self._fill_band_cache = PromptProjectionFillBandCache(
                key=cache_key,
                rects=(),
            )
            self._log_passive_metric_read(
                metric="visible_prompt_fill_band_rects",
                committed_revision=cache_key.source_revision,
                rect_count=0,
            )
            return ()
        viewport_rect = QRectF(self.viewport().rect())
        scroll_offset = self._scroll_offset()
        band_rects: list[PromptFillBandRect] = []
        band_sources: list[tuple[int, int, int]] = []
        next_band_index = 0
        if scene_document.universal_text.strip():
            band_sources.append(
                (
                    next_band_index,
                    scene_document.universal_range.start,
                    scene_document.universal_range.end,
                )
            )
            band_rects.extend(
                PromptFillBandRect(rect=rect, band_index=next_band_index)
                for rect in self._layout.source_range_row_rects(
                    scene_document.universal_range.start,
                    scene_document.universal_range.end,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
            )
            next_band_index += 1
        for scene_index, scene in enumerate(scene_document.scenes):
            band_index = next_band_index + scene_index
            band_sources.append(
                (
                    band_index,
                    scene.marker.title_range.start,
                    scene.content_range.end,
                )
            )
            band_rects.extend(
                PromptFillBandRect(rect=rect, band_index=band_index)
                for rect in self._layout.source_range_row_rects(
                    scene.marker.title_range.start,
                    scene.content_range.end,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
            )
        result = tuple(band_rects)
        self._fill_band_cache = PromptProjectionFillBandCache(
            key=cache_key,
            rects=result,
        )
        self._log_passive_metric_read(
            metric="visible_prompt_fill_band_rects",
            committed_revision=cache_key.source_revision,
            rect_count=len(result),
        )
        return result

    def _fill_band_source_text(self) -> str:
        """Return the source text that matches passive fill-band layout freshness."""

        return self._projection_freshness_controller.fill_band_source_text(
            committed_source_text=self._projection_document.source_text,
            live_source_text=self.toPlainText(),
        )

    def _fill_band_cache_key(self) -> PromptProjectionFillBandCacheKey:
        """Return the view-state key for passive fill-band cache lookups."""

        source_revision = (
            self._projection_freshness_controller.fill_band_source_revision(
                current_source_revision=self._source_revision
            )
        )
        content_width = self._projection_freshness_controller.fill_band_content_width(
            current_content_width=self._layout.content_size().width()
        )
        return PromptProjectionFillBandCacheKey(
            source_revision=source_revision,
            display_mode=self._display_mode,
            viewport_width=self.viewport().width(),
            viewport_height=self.viewport().height(),
            scroll_offset=int(round(self._scroll_offset())),
            content_width=content_width,
            content_left_inset=self._source_line_chrome.content_left_inset,
        )

    def _fill_band_cache_matches(
        self,
        cache: PromptProjectionFillBandCache,
        key: PromptProjectionFillBandCacheKey,
    ) -> bool:
        """Return whether a cached fill-band result matches the current view state."""

        mismatch_reason: str | None = None
        if cache.key.source_revision != key.source_revision:
            mismatch_reason = "source_revision"
        elif cache.key.display_mode is not key.display_mode:
            mismatch_reason = "display_mode"
        elif cache.key.viewport_width != key.viewport_width:
            mismatch_reason = "viewport_width"
        elif cache.key.viewport_height != key.viewport_height:
            mismatch_reason = "viewport_height"
        elif cache.key.scroll_offset != key.scroll_offset:
            mismatch_reason = "scroll_offset"
        elif abs(cache.key.content_width - key.content_width) >= 0.01:
            mismatch_reason = "content_width"
        elif abs(cache.key.content_left_inset - key.content_left_inset) >= 0.01:
            mismatch_reason = "content_left_inset"
        if mismatch_reason is None:
            return True
        return False

    def prompt_fill_band_color(self) -> QColor:
        """Return the alternating prompt fill color used beneath projection painting."""

        return scene_zebra_color()

    def current_source_line_index(self) -> int:
        """Return the newline-delimited source line containing the cursor."""

        self._flush_pending_projection_update(reason="current_source_line_index")
        return self._source_line_chrome.current_source_line_index(
            layout=self._layout,
            cursor_position=self.cursor_position,
        )

    def set_source_line_chrome_enabled(self, enabled: bool) -> None:
        """Enable source logical line backgrounds for wrapper-provided editor chrome."""

        if not self._source_line_chrome.set_enabled(enabled):
            return
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
        self._invalidate_projection_content_cache(reason="autocomplete_preview_state")
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
            self._document_view,
            self._render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=active_span_range,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            transient_state=transient_state,
        )
        self._layout.set_projection(
            self._active_projection_document,
            prompt_document_view=self._document_view,
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
            self._document_view,
            self._render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=active_span_range,
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            layout=self._layout,
        )
        if result is None:
            log_prompt_editor_probe(
                "surface.refresh_projection_paint_state.noop",
                surface=surface_probe_state(self),
            )
            return
        self._last_rendered_active_span_range = result.active_span_range
        self._active_projection_document = self._projection_document
        self.viewport().update()
        log_prompt_editor_probe(
            "surface.refresh_projection_paint_state.end",
            surface=surface_probe_state(self),
        )

    def _restore_base_projection_layout_after_transient_state(self) -> None:
        """Restore canonical projection geometry after layout-affecting transient state."""

        if self._layout.projection_document is self._projection_document:
            self._active_projection_document = self._projection_document
            return
        log_prompt_editor_probe(
            "surface.restore_base_projection_layout.begin",
            surface=surface_probe_state(self),
        )
        self._layout.set_projection(
            self._projection_document,
            prompt_document_view=self._document_view,
        )
        self._active_projection_document = self._projection_document
        self._sync_layout_state()
        self._invalidate_projection_content_cache(reason="restore_base_projection")
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

    def _new_projection_layout(self) -> PromptProjectionLayout:
        """Return a projection layout configured with the surface renderers."""

        return PromptProjectionLayout(
            PromptProjectionInlineObjectRendererRegistry(
                (
                    PromptEmphasisPrefixRenderer(),
                    PromptEmphasisSuffixRenderer(),
                    PromptLoraInlineObjectRenderer(
                        self._lora_feature_delegate.thumbnail_cache
                    ),
                    PromptWildcardInlineObjectRenderer(),
                )
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
        self.viewport().update()

    def clear_search_matches(self) -> None:
        """Clear transient search highlights from the projection surface."""

        self._session.clear_search_matches()
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
        self._schedule_diagnostic_fragment_cache_warm(reason="diagnostics_changed")
        self.viewport().update()

    def clear_diagnostics(self) -> None:
        """Clear transient diagnostics from the projection surface."""

        if not self._session.diagnostics:
            return
        self._clear_diagnostic_fragment_cache(reason="diagnostics_cleared")
        self._diagnostic_painter.stop_warm()
        self._session.clear_diagnostics()
        self.viewport().update()

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
            self._reorder_overlay_suppression_snapshots_by_index = {}
        self._flush_pending_projection_update(reason="set_reorder_preview_state")
        invalidation = self._reorder_preview_projection.set_preview_state(
            preview_state,
            context=self._reorder_preview_projection_context(preview_state),
            font=self.font(),
            palette=self.palette(),
            semantic_palette=semantic_palette_from_theme(),
            live_projection_document=self._projection_document,
            live_projection_layout=self._layout,
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

        self._reorder_geometry_cache.reset_counters()
        self._reorder_preview_projection.reset_counters()
        self._reorder_paint_snapshot_exact_reuse_count = 0
        self._reorder_paint_snapshot_scroll_reuse_count = 0
        self._reorder_paint_snapshot_rebuild_count = 0

    def reorder_geometry_cache_counters(self) -> dict[str, object]:
        """Return per-gesture reorder cache counters for diagnostics summaries."""

        return {
            **self._reorder_geometry_cache.counters(),
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

        self._clear_base_drag_geometry_caches(reason=reason)
        self._clear_preview_chip_geometry_cache(reason=reason)

    def _clear_reorder_projection_and_geometry_caches(self, *, reason: str) -> None:
        """Invalidate reorder projection and geometry caches after metric changes."""

        self._reorder_preview_projection.clear_projection_cache(reason=reason)
        self._reorder_geometry_cache.clear_live_chip_geometry_cache(reason=reason)
        self._clear_reorder_geometry_caches(reason=reason)

    def _clear_base_drag_geometry_caches(self, *, reason: str) -> None:
        """Invalidate stable drag-base chip and placement geometry caches."""

        self._reorder_geometry_cache.clear_base_drag_geometry_caches(reason=reason)

    def _clear_preview_chip_geometry_cache(self, *, reason: str) -> None:
        """Invalidate cached preview chip geometry snapshots."""

        self._reorder_geometry_cache.clear_preview_chip_geometry_cache(reason=reason)

    def _reorder_chip_geometry_cache_key(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        projection_layout: PromptProjectionLayout,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderChipGeometryCacheKey:
        """Return the full identity for a reorder chip geometry snapshot."""

        return self._reorder_geometry_cache.chip_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout_identity=id(projection_layout),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=self._layout_width_for_projection_rebuild(),
        )

    def _reorder_placement_geometry_cache_key(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        projection_layout: PromptProjectionLayout,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> PromptReorderPlacementGeometryCacheKey:
        """Return the full identity for a reorder placement snapshot."""

        return self._reorder_geometry_cache.placement_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout_identity=id(projection_layout),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=self._layout_width_for_projection_rebuild(),
        )

    def _reorder_geometry_cache_context(
        self,
        key: PromptReorderChipGeometryCacheKey | PromptReorderPlacementGeometryCacheKey,
    ) -> dict[str, object]:
        """Return prompt-safe diagnostics for one reorder geometry cache key."""

        return self._reorder_geometry_cache.context(key)

    def _remember_preview_chip_geometry_cache(
        self,
        *,
        key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> None:
        """Store one preview chip snapshot and evict oldest entries if needed."""

        self._reorder_geometry_cache.remember_preview_chip_snapshot(
            key=key,
            snapshot=snapshot,
        )

    def _reuse_preview_chip_geometry_snapshot(
        self,
        snapshot: PromptReorderChipGeometrySnapshot,
    ) -> tuple[PromptReorderChipGeometrySnapshot, int, int, int]:
        """Reuse immutable chip geometries from recent preview snapshots when equal."""

        return self._reorder_geometry_cache.reuse_preview_chip_geometry_snapshot(
            snapshot
        )

    def reorder_preview_fragments(
        self,
        *,
        start: int,
        end: int,
    ) -> tuple[QRectF, ...]:
        """Return wrapped preview fragments for one raw preview source range."""

        if self._reorder_preview_projection.preview_layout is None:
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
        """Return projection-owned live reorder chip geometry."""

        started_at = reorder_drag_started_at()
        self._flush_pending_projection_update(reason="reorder_live_chip_geometry")
        viewport_rect = QRectF(self.viewport().rect())
        scroll_offset = self._scroll_offset()
        cache_key = self._reorder_geometry_cache.live_chip_geometry_cache_key(
            source_text=self._document_view.source_text,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            layout_view=layout_view,
            projection_layout_identity=id(self._layout),
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            layout_width=self._layout_width_for_projection_rebuild(),
        )
        snapshot = self._reorder_geometry_cache.live_chip_snapshot(cache_key)
        cache_hit = snapshot is not None
        if snapshot is None:
            scroll_candidate = self._reorder_geometry_cache.live_chip_scroll_candidate(
                cache_key
            )
            if scroll_candidate is None:
                snapshot = self._layout.reorder_chip_geometry_snapshot(
                    layout_view=layout_view,
                    chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
                    chip_owned_ranges_by_index=chip_owned_ranges_by_index,
                    viewport_rect=viewport_rect,
                    scroll_offset=scroll_offset,
                )
            else:
                previous_key, previous_snapshot = scroll_candidate
                scroll_result = build_reorder_geometry_after_scroll(
                    self._layout,
                    layout_view=layout_view,
                    chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
                    chip_owned_ranges_by_index=chip_owned_ranges_by_index,
                    previous_snapshot=previous_snapshot,
                    previous_viewport_rect=reorder_geometry_viewport_rect(
                        previous_key.viewport
                    ),
                    current_viewport_rect=viewport_rect,
                    current_scroll_offset=scroll_offset,
                )
                snapshot = scroll_result.snapshot
                self._reorder_geometry_cache.record_scroll_geometry_reuse(
                    translated_chip_count=scroll_result.translated_chip_count,
                    rebuilt_chip_count=scroll_result.rebuilt_chip_count,
                )
            self._reorder_geometry_cache.remember_live_chip_snapshot(
                key=cache_key,
                snapshot=snapshot,
            )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_live_chip_geometry_snapshot",
            started_at=started_at,
            cache_hit=cache_hit,
            **chip_geometry_snapshot_context(snapshot),
        )
        if elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.chip_geometry_snapshot",
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                snapshot_kind="live",
                **chip_geometry_snapshot_context(snapshot),
            )
        return snapshot

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned preview reorder chip geometry."""

        preview_layout = self._reorder_preview_projection.preview_layout
        if preview_layout is None:
            return PromptReorderChipGeometrySnapshot(
                geometries_by_chip_index={},
                ordered_chip_indices=(),
                visual_line_count=0,
                layout_width=float(self.viewport().width()),
                content_height=0.0,
                scroll_offset=float(self._scroll_offset()),
            )
        started_at = reorder_drag_started_at()
        self._flush_pending_projection_update(reason="reorder_preview_chip_geometry")
        viewport_rect = QRectF(self.viewport().rect())
        scroll_offset = self._scroll_offset()
        cache_key = self._reorder_chip_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout=preview_layout,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        cached_snapshot = self._reorder_geometry_cache.preview_chip_snapshot(cache_key)
        preview_state = self._reorder_preview_projection.preview_state
        if cached_snapshot is not None:
            log_reorder_drag_event(
                "cache.preview_chip_geometry.hit",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                **self._reorder_geometry_cache_context(cache_key),
            )
            log_reorder_drag_event(
                "preview_geometry.reused_chip_count",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                reused_chip_count=len(cached_snapshot.geometries_by_chip_index),
                rebuilt_chip_count=0,
                reuse_rejected_count=0,
                cache_hit=True,
                **self._reorder_geometry_cache_context(cache_key),
            )
            log_reorder_drag_timing(
                "surface.reorder_preview_chip_geometry_snapshot",
                started_at=started_at,
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                reason=""
                if preview_state is None
                else preview_state.instrumentation_reason,
                cache_hit=True,
                **chip_geometry_snapshot_context(cached_snapshot),
            )
            return cached_snapshot

        log_reorder_drag_event(
            "cache.preview_chip_geometry.miss",
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            **self._reorder_geometry_cache_context(cache_key),
        )
        scroll_candidate = self._reorder_geometry_cache.preview_chip_scroll_candidate(
            cache_key
        )
        if scroll_candidate is None:
            chip_snapshot = preview_layout.reorder_chip_geometry_snapshot(
                layout_view=layout_view,
                chip_rendered_ranges_by_index=(snapshot.chip_rendered_ranges_by_index),
                chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            )
            (
                chip_snapshot,
                reused_chip_count,
                rebuilt_chip_count,
                reuse_rejected_count,
            ) = self._reuse_preview_chip_geometry_snapshot(chip_snapshot)
        else:
            previous_key, previous_snapshot = scroll_candidate
            scroll_result = build_reorder_geometry_after_scroll(
                preview_layout,
                layout_view=layout_view,
                chip_rendered_ranges_by_index=(snapshot.chip_rendered_ranges_by_index),
                chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
                previous_snapshot=previous_snapshot,
                previous_viewport_rect=reorder_geometry_viewport_rect(
                    previous_key.viewport
                ),
                current_viewport_rect=viewport_rect,
                current_scroll_offset=scroll_offset,
            )
            chip_snapshot = scroll_result.snapshot
            reused_chip_count = scroll_result.translated_chip_count
            rebuilt_chip_count = scroll_result.rebuilt_chip_count
            reuse_rejected_count = 0
            self._reorder_geometry_cache.record_scroll_geometry_reuse(
                translated_chip_count=reused_chip_count,
                rebuilt_chip_count=rebuilt_chip_count,
            )
        log_reorder_drag_event(
            "preview_geometry.reused_chip_count",
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            reused_chip_count=reused_chip_count,
            rebuilt_chip_count=rebuilt_chip_count,
            reuse_rejected_count=reuse_rejected_count,
            cache_hit=False,
            **self._reorder_geometry_cache_context(cache_key),
        )
        log_reorder_drag_event(
            "preview_geometry.rebuilt_chip_count",
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            rebuilt_chip_count=rebuilt_chip_count,
            reused_chip_count=reused_chip_count,
            reuse_rejected_count=reuse_rejected_count,
            cache_hit=False,
            **self._reorder_geometry_cache_context(cache_key),
        )
        if reuse_rejected_count:
            log_reorder_drag_event(
                "preview_geometry.reuse_rejected",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                reuse_rejected_count=reuse_rejected_count,
                rebuilt_chip_count=rebuilt_chip_count,
                **self._reorder_geometry_cache_context(cache_key),
            )
        self._remember_preview_chip_geometry_cache(
            key=cache_key,
            snapshot=chip_snapshot,
        )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_preview_chip_geometry_snapshot",
            started_at=started_at,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            cache_hit=False,
            **chip_geometry_snapshot_context(chip_snapshot),
        )
        self._reorder_geometry_cache.record_preview_chip_elapsed(elapsed_ms)
        if elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.chip_geometry_snapshot",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                snapshot_kind="preview",
                **chip_geometry_snapshot_context(chip_snapshot),
            )
        return chip_snapshot

    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned live paint snapshots for visible reorder chips."""

        self._flush_pending_projection_update(reason="reorder_live_chip_visuals")
        snapshots = self._reorder_chip_projection_paint_snapshots(
            projection_layout=self._layout,
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

        preview_layout = self._reorder_preview_projection.preview_layout
        if preview_layout is None:
            return {}
        self._flush_pending_projection_update(reason="reorder_preview_chip_visuals")
        snapshots = self._reorder_chip_projection_paint_snapshots(
            projection_layout=preview_layout,
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
        projection_layout: PromptProjectionLayout,
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
                source_revision=self._source_revision,
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
        rebuilt_snapshots = projection_layout.reorder_projection_paint_snapshots(
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
            self._reorder_preview_projection.preview_layout is None
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

        if self._reorder_preview_projection.base_drag_layout is None:
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
        """Return projection-owned base-drag reorder chip geometry."""

        base_drag_layout = self._reorder_preview_projection.base_drag_layout
        if base_drag_layout is None:
            return PromptReorderChipGeometrySnapshot(
                geometries_by_chip_index={},
                ordered_chip_indices=(),
                visual_line_count=0,
                layout_width=float(self.viewport().width()),
                content_height=0.0,
                scroll_offset=float(self._scroll_offset()),
            )
        started_at = reorder_drag_started_at()
        viewport_rect = QRectF(self.viewport().rect())
        scroll_offset = self._scroll_offset()
        cache_key = self._reorder_chip_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout=base_drag_layout,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        preview_state = self._reorder_preview_projection.preview_state
        cached_chip_snapshot = self._reorder_geometry_cache.base_drag_chip_snapshot(
            cache_key
        )
        if cached_chip_snapshot is not None:
            chip_snapshot = cached_chip_snapshot
            log_reorder_drag_event(
                "cache.base_drag_chip_geometry.hit",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                **self._reorder_geometry_cache_context(cache_key),
            )
            log_reorder_drag_timing(
                "surface.reorder_base_drag_chip_geometry_snapshot",
                started_at=started_at,
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                reason=""
                if preview_state is None
                else preview_state.instrumentation_reason,
                cache_hit=True,
                **chip_geometry_snapshot_context(chip_snapshot),
            )
            return chip_snapshot
        log_reorder_drag_event(
            "cache.base_drag_chip_geometry.miss",
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            **self._reorder_geometry_cache_context(cache_key),
        )
        scroll_candidate = self._reorder_geometry_cache.base_drag_chip_scroll_candidate(
            cache_key
        )
        if scroll_candidate is None:
            chip_snapshot = base_drag_layout.reorder_chip_geometry_snapshot(
                layout_view=layout_view,
                chip_rendered_ranges_by_index=(snapshot.chip_rendered_ranges_by_index),
                chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
            )
        else:
            previous_key, previous_snapshot = scroll_candidate
            scroll_result = build_reorder_geometry_after_scroll(
                base_drag_layout,
                layout_view=layout_view,
                chip_rendered_ranges_by_index=(snapshot.chip_rendered_ranges_by_index),
                chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
                previous_snapshot=previous_snapshot,
                previous_viewport_rect=reorder_geometry_viewport_rect(
                    previous_key.viewport
                ),
                current_viewport_rect=viewport_rect,
                current_scroll_offset=scroll_offset,
            )
            chip_snapshot = scroll_result.snapshot
            self._reorder_geometry_cache.record_scroll_geometry_reuse(
                translated_chip_count=scroll_result.translated_chip_count,
                rebuilt_chip_count=scroll_result.rebuilt_chip_count,
            )
        self._reorder_geometry_cache.remember_base_drag_chip_snapshot(
            key=cache_key,
            snapshot=chip_snapshot,
        )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_base_drag_chip_geometry_snapshot",
            started_at=started_at,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            cache_hit=False,
            **chip_geometry_snapshot_context(chip_snapshot),
        )
        self._reorder_geometry_cache.record_base_drag_chip_elapsed(elapsed_ms)
        if elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.chip_geometry_snapshot",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                snapshot_kind="base_drag",
                **chip_geometry_snapshot_context(chip_snapshot),
            )
        return chip_snapshot

    def reorder_base_drag_cursor_rect(self, position: int) -> QRectF:
        """Return the stable drag-base caret rect for one raw preview source position."""

        if (
            self._reorder_preview_projection.base_drag_layout is None
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
        """Return projection-owned base-drag placement geometry."""

        base_drag_layout = self._reorder_preview_projection.base_drag_layout
        if base_drag_layout is None:
            return PromptReorderPlacementSnapshot(
                placements=(),
                visual_line_count=0,
                layout_width=float(self.viewport().width()),
                content_height=0.0,
            )
        started_at = reorder_drag_started_at()
        viewport_rect = QRectF(self.viewport().rect())
        scroll_offset = self._scroll_offset()
        cache_key = self._reorder_placement_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout=base_drag_layout,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        preview_state = self._reorder_preview_projection.preview_state
        cached_placement_snapshot = (
            self._reorder_geometry_cache.base_drag_placement_snapshot(cache_key)
        )
        if cached_placement_snapshot is not None:
            placement_snapshot = cached_placement_snapshot
            log_reorder_drag_event(
                "cache.base_drag_placement.hit",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                **self._reorder_geometry_cache_context(cache_key),
            )
            log_reorder_drag_timing(
                "surface.reorder_base_drag_placement_snapshot",
                started_at=started_at,
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                cache_hit=True,
                placement_count=len(placement_snapshot.placements),
                visual_line_count=placement_snapshot.visual_line_count,
                layout_width=f"{placement_snapshot.layout_width:.2f}",
                content_height=f"{placement_snapshot.content_height:.2f}",
            )
            return placement_snapshot

        log_reorder_drag_event(
            "cache.base_drag_placement.miss",
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            **self._reorder_geometry_cache_context(cache_key),
        )
        chip_snapshot = self.reorder_base_drag_chip_geometry_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )
        placement_snapshot = base_drag_layout.reorder_placement_snapshot(
            layout_view=layout_view,
            chip_geometry_snapshot=chip_snapshot,
            gap_ranges_by_index=snapshot.gap_ranges_by_index,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )
        self._reorder_geometry_cache.remember_base_drag_placement_snapshot(
            key=cache_key,
            snapshot=placement_snapshot,
        )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_base_drag_placement_snapshot",
            started_at=started_at,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            cache_hit=False,
            placement_count=len(placement_snapshot.placements),
            visual_line_count=placement_snapshot.visual_line_count,
            layout_width=f"{placement_snapshot.layout_width:.2f}",
            content_height=f"{placement_snapshot.content_height:.2f}",
        )
        self._reorder_geometry_cache.record_base_drag_placement_elapsed(elapsed_ms)
        if elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.placement_snapshot",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                placement_count=len(placement_snapshot.placements),
                visual_line_count=placement_snapshot.visual_line_count,
                layout_width=f"{placement_snapshot.layout_width:.2f}",
                content_height=f"{placement_snapshot.content_height:.2f}",
            )
        duplicate_targets = duplicate_reorder_placement_targets(placement_snapshot)
        if duplicate_targets:
            log_reorder_drag_event(
                "anomaly.placement_duplicate_target",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                duplicate_target_count=len(duplicate_targets),
                duplicate_targets=";".join(duplicate_targets),
                placement_count=len(placement_snapshot.placements),
            )
        return placement_snapshot

    def reorder_live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Build provisional placements from the already-current live projection."""

        self._flush_pending_projection_update(reason="reorder_live_placement")
        return self._layout.reorder_placement_snapshot(
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
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
                    for span in reversed(self._render_plan.syntax_spans)
                    if span.start == token.source_start and span.end == token.source_end
                ),
                None,
            )
        position = self.cursor_position
        for span in reversed(self._render_plan.syntax_spans):
            if span.start < position < span.end:
                return span
        return None

    def hovered_token(self) -> PromptProjectionToken | None:
        """Return the token currently under the pointer when present."""

        hovered_token_id = self._mouse_handler.hovered_token_id
        if hovered_token_id is None:
            return None
        return self._layout.effective_token_for_paint(hovered_token_id)

    def focused_token(self) -> PromptProjectionToken | None:
        """Return the token currently owning caret focus when present."""

        return self._projection_document.token_by_id(self._cursor_state.token_id)

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projected token painted under one viewport-local point."""

        return self._token_at_viewport_position(position)

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor rect used by any token controls."""

        return self._layout.token_anchor_rect(
            token,
            scroll_offset=self._scroll_offset(),
        )

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local projection-owned weight slot for one emphasis token."""

        return self._layout.token_weight_text_rect(
            token,
            scroll_offset=self._scroll_offset(),
        )

    def toPlainText(self) -> str:
        """Return the current raw prompt source text."""

        return self._editing_session.source_text

    def prompt_document_view(self) -> PromptDocumentView:
        """Return the current prepared prompt document view."""

        return self._document_view

    def set_defer_source_rebuilds_until_prompt_state(self, enabled: bool) -> None:
        """Set whether source edits wait for controller-owned prompt snapshots."""

        self._projection_freshness_controller.set_defer_source_rebuilds_until_prompt_state(
            enabled
        )

    def apply_edit_controller_result(
        self,
        result: PromptEditControllerResult[PromptProjectionUndoPayload, object],
    ) -> None:
        """Apply committed mutation results produced outside the projection surface."""

        self._source_change_applier.apply_edit_controller_result(result)

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
        caret_state = self._layout.hit_test(
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

        self._require_edit_block_actions().begin_surface_edit_block(
            finish_typing=finish_typing
        )

    def cursor_adapter_end_edit_block(self) -> None:
        """End an edit block requested by the source cursor adapter."""

        self._require_edit_block_actions().end_surface_edit_block()

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

    def set_prompt_state(
        self,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> None:
        """Replace the source snapshot and rebuild the token-aware projection."""

        if not qt_object_is_alive(self):
            return
        self._prompt_state_applier.set_prompt_state(document_view, render_plan)

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
            source_revision=self._source_revision,
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
                source_text=self._projection_document.source_text
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
        source_revision: int,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> None:
        """Record source revision and whether the next prompt state can be scheduled."""

        if not deferrable_projection:
            self._clear_transient_caret_geometry()
        self._source_revision = source_revision
        if self._reorder_preview_projection.preview_state is not None:
            self._clear_reorder_projection_and_geometry_caches(reason="source_changed")
        if clear_diagnostic_fragment_cache:
            self._clear_diagnostic_fragment_cache(reason="source_changed")
        self._invalidate_projection_content_cache(reason="source_changed")
        self._projection_paint_cache.skip_next_cache_build()
        self._projection_freshness_controller.mark_source_text_changed(
            deferrable_projection=deferrable_projection,
            source_revision=source_revision,
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
            source_revision=self._source_revision,
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
            self._document_view,
            self._render_plan,
            display_mode=self._display_mode,
            session=self._session,
            active_span_range=self._active_span_range(),
            decoration_accent_ranges=self._decoration_accent_ranges(),
            scene_error_keys=self._scene_error_keys,
            layout=self._layout,
        )
        if result is None:
            return False
        self._projection_freshness_controller.clear_pending_after_immediate_apply()
        self._projection_document = result.projection_document
        self._last_rendered_active_span_range = result.active_span_range
        self._active_projection_document = self._projection_document
        self._clear_transient_caret_geometry()
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
                for candidate in self._projection_document.tokens
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
            token = self._projection_document.token_by_id(token_id)
            if token is not None:
                return token
        edit_state = self._session.exact_weight_edit
        if edit_state is None:
            return None
        return next(
            (
                token
                for token in self._projection_document.tokens
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

    def _refresh_geometry_paint_signature(self) -> _RefreshGeometryPaintSignature:
        """Return visual state used to decide whether refresh_geometry repaints."""

        active_layout = self._reorder_preview_projection.preview_layout or self._layout
        content_size = active_layout.content_size()
        scroll_bar = self.verticalScrollBar()
        return _RefreshGeometryPaintSignature(
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

    def restore_clipboard_history_state(
        self,
        restore_result: PromptEditingSessionRestoreResult[PromptProjectionUndoPayload],
    ) -> None:
        """Apply an undo or redo restoration requested by the history owner."""

        self._source_change_applier.apply_restore_result(restore_result)

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
        for token in self._projection_document.tokens:
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
            self._projection_document.caret_map.state_for_source_position(
                cursor_state.cursor_position
            )
        )
        next_anchor_state = (
            self._projection_document.caret_map.state_for_source_position(
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
        resolved_cursor_state = self._projection_document.caret_map.resolve_state(
            cursor_state
        )
        resolved_anchor_state = self._projection_document.caret_map.resolve_state(
            anchor_state
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

        self._require_edit_block_actions().finish_surface_pending_key_edit_block(
            reason=reason
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Delegate projection-aware pointer press handling."""

        if self._mouse_handler.handle_mouse_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Delegate projection-aware pointer move handling."""

        if self._mouse_handler.handle_mouse_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Delegate projection-aware pointer release handling."""

        if self._mouse_handler.handle_viewport_mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Delegate token-aware double-click handling."""

        if self._mouse_handler.handle_mouse_double_click(event):
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
                    viewport_position=cast(QMouseEvent, event).position(),
                )
            if event.type() == QEvent.Type.MouseMove:
                return self._mouse_handler.handle_viewport_mouse_move(
                    cast(QMouseEvent, event),
                    viewport_position=cast(QMouseEvent, event).position(),
                )
            if event.type() == QEvent.Type.MouseButtonRelease:
                return self._mouse_handler.handle_viewport_mouse_release(
                    cast(QMouseEvent, event)
                )
            if event.type() == QEvent.Type.MouseButtonDblClick:
                return self._mouse_handler.handle_viewport_mouse_double_click(
                    cast(QMouseEvent, event),
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
                self._schedule_caret_blink_sync(reset_cycle=True)
            elif event.type() in {QEvent.Type.FocusOut, QEvent.Type.Hide}:
                self._schedule_caret_blink_sync(reset_cycle=False)
            elif event.type() == QEvent.Type.Show:
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

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the projection layout width in sync with the viewport."""

        super().resizeEvent(event)
        self._preferred_x = None
        self._caret_rect_override = None
        if not self._projection_freshness_controller.has_stale_projection_geometry():
            self._clear_transient_caret_geometry()
        self._clear_reorder_projection_and_geometry_caches(reason="resize")
        self._diagnostic_painter.advance_layout_revision(reason="resize")
        self._clear_diagnostic_fragment_cache(reason="resize")
        self.refresh_geometry()
        self.viewport().update()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Restart caret blinking when the surface itself gains focus ownership."""

        super().focusInEvent(event)
        self._schedule_caret_blink_sync(reset_cycle=True)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Stop caret blinking when the surface itself loses focus ownership."""

        self._finish_pending_key_edit_block(reason="focus_out")
        super().focusOutEvent(event)
        self._schedule_caret_blink_sync(reset_cycle=False)

    def showEvent(self, event: QShowEvent) -> None:
        """Resume caret blinking when the surface becomes visible again."""

        super().showEvent(event)
        self._schedule_caret_blink_sync(reset_cycle=False)
        self._prewarm_visible_lora_banners()

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop caret blinking while the surface is hidden."""

        previous_caret_rect = self._current_caret_rect()
        self._stop_caret_blink_cycle()
        self._update_caret_paint(previous_caret_rect)
        super().hideEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint either the live projection or the active reorder preview projection."""

        log_prompt_editor_probe(
            "surface.paint.begin",
            event_rect=repr(event.rect()),
            surface=surface_probe_state(self),
        )
        painter = QPainter(self.viewport())
        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            preview_layout = self._reorder_preview_projection.preview_layout
            if preview_layout is not None:
                started_at = reorder_drag_started_at()
                viewport_rect = QRectF(self.viewport().rect())
                scroll_offset = self._scroll_offset()
                self._paint_source_line_chrome(painter, layout=preview_layout)
                self._paint_reorder_surface_chrome(painter, mode="preview")
                preview_layout.draw(
                    painter,
                    selection=None,
                    scroll_offset=scroll_offset,
                    clip_rect=viewport_rect,
                    excluded_region=self._preview_visible_region(),
                )
                preview_state = self._reorder_preview_projection.preview_state
                log_reorder_drag_timing(
                    "surface.paint.preview",
                    started_at=started_at,
                    gesture_id=None
                    if preview_state is None
                    else preview_state.instrumentation_gesture_id,
                    event_id=None
                    if preview_state is None
                    else preview_state.instrumentation_event_id,
                    viewport_width=viewport_rect.width(),
                    viewport_height=viewport_rect.height(),
                    scroll_offset=scroll_offset,
                    preview_active=True,
                    line_count=preview_layout.line_count(),
                    text_fragment_count=preview_layout.text_fragment_count(),
                    inline_object_count=preview_layout.inline_object_fragment_count(),
                    clip_width=viewport_rect.width(),
                    clip_height=viewport_rect.height(),
                )
                return
            viewport_rect = QRectF(self.viewport().rect())
            paint_clip_rect = QRectF(event.rect()).intersected(viewport_rect)
            scroll_offset = self._scroll_offset()
            self._paint_source_line_chrome(painter, layout=self._layout)
            self._paint_reorder_surface_chrome(painter, mode="live")
            self._paint_search_matches(painter)
            deletion_visible_region = self._transient_deletion_visible_region()
            selection = self._selection()
            self._paint_projection_content(
                painter,
                selection=selection,
                scroll_offset=scroll_offset,
                clip_rect=paint_clip_rect,
                viewport_rect=viewport_rect,
                excluded_region=deletion_visible_region,
            )
            self._paint_transient_insertion_overlay(painter)
            self._paint_diagnostics(painter)
            self._paint_transient_deletion_overlay(painter)
            if self._should_paint_caret():
                paint_text_caret(
                    painter,
                    self._current_caret_rect(),
                    self.palette(),
                )
        finally:
            painter.end()
            log_prompt_editor_probe(
                "surface.paint.end",
                surface=surface_probe_state(self),
            )

    def _paint_projection_content(
        self,
        painter: QPainter,
        *,
        selection: PromptProjectionSelection,
        scroll_offset: float,
        clip_rect: QRectF,
        viewport_rect: QRectF,
        excluded_region: QRegion | None,
    ) -> str:
        """Delegate projection content painting to the projection paint cache."""

        if self._session.autocomplete_preview is not None:
            self._active_projection_paint_layout().draw(
                painter,
                selection=selection,
                scroll_offset=scroll_offset,
                clip_rect=clip_rect,
                excluded_region=excluded_region,
            )
            log_prompt_editor_probe(
                "surface.paint_projection_content.end",
                result="preview",
                clip_rect=repr(clip_rect),
                viewport_rect=repr(viewport_rect),
                surface=surface_probe_state(self),
            )
            return "preview"
        result = self._projection_paint_cache.paint_projection_content(
            painter,
            active_layout=self._active_projection_paint_layout(),
            base_layout=self._layout,
            selection=selection,
            scroll_offset=scroll_offset,
            clip_rect=clip_rect,
            viewport_rect=viewport_rect,
            excluded_region=excluded_region,
            source_revision=self._source_revision,
            device_pixel_ratio=float(self.devicePixelRatioF()),
            font=self.font(),
            palette=self.palette(),
            semantic_palette=semantic_palette_from_theme(),
        )
        log_prompt_editor_probe(
            "surface.paint_projection_content.end",
            result=result,
            clip_rect=repr(clip_rect),
            viewport_rect=repr(viewport_rect),
            surface=surface_probe_state(self),
        )
        return result

    def _invalidate_projection_content_cache(self, *, reason: str) -> None:
        """Delegate projection content cache invalidation to the cache owner."""

        self._projection_paint_cache.invalidate(reason=reason)

    def refresh_lora_thumbnail_paint(self, *, reason: str) -> None:
        """Invalidate cached LoRA chip paint and repaint the visible viewport."""

        self._invalidate_projection_content_cache(reason=reason)
        viewport = self.viewport()
        repaint_rect = viewport.rect()
        self.backingFillInvalidated.emit(repaint_rect)
        viewport.update(repaint_rect)
        viewport.repaint(repaint_rect)

    def _active_projection_paint_layout(self) -> PromptProjectionLayout:
        """Return the layout that currently owns projection content painting."""

        return self._layout

    def _paint_source_line_chrome(
        self,
        painter: QPainter,
        *,
        layout: PromptProjectionLayout,
    ) -> None:
        """Paint source-line chrome from the layout owning the visible content."""

        if not self._source_line_chrome.enabled:
            return
        self._source_line_chrome.paint_source_lines(
            painter,
            source_lines=self._source_line_chrome.source_line_rects(
                layout=layout,
                viewport_rect=QRectF(self.viewport().rect()),
                scroll_offset=self._scroll_offset(),
            ),
            current_line_index=self._source_line_chrome.current_source_line_index(
                layout=layout,
                cursor_position=self.cursor_position,
            ),
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

    def _reorder_preview_is_active(self) -> bool:
        """Return whether a reorder preview currently suppresses the live caret."""

        return self._reorder_preview_projection.is_active()

    def _paint_search_matches(self, painter: QPainter) -> None:
        """Paint transient search highlight ranges beneath text and selection."""

        self._source_line_chrome.paint_search_matches(
            painter,
            layout=self._active_projection_paint_layout(),
            match_ranges=self._session.search_match_ranges,
            active_match_index=self._session.active_search_match_index,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
            palette=self.palette(),
        )

    def _transient_insertion_overlay_viewport_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
    ) -> QRectF:
        """Return the viewport-local repaint rect for one transient text overlay."""

        return self._transient_edit_overlays.insertion_overlay_viewport_rect(
            overlay,
            metrics=self._layout.metrics,
            scroll_offset=self._scroll_offset(),
        )

    def _transient_insertion_overlay_document_rect(
        self,
        overlay: PromptProjectionTransientInsertionOverlay,
    ) -> QRectF:
        """Return the document-local paint rect for one transient text overlay."""

        return self._transient_edit_overlays.insertion_overlay_document_rect(
            overlay,
            metrics=self._layout.metrics,
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
            metrics=self._layout.metrics,
            scroll_offset=self._scroll_offset(),
        )
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

    def _transient_deletion_visible_region(self) -> QRegion | None:
        """Return the viewport region where stale projection text may still paint."""

        return self._transient_edit_overlays.deletion_visible_region(
            self._transient_edit_overlays.valid_deletion_overlay(
                freshness_is_stale_safe=(
                    self._projection_freshness_controller.has_stale_projection_geometry()
                ),
                source_revision=self._source_revision,
            ),
            viewport_region=QRegion(self.viewport().rect()),
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
        if repaint_rect is None:
            return
        self.viewport().update(repaint_rect.toAlignedRect())

    def _paint_diagnostics(self, painter: QPainter) -> None:
        """Paint diagnostic underlines using the semantic diagnostic palette."""

        viewport_rect = QRectF(self.viewport().rect())
        self._diagnostic_painter.paint(
            painter,
            diagnostics=self._session.diagnostics,
            selection=self._selection(),
            layout=self._layout,
            preview_layout=None,
            viewport_rect=viewport_rect,
            scroll_offset=self._scroll_offset(),
            source_revision=self._source_revision,
            color=qcolor_from_rgb(semantic_palette_from_theme().error_foreground),
        )

    def _schedule_diagnostic_fragment_cache_warm(self, *, reason: str) -> None:
        """Queue budgeted diagnostic fragment discovery outside paint events."""

        self._diagnostic_painter.schedule_warm(
            reason=reason,
            diagnostics=self._session.diagnostics,
            layout=self._layout,
            viewport_rect=QRectF(self.viewport().rect()),
            scroll_offset=self._scroll_offset(),
            source_revision=self._source_revision,
        )

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
        self._layout.prewarm_geometry_reuse_indexes()

    def _paint_transient_deletion_overlay(self, painter: QPainter) -> None:
        """Erase freshly deleted text while deferred projection catches up."""

        overlay = self._transient_edit_overlays.valid_deletion_overlay(
            freshness_is_stale_safe=(
                self._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_revision=self._source_revision,
        )
        if overlay is None:
            return
        viewport_rects = self._transient_deletion_overlay_erase_rects(overlay)
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        for rect in viewport_rects:
            painter.fillRect(rect, self.palette().base())
        painter.restore()

    def _paint_transient_insertion_overlay(self, painter: QPainter) -> None:
        """Paint freshly typed text while deferred projection catches up."""

        overlay = self._transient_edit_overlays.valid_insertion_overlay(
            freshness_is_stale_safe=(
                self._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_revision=self._source_revision,
        )
        if overlay is None:
            return
        text_rect = self._transient_insertion_overlay_viewport_rect(overlay)
        baseline = self._layout.metrics.text_baseline_for_row(
            row_top=text_rect.top(),
            row_height=text_rect.height(),
        )
        painter.save()
        painter.setFont(self.font())
        painter.fillRect(text_rect.adjusted(-1.0, 0.0, 1.0, 0.0), self.palette().base())
        painter.setPen(QColor(self.palette().color(QPalette.ColorRole.Text)))
        painter.drawText(QPointF(text_rect.left(), baseline), overlay.text)
        painter.restore()

    def _diagnostic_fragments_for_paint(
        self,
        diagnostic: PromptDiagnostic,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return cached diagnostic underline fragments for one paint pass."""

        return self._diagnostic_painter.diagnostic_fragments_for_paint(
            diagnostic=diagnostic,
            layout=self._layout,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            source_revision=self._source_revision,
        )

    def _clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Discard cached diagnostic underline fragments after geometry changes."""

        self._diagnostic_painter.clear_fragment_cache(reason=reason)

    def _preserve_diagnostic_fragment_cache_for_incremental_edit(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        next_layout_revision: int,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Keep unaffected diagnostic fragments after an accepted local edit."""

        self._diagnostic_painter.preserve_fragment_cache_for_incremental_edit(
            diagnostics=self._session.diagnostics,
            source_revision=self._source_revision,
            start=start,
            end=end,
            replacement_text=replacement_text,
            next_layout_revision=next_layout_revision,
            fragment_y_delta=fragment_y_delta,
        )

    def _update_incremental_plain_text_projection_paint(
        self,
        layout_result: PromptProjectionIncrementalLayoutResult,
    ) -> None:
        """Repaint only the visual lines changed by one accepted plain-text edit."""

        viewport_rect = QRectF(self.viewport().rect())
        repaint_rect = self._layout.visual_line_range_viewport_rect(
            first_line_index=layout_result.first_reflowed_line_index,
            line_count=max(1, layout_result.reflowed_line_count),
            viewport_rect=viewport_rect,
            scroll_offset=self._scroll_offset(),
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
        self._require_source_mutation_actions().replace_source_range(
            start=start,
            end=end,
            replacement_text=replacement_text,
            origin=origin,
        )

    def _syntax_sensitive_characters(self) -> frozenset[str]:
        """Return typed characters that require immediate projection semantics."""

        return frozenset(("(", ")", "{", "}", "<", ">", ":", "\\", "*"))

    def _typed_character_requires_immediate_projection(
        self,
        character: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one typed character must bypass safe projection deferral."""

        if character == ",":
            return self._comma_requires_immediate_projection(start=start, end=end)
        return character in self._syntax_sensitive_characters()

    def _can_defer_syntax_sensitive_autocomplete_prefix(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalized_text: str,
    ) -> bool:
        """Return whether syntax text is still only an autocomplete prefix."""

        if start != end or len(replacement_text) != 1:
            return False
        if replacement_text not in self._syntax_sensitive_characters():
            return False
        focused_token = self.focused_token()
        if (
            focused_token is not None
            and focused_token.source_start < start < focused_token.source_end
        ):
            return False

        next_position = start + len(replacement_text)
        if next_position < 0 or next_position > len(normalized_text):
            return False
        line_start = normalized_text.rfind("\n", 0, next_position) + 1
        delimiter_start = normalized_text.rfind(",", line_start, next_position) + 1
        prefix_start = max(line_start, delimiter_start)
        if focused_token is not None and start in {
            focused_token.source_start,
            focused_token.source_end,
        }:
            prefix_start = max(prefix_start, start)
        while prefix_start < next_position and normalized_text[prefix_start].isspace():
            prefix_start += 1
        prefix = normalized_text[prefix_start:next_position].casefold()
        if prefix == "<":
            return True
        return prefix.startswith("<lora:") and ">" not in prefix

    def _comma_requires_immediate_projection(self, *, start: int, end: int) -> bool:
        """Return whether comma typing is editing active syntax rather than prose."""

        if start != end:
            return True
        if self._display_mode is not PromptProjectionDisplayMode.PROJECTED:
            return True
        if self._reorder_preview_projection.is_active():
            return True
        if self._session.expanded_source_range is not None:
            return True
        if self._session.exact_weight_edit is not None:
            return True
        token = self.focused_token()
        return bool(token is not None and token.source_start < start < token.source_end)

    def _source_range_intersects_projected_token(self, *, start: int, end: int) -> bool:
        """Return whether one source range touches projected token syntax."""

        return any(
            start < token.source_end and token.source_start < end
            for token in self._projection_document.tokens
        )

    def _source_edit_requires_canonical_rebuild(
        self,
        previous_source_text: str,
        next_source_text: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one source-local edit changes canonical scene topology."""

        return self._projection_applicator.source_edit_requires_canonical_rebuild(
            previous_source_text,
            next_source_text,
            start=start,
            end=end,
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
            self._document_view,
            self._render_plan,
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
            text_length=len(self._document_view.source_text),
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

        self._projection_document = rebuild_result.projection_document
        self._last_rendered_active_span_range = rebuild_result.active_span_range
        self._diagnostic_painter.advance_layout_revision(reason=invalidation_reason)
        self._clear_diagnostic_fragment_cache(reason=invalidation_reason)
        self._cursor_state = rebuild_result.cursor_state
        self._anchor_state = rebuild_result.anchor_state
        self._sync_editing_session_to_caret_states()
        self._caret_rect_override = None
        self._rebuild_active_projection(commit_projection=True)
        self._prewarm_visible_lora_banners()
        self._clear_transient_caret_geometry()
        self.backingFillInvalidated.emit(self.viewport().rect())
        self.viewport().update()

    def preload_visible_lora_banners(self, *, on_complete: Callable[[], None]) -> bool:
        """Preload visible LoRA banners and notify when queued work is ready."""

        return self._lora_feature_delegate.preload_visible_banners(
            on_complete=on_complete
        )

    def _prewarm_visible_lora_banners(self) -> int:
        """Queue thumbnail loads for visible found LoRA chips after layout."""

        return self._lora_feature_delegate.prewarm_visible_banners()

    def _update_lora_thumbnail_pixmap(self, storage_key: str) -> None:
        """Repaint visible LoRA chips that reference a ready thumbnail asset."""

        self._lora_feature_delegate.update_lora_thumbnail_pixmap(storage_key)

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

    def _layout_width_for_projection_rebuild(self) -> float:
        """Return a non-pathological layout width for projection wrapping."""

        return (
            self._projection_freshness_controller.layout_width_for_projection_rebuild(
                viewport_width=self.viewport().width(),
                parent_width=self._nearest_valid_parent_layout_width(),
            )
        )

    def _nearest_valid_parent_layout_width(self) -> int | None:
        """Return an ancestor width usable before a hidden viewport is polished."""

        parent = self.parentWidget()
        while parent is not None:
            width = parent.width()
            if width >= _MINIMUM_VALID_LAYOUT_WIDTH:
                return width
            parent = parent.parentWidget()
        return None

    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Keep layout metrics in sync and optionally commit rebuilt projection freshness."""

        layout_width = self._layout_width_for_projection_rebuild()
        semantic_palette = semantic_palette_from_theme()
        sync_result = self._projection_applicator.sync_layout_state(
            layout=self._layout,
            reorder_preview_layout=self._reorder_preview_projection.preview_layout,
            reorder_base_drag_layout=self._reorder_preview_projection.base_drag_layout,
            layout_width=layout_width,
            font=self.font(),
            palette=self.palette(),
            semantic_palette=semantic_palette,
            content_left_inset=self._source_line_chrome.content_left_inset,
        )
        self._source_document_adapter.sync_default_font(self.font())
        self._source_document_adapter.sync_text_width(layout_width)
        content_height = sync_result.content_height
        viewport_height = max(1, self.viewport().height())
        scroll_range = max(0, math.ceil(content_height - viewport_height))
        self.verticalScrollBar()
        self.verticalScrollBar().setPageStep(viewport_height)
        self.verticalScrollBar().setRange(0, scroll_range)
        self._wheel_handler.sync_external_scroll_range(
            page_step=viewport_height,
            scroll_range=scroll_range,
        )
        should_emit_height = self._projection_freshness_controller.sync_layout_metrics(
            commit_projection=commit_projection,
            reorder_preview_active=self._reorder_preview_projection.is_active(),
            source_revision=self._source_revision,
            content_height=content_height,
            content_width=sync_result.content_width,
            layout_width=sync_result.layout_width,
            display_mode=self._display_mode,
        )
        if should_emit_height:
            self.contentHeightChanged.emit(content_height)

    def _reorder_preview_projection_context(
        self,
        preview_state: PromptReorderPreviewState | None,
    ) -> PromptReorderPreviewProjectionContext:
        """Return non-widget inputs that identify one reorder preview projection."""

        return PromptReorderPreviewProjectionContext(
            source_revision=self._source_revision,
            layout_width=self._layout_width_for_projection_rebuild(),
            viewport_width=self.viewport().width(),
            preview_layout_key=None
            if preview_state is None
            else preview_state.preview_layout_key,
            base_drag_layout_key=None
            if preview_state is None
            else preview_state.base_drag_layout_key,
            active_drop_target_identity=None
            if preview_state is None
            else preview_state.active_drop_target_identity,
        )

    def set_reorder_overlay_suppression_snapshots(
        self,
        snapshots_by_index: dict[int, PromptReorderProjectionPaintSnapshot],
    ) -> None:
        """Suppress fragments represented by exact overlay paint snapshots."""

        previous = self._reorder_overlay_suppression_snapshots_by_index
        if previous.keys() == snapshots_by_index.keys() and all(
            previous[index] is snapshot
            for index, snapshot in snapshots_by_index.items()
        ):
            return
        self._reorder_overlay_suppression_snapshots_by_index = dict(snapshots_by_index)
        self.viewport().update()

    def set_reorder_surface_chrome(
        self,
        *,
        mode: str,
        chips: tuple[PromptReorderSurfaceChromeChip, ...],
    ) -> None:
        """Publish stationary reorder chrome against the active projection identity."""

        if mode not in {"live", "preview"}:
            raise ValueError(f"Unsupported reorder surface chrome mode {mode!r}.")
        next_snapshot = (
            None
            if not chips
            else PromptReorderSurfaceChromeSnapshot(
                source_revision=self._source_revision,
                viewport_rect=self.viewport().rect(),
                scroll_offset=int(round(self._scroll_offset())),
                preview_generation=(
                    self._reorder_preview_generation() if mode == "preview" else None
                ),
                mode=mode,
                chips=chips,
            )
        )
        if self._reorder_surface_chrome_snapshot == next_snapshot:
            return
        self._reorder_surface_chrome_snapshot = next_snapshot
        self.viewport().update()

    def _paint_reorder_surface_chrome(
        self,
        painter: QPainter,
        *,
        mode: str,
    ) -> None:
        """Paint fresh stationary chrome below the active projection text."""

        snapshot = self._reorder_surface_chrome_snapshot
        if snapshot is None or not snapshot.matches(
            source_revision=self._source_revision,
            viewport_rect=self.viewport().rect(),
            scroll_offset=int(round(self._scroll_offset())),
            preview_generation=(
                self._reorder_preview_generation() if mode == "preview" else None
            ),
            mode=mode,
        ):
            return
        self._reorder_surface_chrome_painter.paint(painter, snapshot)

    def _preview_visible_region(self) -> QRegion | None:
        """Return the viewport region that should remain visible during preview paint."""

        preview_state = self._reorder_preview_projection.preview_state
        preview_layout = self._reorder_preview_projection.preview_layout
        if preview_state is None or preview_layout is None:
            return None
        suppression_snapshots = self._reorder_overlay_suppression_snapshots_by_index
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
            key.source_revision != self._source_revision
            or key.viewport_rect != self.viewport().rect()
            or key.scroll_offset != int(round(self._scroll_offset()))
            or key.preview_generation != self._reorder_preview_generation()
            or key.segment_index != chip_index
            or key.mode != "preview"
        )

    def undo_restoration_payload(self) -> PromptProjectionUndoPayload:
        """Return passive projection state for controller-owned undo snapshots."""

        return PromptProjectionUndoPayload(
            cursor_state=self._cursor_state,
            anchor_state=self._anchor_state,
            expanded_source_range=self._session.expanded_source_range,
            document_view=self._document_view,
            render_plan=self._render_plan,
            layout_checkpoint=self._layout.create_history_checkpoint(),
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
            direction,
            keep_anchor=keep_anchor,
        )

    def _move_vertically(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret vertically by adjacent visual line and preferred column."""

        self._caret_movement_controller.move_vertically(
            direction,
            keep_anchor=keep_anchor,
        )

    def _backspace(self) -> None:
        """Delete the previous raw source boundary or selection."""

        selection = self._selection()
        if not selection.is_empty:
            self._flush_pending_projection_update(reason="backspace")
            self._delete_viewport_selection()
            return
        if self.cursor_position <= 0:
            self._flush_pending_projection_update(reason="backspace_at_start")
            return
        if self._can_delete_raw_boundary_from_stale_projection(
            start=self.cursor_position - 1,
            end=self.cursor_position,
        ):
            self._replace_viewport_range(
                self.cursor_position - 1, self.cursor_position, ""
            )
            return
        if not self._cancel_stale_safe_projection_update(reason="backspace"):
            self._flush_pending_projection_update(reason="backspace")
        token = self.focused_token()
        previous_state = self._projection_document.caret_map.previous_state(
            self._cursor_state
        )
        if (
            token is not None
            and not self._session.is_expanded(token)
            and self._cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_CONTENT
            and previous_state.token_id == token.token_id
            and previous_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
        ):
            self._replace_viewport_range(
                previous_state.source_position, self.cursor_position, ""
            )
            return
        if token is not None and not self._session.is_expanded(token):
            self._session.expand_token(token)
            self._rebuild_projection()
            self.set_cursor_positions(
                cursor_position=token.source_end,
                anchor_position=token.source_start,
            )
            return
        if previous_state.source_position >= self.cursor_position:
            return
        self._replace_viewport_range(
            previous_state.source_position, self.cursor_position, ""
        )

    def _delete(self) -> None:
        """Delete the next raw source boundary or selection."""

        selection = self._selection()
        if not selection.is_empty:
            self._flush_pending_projection_update(reason="delete")
            self._delete_viewport_selection()
            return
        if self.cursor_position >= len(self.toPlainText()):
            self._flush_pending_projection_update(reason="delete_at_end")
            return
        if self._can_delete_raw_boundary_from_stale_projection(
            start=self.cursor_position,
            end=self.cursor_position + 1,
        ):
            self._replace_viewport_range(
                self.cursor_position, self.cursor_position + 1, ""
            )
            return
        if not self._cancel_stale_safe_projection_update(reason="delete"):
            self._flush_pending_projection_update(reason="delete")
        token = self.focused_token()
        next_state = self._projection_document.caret_map.next_state(self._cursor_state)
        if (
            token is not None
            and not self._session.is_expanded(token)
            and self._cursor_state.placement
            is PromptProjectionCaretPlacement.TOKEN_CONTENT
            and next_state.token_id == token.token_id
            and next_state.placement is PromptProjectionCaretPlacement.TOKEN_CONTENT
        ):
            self._replace_viewport_range(
                self.cursor_position, next_state.source_position, ""
            )
            return
        if token is not None and not self._session.is_expanded(token):
            self._session.expand_token(token)
            self._rebuild_projection()
            self.set_cursor_positions(
                cursor_position=token.source_end,
                anchor_position=token.source_start,
            )
            return
        if next_state.source_position <= self.cursor_position:
            return
        self._replace_viewport_range(
            self.cursor_position, next_state.source_position, ""
        )

    def _can_delete_raw_boundary_from_stale_projection(
        self,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether deletion can avoid flushing a pending projection first."""

        if start < 0 or end > len(self.toPlainText()):
            return False
        if self.toPlainText()[start:end] in {"\n", "\r", "\t"}:
            return False
        projection_source_is_stale = (
            self._projection_document.source_text != self.toPlainText()
        )
        return bool(
            (
                projection_source_is_stale
                or self._projection_freshness_controller.has_stale_projection_geometry()
            )
            and self._cursor_state.token_id is None
            and self._anchor_state.token_id is None
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
        return self._layout.cursor_rect(
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

        self._caret_visual_controller.update_caret_paint(previous_caret_rect)

    def _ensure_caret_visible(self) -> None:
        """Scroll the viewport vertically until the caret is visible."""

        self._caret_visual_controller.ensure_caret_visible()

    def _collapse_expanded_token_if_possible(self) -> None:
        """Collapse the expanded token once caret ownership has left a still-valid span."""

        collapsed = self._session.collapse_if_cursor_left_token(
            self._document_view,
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

    def _token_at_viewport_position(
        self,
        local_position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the token currently painted beneath one viewport-local point."""

        for token in reversed(self._projection_document.tokens):
            token_fragments = self._layout.token_fragments(
                token,
                scroll_offset=self._scroll_offset(),
            )
            if any(fragment.contains(local_position) for fragment in token_fragments):
                return token
        return None

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
