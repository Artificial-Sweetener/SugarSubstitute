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

"""Define projection source-state application contracts for committed edits."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Protocol, TypeVar, cast

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor.prompt_literal_parenthesis_normalizer import (
    PromptParenthesisTransitionKind,
)

from ..editing_session import (
    PromptEditingSessionRestoreResult,
    PromptEditingSessionSourceChange,
    PromptSourceEditOrigin,
    PromptUndoAvailabilityChange,
)
from ..editing_session.edit_controller import (
    PromptEditControllerResult,
    PromptOptimisticPromptState,
    PromptProjectionRestoreApplication,
    PromptProjectionSourceApplicationMode,
    PromptProjectionSourceChangeApplication,
)
from .freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .incremental_apply_controller import (
    PromptProjectionIncrementalApplyController,
    PromptProjectionSourceChangeApplyRequest,
)
from .layout_engine import PromptProjectionLayout
from .model import (
    PromptProjectionCaretState,
    PromptProjectionDocument,
    PromptProjectionToken,
)
from .observability import (
    log_projection_timing,
    projection_observability_started_at,
)
from .semantic_remap import (
    PromptProjectionOptimisticPromptState,
    PromptProjectionSemanticRemapper,
)
from .source_edit_projection_policy import PromptSourceEditProjectionPolicy
from .transient_edit_overlays import (
    PromptProjectionTransientCaretGeometry,
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)

TPayload = TypeVar("TPayload")
TProjectionPayload = TypeVar("TProjectionPayload")


class PromptProjectionSourceStateApplyPath(Enum):
    """Name how one committed source-state application affects projection state."""

    SIGNALS_ONLY = "signals_only"
    SOURCE_DOCUMENT_ONLY = "source_document_only"
    DEFERRED_OVERLAY = "deferred_overlay"
    PAINT_ONLY = "paint_only"
    FAST_TRAILING = "fast_trailing"
    INCREMENTAL = "incremental"
    SCHEDULED = "scheduled"
    CANCELLED_STALE = "cancelled_stale"
    FULL_REBUILD = "full_rebuild"
    REJECTED = "rejected"
    FAILED = "failed"


class PromptProjectionFreshnessState(Enum):
    """Describe whether projection metrics match the current source revision."""

    FRESH = "fresh"
    STALE_SAFE = "stale_safe"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceDocumentRangeEdit:
    """Describe a bounded source-document mirror edit."""

    previous_text: str
    next_text: str
    start: int
    end: int
    replacement_text: str


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceDocumentOutcome:
    """Describe how the plain source document mirror should be updated."""

    full_text: str | None = None
    range_edit: PromptProjectionSourceDocumentRangeEdit | None = None


@dataclass(frozen=True, slots=True)
class PromptProjectionViewportInvalidation:
    """Describe viewport and cache invalidation caused by source-state apply."""

    update_viewport: bool = False
    update_rects: tuple[object, ...] = ()
    invalidate_layout: bool = False
    invalidate_paint_cache: bool = False
    invalidate_diagnostic_fragments: bool = False
    content_height_changed: float | None = None


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretSync:
    """Describe caret updates the viewport surface should apply."""

    cursor_position: int | None = None
    anchor_position: int | None = None
    ensure_visible: bool = False
    restart_blink: bool = False
    use_transient_geometry: bool = False
    mark_horizontal_movement_origin: bool = False


@dataclass(frozen=True, slots=True)
class PromptProjectionFreshnessOutcome:
    """Describe freshness state and pending projection-update side effects."""

    source_revision: int | None = None
    state: PromptProjectionFreshnessState | None = None
    schedule_reason: str | None = None
    cancel_pending: bool = False
    flush_reason: str | None = None
    committed_metrics_changed: bool = False
    last_source_edit_deferrable: bool = False


@dataclass(frozen=True, slots=True)
class PromptProjectionSignalOutcome:
    """Describe Qt signal emissions without emitting them in the owner."""

    emit_text_changed: bool = False
    emit_cursor_position_changed: bool = False
    emit_undo_available_changed: bool | None = None
    emit_redo_available_changed: bool | None = None


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceStateApplicationRequest(Generic[TPayload]):
    """Carry one Phase 21 committed application into projection source-state apply."""

    application: (
        PromptProjectionSourceChangeApplication[TPayload]
        | PromptProjectionRestoreApplication[TPayload]
    )
    current_source_revision: int
    current_projection_source_text: str
    reason: str


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceStateOutcome:
    """Carry typed effects from source-state apply back to the viewport surface."""

    apply_path: PromptProjectionSourceStateApplyPath
    source_revision: int | None = None
    source_document: PromptProjectionSourceDocumentOutcome = field(
        default_factory=PromptProjectionSourceDocumentOutcome
    )
    viewport: PromptProjectionViewportInvalidation = field(
        default_factory=PromptProjectionViewportInvalidation
    )
    caret: PromptProjectionCaretSync = field(default_factory=PromptProjectionCaretSync)
    freshness: PromptProjectionFreshnessOutcome = field(
        default_factory=PromptProjectionFreshnessOutcome
    )
    signals: PromptProjectionSignalOutcome = field(
        default_factory=PromptProjectionSignalOutcome
    )
    clear_autocomplete_preview: bool = False
    clear_pointer_state: bool = False
    remap_diagnostics: bool = False
    preserve_source_line_chrome: bool = True
    schedule_geometry_reuse_warm_reason: str | None = None


class PromptProjectionSourceStateOwner(Protocol[TPayload]):
    """Apply committed source-state changes without owning command routing."""

    def apply_source_state_change(
        self,
        request: PromptProjectionSourceStateApplicationRequest[TPayload],
    ) -> PromptProjectionSourceStateOutcome:
        """Return viewport-safe effects for one committed source-state change."""


class PromptProjectionRestorePayload(Protocol):
    """Describe projection state needed to restore an undo snapshot."""

    cursor_state: PromptProjectionCaretState
    anchor_state: PromptProjectionCaretState
    expanded_source_range: tuple[int, int] | None
    document_view: PromptDocumentView
    render_plan: PromptSyntaxRenderPlan


class PromptProjectionNoArgSignal(Protocol):
    """Represent a Qt signal with no payload for source-change application."""

    def emit(self) -> None:
        """Emit the signal."""


class PromptProjectionSourceChangeViewport(Protocol):
    """Represent the viewport operations source-change application needs."""

    def width(self) -> int:
        """Return the viewport width."""

    def height(self) -> int:
        """Return the viewport height."""

    def update(self) -> None:
        """Request a viewport repaint."""


class PromptProjectionSourceChangeScrollBar(Protocol):
    """Represent the scroll operation used by full-source replacements."""

    def setValue(self, value: int) -> None:  # noqa: N802
        """Set the current scroll value."""


class PromptProjectionSourceDocumentMirror(Protocol):
    """Expose source-document mirror operations needed by the applier."""

    def sync_default_font(self, font: QFont) -> None:
        """Synchronize the mirror default font."""

    def replace_with_range_fallback(
        self,
        *,
        next_text: str,
        previous_text: str | None,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> bool:
        """Mirror committed text with a bounded edit fallback."""

    def replace_text(self, text: str) -> None:
        """Replace the mirror text exactly."""


class PromptProjectionSourceChangeMouseHandler(Protocol):
    """Expose source-change pointer cleanup owned by mouse interactions."""

    def clear_pointer_state_for_source_replacement(self) -> None:
        """Clear pointer state after a committed source replacement."""


class PromptProjectionSourceChangeSession(Protocol):
    """Expose session state touched by committed source-change application."""

    diagnostics: tuple[PromptDiagnostic, ...]
    autocomplete_preview: object | None
    expanded_source_range: tuple[int, int] | None

    def set_diagnostics(self, diagnostics: tuple[PromptDiagnostic, ...]) -> None:
        """Replace visible diagnostics."""

    def set_pending_auto_exact_weight_edit(
        self,
        *,
        source_text: str,
        cursor_position: int,
    ) -> None:
        """Remember an auto-created emphasis token should enter exact edit."""


class PromptProjectionSourceChangeHost(Protocol):
    """Surface-side operations the Phase 22.3 applier coordinates."""

    textChanged: PromptProjectionNoArgSignal
    cursorPositionChanged: PromptProjectionNoArgSignal
    _session: PromptProjectionSourceChangeSession
    _mouse_handler: PromptProjectionSourceChangeMouseHandler
    _source_document_adapter: PromptProjectionSourceDocumentMirror
    _projection_freshness_controller: PromptProjectionFreshnessController
    _incremental_apply_controller: PromptProjectionIncrementalApplyController
    _document_view: PromptDocumentView
    _render_plan: PromptSyntaxRenderPlan
    _projection_document: PromptProjectionDocument
    _layout: PromptProjectionLayout
    _source_revision: int
    _caret_visibility_prompt_state_revision: int
    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _caret_rect_override: QRectF | None
    _transient_edit_overlays: PromptProjectionTransientEditOverlayController
    _preferred_x: float | None

    def emit_undo_available_changed(self, available: bool) -> None:
        """Emit an undo availability transition."""

    def emit_redo_available_changed(self, available: bool) -> None:
        """Emit a redo availability transition."""

    def notify_implicit_parenthesis_authored(self, nesting_depth: int) -> None:
        """Publish authored nested implicit emphasis to its education owner."""

    def set_cursor_positions(
        self, *, cursor_position: int, anchor_position: int
    ) -> object:
        """Set the source cursor and anchor positions."""

    def verticalScrollBar(self) -> PromptProjectionSourceChangeScrollBar:  # noqa: N802
        """Return the active vertical scrollbar."""

    def viewport(self) -> PromptProjectionSourceChangeViewport:
        """Return the projection viewport."""

    def font(self) -> QFont:
        """Return the current surface font."""

    def _schedule_projection_geometry_reuse_warm(self, *, reason: str) -> None:
        """Schedule geometry reuse warmup."""

    def clear_autocomplete_preview_state(self) -> None:
        """Clear autocomplete preview through the authoritative preview owner."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return the live source text."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return current projection modes that block source-state deferral."""

    def _typed_character_requires_immediate_projection(
        self,
        character: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one character must rebuild projection immediately."""

    def _can_defer_syntax_sensitive_autocomplete_prefix(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalized_text: str,
    ) -> bool:
        """Return whether autocomplete can tolerate one syntax-sensitive prefix."""

    def _source_range_intersects_projected_token(
        self,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one source range intersects projected token syntax."""

    def _current_caret_document_rect(self) -> QRectF:
        """Return the current document-local caret rectangle."""

    def _mark_source_text_changed(
        self,
        *,
        deferrable_projection: bool,
        source_revision: int,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> None:
        """Record a source text change."""

    def _clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Clear diagnostic fragment cache state."""

    def _set_deferred_source_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Set caret states while wrap reflow is deferred."""

    def _set_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        reset_preferred_x: bool = True,
        caret_rect_override: QRectF | None = None,
        collapse_expanded_token: bool = True,
        reason: str = "generic",
    ) -> None:
        """Set committed caret states."""

    def _sync_editing_session_to_caret_states(self) -> object:
        """Synchronize editing-session cursor state from caret states."""

    def _ensure_caret_visible(self) -> None:
        """Ensure the caret is visible."""

    def _update_transient_insertion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
    ) -> None:
        """Update insertion overlay paint regions."""

    def _update_transient_deletion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Update deletion overlay paint regions."""

    def _restart_caret_blink_cycle(self) -> None:
        """Restart the caret blink cycle."""

    def _clear_transient_caret_geometry(self) -> None:
        """Clear transient caret and edit overlays."""

    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Synchronize layout state."""

    def _rebuild_active_projection(self, *, commit_projection: bool = False) -> None:
        """Rebuild active projection layout after committed projection changes."""

    def _rebuild_projection(self) -> None:
        """Rebuild projection through the surface sink."""

    def _mark_source_edit_horizontal_movement_origin(self) -> None:
        """Mark horizontal movement origin after a source edit."""

    def start_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start exact weight editing for one projected token."""

    def update_exact_weight_edit(
        self,
        *,
        buffer_text: str,
        caret_index: int,
        select_all: bool,
    ) -> None:
        """Update the active exact weight edit buffer."""


class PromptProjectionSourceChangeApplier(Generic[TProjectionPayload]):
    """Apply committed source changes without owning command construction."""

    def __init__(
        self,
        host: object,
        *,
        semantic_remapper: PromptProjectionSemanticRemapper | None = None,
    ) -> None:
        """Store source-change collaborators used by committed edit application."""

        self._host = cast(PromptProjectionSourceChangeHost, host)
        self._semantic_remapper = (
            semantic_remapper
            if semantic_remapper is not None
            else PromptProjectionSemanticRemapper()
        )
        self._source_edit_projection_policy = PromptSourceEditProjectionPolicy()

    def apply_edit_controller_result(
        self,
        result: PromptEditControllerResult[TProjectionPayload, object],
    ) -> None:
        """Apply committed mutation results produced outside the projection surface."""

        for application in result.source_applications:
            if isinstance(application, PromptProjectionRestoreApplication):
                self.apply_restore_application(application)
                continue
            self.apply_source_change_application(application)

    def apply_source_change_application(
        self,
        application: PromptProjectionSourceChangeApplication[TProjectionPayload],
    ) -> None:
        """Apply one committed source change using the requested projection strategy."""

        host = self._host
        if application.mode is PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT:
            self._apply_source_replacement_source_change(
                previous_text=application.previous_source_text,
                source_change=application.source_change,
                undo_availability_change=(
                    application.signal_intent.undo_availability_change
                ),
                origin=application.origin,
            )
            return
        if application.mode is PromptProjectionSourceApplicationMode.FULL_SOURCE:
            self._emit_undo_availability_change(
                application.signal_intent.undo_availability_change
            )
            self._apply_editing_session_source_change(
                application.source_change,
                emit_text_changed=application.signal_intent.emit_text_changed,
                optimistic_prompt_state=self._projection_prompt_state_tuple(
                    application.optimistic_prompt_state
                ),
                source_edit_start=application.source_edit_start,
                source_edit_end=application.source_edit_end,
                source_edit_replacement_text=(application.source_edit_replacement_text),
                previous_source_text=application.previous_source_text,
                origin=application.origin,
            )
            if application.reset_scroll_to_top:
                host.verticalScrollBar().setValue(0)
            if application.schedule_geometry_reuse_warm_reason is not None:
                host._schedule_projection_geometry_reuse_warm(
                    reason=application.schedule_geometry_reuse_warm_reason
                )

    def apply_restore_application(
        self,
        application: PromptProjectionRestoreApplication[TProjectionPayload],
    ) -> None:
        """Apply one committed undo/redo restore application."""

        self._emit_undo_availability_change(
            application.signal_intent.undo_availability_change
        )
        self._restore_undo_state(application.restore_result)

    def apply_restore_result(
        self,
        restore_result: PromptEditingSessionRestoreResult[TProjectionPayload],
    ) -> None:
        """Apply one restore result from clipboard/history owners."""

        self._restore_undo_state(restore_result)

    def _projection_prompt_state_tuple(
        self,
        optimistic_prompt_state: PromptOptimisticPromptState | None,
    ) -> PromptProjectionOptimisticPromptState | None:
        """Return projection-typed optimistic state from the edit result protocol."""

        if optimistic_prompt_state is None:
            return None
        document_view = optimistic_prompt_state.document_view
        render_plan = optimistic_prompt_state.render_plan
        if not isinstance(document_view, PromptDocumentView):
            return None
        if not isinstance(render_plan, PromptSyntaxRenderPlan):
            return None
        return document_view, render_plan

    def _emit_undo_availability_change(
        self,
        availability_change: PromptUndoAvailabilityChange | None,
    ) -> None:
        """Emit undo/redo availability from a committed projection application."""

        if availability_change is None:
            return
        host = self._host
        if availability_change.undo_changed:
            host.emit_undo_available_changed(availability_change.current.can_undo)
        if availability_change.redo_changed:
            host.emit_redo_available_changed(availability_change.current.can_redo)

    def _remap_diagnostics_for_source_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> None:
        """Keep visible diagnostic ranges aligned with a local source edit."""

        host = self._host
        if start is None or end is None or replacement_text is None:
            return
        if not host._session.diagnostics:
            return
        next_diagnostics = self._semantic_remapper.remap_diagnostics_for_edit(
            host._session.diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )
        if next_diagnostics == host._session.diagnostics:
            return
        host._session.set_diagnostics(next_diagnostics)

    def _apply_editing_session_source_change(
        self,
        source_change: PromptEditingSessionSourceChange[TProjectionPayload],
        *,
        emit_text_changed: bool,
        rebuild_immediately: bool = True,
        deferrable_projection: bool = False,
        transient_caret_geometry: PromptProjectionTransientCaretGeometry | None = None,
        transient_insertion_overlay: (
            PromptProjectionTransientInsertionOverlay | None
        ) = None,
        transient_deletion_overlay: PromptProjectionTransientDeletionOverlay
        | None = None,
        optimistic_prompt_state: PromptProjectionOptimisticPromptState | None = None,
        source_edit_start: int | None = None,
        source_edit_end: int | None = None,
        source_edit_replacement_text: str | None = None,
        previous_source_text: str | None = None,
        refresh_caret_after_prompt_state: bool = False,
        projection_deferral_reason: str = "",
        origin: PromptSourceEditOrigin = PromptSourceEditOrigin.PROGRAMMATIC,
    ) -> None:
        """Mirror an editing-session source change into projection-owned state."""

        host = self._host
        text = source_change.next_snapshot.source_text
        cursor_position = source_change.cursor_state.cursor_position
        anchor_position = source_change.cursor_state.anchor_position
        source_revision = source_change.next_snapshot.source_revision
        previous_document_view = host._document_view
        previous_render_plan = host._render_plan
        previous_projection_freshness = host._projection_freshness_controller.freshness
        previous_deletion_overlay = self._valid_transient_deletion_overlay()
        if host._session.autocomplete_preview is not None:
            host.clear_autocomplete_preview_state()
        can_preserve_diagnostic_fragment_cache = (
            previous_source_text is not None
            and source_edit_start is not None
            and source_edit_end is not None
            and source_edit_replacement_text is not None
            and source_edit_end - source_edit_start <= 1
            and len(source_edit_replacement_text) <= 1
        )
        host._mark_source_text_changed(
            deferrable_projection=deferrable_projection,
            source_revision=source_revision,
            clear_diagnostic_fragment_cache=(
                not can_preserve_diagnostic_fragment_cache
            ),
        )
        if emit_text_changed and refresh_caret_after_prompt_state:
            host._caret_visibility_prompt_state_revision = host._source_revision
        document_view_started_at = projection_observability_started_at()
        if optimistic_prompt_state is None:
            optimistic_prompt_state = (
                self._semantic_remapper.optimistic_prompt_state_for_source_edit(
                    current_document_view=host._document_view,
                    current_render_plan=host._render_plan,
                    previous_text=previous_source_text,
                    next_text=text,
                    start=source_edit_start,
                    end=source_edit_end,
                    replacement_text=source_edit_replacement_text,
                )
            )
        if optimistic_prompt_state is None:
            host._document_view = PromptDocumentView(
                source_text=text,
                segments=(),
                emphasis_spans=(),
                wildcard_spans=(),
                lora_spans=(),
                syntax_spans=(),
                has_trailing_comma=False,
            )
            host._render_plan = PromptSyntaxRenderPlan(
                syntax_spans=(),
                renderer_views=(),
            )
        else:
            host._document_view, host._render_plan = optimistic_prompt_state
        self._remap_diagnostics_for_source_edit(
            start=source_edit_start,
            end=source_edit_end,
            replacement_text=source_edit_replacement_text,
        )
        next_cursor_state = PromptProjectionCaretState(
            source_position=max(0, min(cursor_position, len(text)))
        )
        next_anchor_state = PromptProjectionCaretState(
            source_position=max(0, min(anchor_position, len(text)))
        )
        if any(
            transition.kind
            is PromptParenthesisTransitionKind.ESCAPED_LITERAL_TO_EMPHASIS
            for transition in source_change.transitions
        ):
            host._session.set_pending_auto_exact_weight_edit(
                source_text=text,
                cursor_position=next_cursor_state.source_position,
            )
        if origin is PromptSourceEditOrigin.TYPED:
            authored_depth = max(
                (
                    transition.nesting_depth
                    for transition in source_change.transitions
                    if transition.kind
                    is PromptParenthesisTransitionKind.IMPLICIT_EMPHASIS
                ),
                default=0,
            )
            if authored_depth >= 2:
                host.notify_implicit_parenthesis_authored(authored_depth)
        host._mouse_handler.clear_pointer_state_for_source_replacement()
        log_projection_timing(
            "source_change.prepare_document_view",
            started_at=document_view_started_at,
            text_length=len(text),
            emit_text_changed=emit_text_changed,
        )
        qtext_document_started_at = projection_observability_started_at()
        host._source_document_adapter.sync_default_font(host.font())
        host._source_document_adapter.replace_with_range_fallback(
            next_text=text,
            previous_text=previous_source_text,
            start=source_edit_start,
            end=source_edit_end,
            replacement_text=source_edit_replacement_text,
        )
        log_projection_timing(
            "source_change.qtext_document",
            started_at=qtext_document_started_at,
            text_length=len(text),
        )
        if rebuild_immediately:
            self._apply_immediate_projection(
                text=text,
                previous_source_text=previous_source_text,
                source_edit_start=source_edit_start,
                source_edit_end=source_edit_end,
                source_edit_replacement_text=source_edit_replacement_text,
                previous_projection_freshness=previous_projection_freshness,
                previous_document_view=previous_document_view,
                previous_render_plan=previous_render_plan,
                previous_deletion_overlay=previous_deletion_overlay,
                next_cursor_state=next_cursor_state,
                next_anchor_state=next_anchor_state,
                can_preserve_diagnostic_fragment_cache=(
                    can_preserve_diagnostic_fragment_cache
                ),
                projection_deferral_reason=projection_deferral_reason,
            )
        else:
            self._apply_deferred_projection(
                text=text,
                transient_caret_geometry=transient_caret_geometry,
                transient_insertion_overlay=transient_insertion_overlay,
                transient_deletion_overlay=transient_deletion_overlay,
                next_cursor_state=next_cursor_state,
                next_anchor_state=next_anchor_state,
            )
        if source_edit_start is not None and source_edit_end is not None:
            host._mark_source_edit_horizontal_movement_origin()
        if emit_text_changed:
            host.textChanged.emit()
        host.cursorPositionChanged.emit()

    def _apply_immediate_projection(
        self,
        *,
        text: str,
        previous_source_text: str | None,
        source_edit_start: int | None,
        source_edit_end: int | None,
        source_edit_replacement_text: str | None,
        previous_projection_freshness: ProjectionFreshness,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
        previous_deletion_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_cursor_state: PromptProjectionCaretState,
        next_anchor_state: PromptProjectionCaretState,
        can_preserve_diagnostic_fragment_cache: bool,
        projection_deferral_reason: str,
    ) -> None:
        """Apply immediate projection refresh, preserving the existing ordering."""

        host = self._host
        projection_started_at = projection_observability_started_at()
        outcome = host._incremental_apply_controller.apply_source_change_projection(
            PromptProjectionSourceChangeApplyRequest(
                text=text,
                previous_source_text=previous_source_text,
                source_edit_start=source_edit_start,
                source_edit_end=source_edit_end,
                source_edit_replacement_text=source_edit_replacement_text,
                previous_projection_freshness=previous_projection_freshness,
                previous_document_view=previous_document_view,
                previous_render_plan=previous_render_plan,
                previous_deletion_overlay=previous_deletion_overlay,
                next_cursor_state=next_cursor_state,
                next_anchor_state=next_anchor_state,
                can_preserve_diagnostic_fragment_cache=(
                    can_preserve_diagnostic_fragment_cache
                ),
                projection_deferral_reason=projection_deferral_reason,
            )
        )
        log_projection_timing(
            "source_change.immediate_projection",
            started_at=projection_started_at,
            text_length=len(text),
            apply_path=outcome.apply_path.value,
            fast_projection_applied=outcome.fast_projection_applied,
            wrap_reflow_deferred=outcome.wrap_reflow_deferred,
        )
        if outcome.wrap_reflow_deferred:
            host._set_deferred_source_caret_states(
                cursor_state=next_cursor_state,
                anchor_state=next_anchor_state,
            )
        else:
            host._set_caret_states(
                cursor_state=next_cursor_state,
                anchor_state=next_anchor_state,
                collapse_expanded_token=not outcome.fast_projection_applied,
                reason=(
                    "fast_source_replace"
                    if outcome.fast_projection_applied
                    else "immediate_source_replace"
                ),
            )

    def _apply_deferred_projection(
        self,
        *,
        text: str,
        transient_caret_geometry: PromptProjectionTransientCaretGeometry | None,
        transient_insertion_overlay: PromptProjectionTransientInsertionOverlay | None,
        transient_deletion_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_cursor_state: PromptProjectionCaretState,
        next_anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Apply deferred projection state for one source edit."""

        host = self._host
        previous_insertion_overlay = host._transient_edit_overlays.insertion_overlay
        previous_deletion_overlay = host._transient_edit_overlays.deletion_overlay
        host._cursor_state = next_cursor_state
        host._anchor_state = next_anchor_state
        host._sync_editing_session_to_caret_states()
        host._caret_rect_override = (
            QRectF(transient_caret_geometry.document_rect)
            if transient_caret_geometry is not None
            else None
        )
        host._transient_edit_overlays.set_overlays(
            caret_geometry=transient_caret_geometry,
            insertion_overlay=transient_insertion_overlay,
            deletion_overlay=transient_deletion_overlay,
        )
        host._ensure_caret_visible()
        host._update_transient_insertion_overlay_paint(
            previous_insertion_overlay,
            transient_insertion_overlay,
        )
        host._update_transient_deletion_overlay_paint(
            previous_deletion_overlay,
            transient_deletion_overlay,
        )
        self._commit_deferred_projection_if_source_matches(text)
        host._restart_caret_blink_cycle()

    def _commit_deferred_projection_if_source_matches(self, text: str) -> None:
        """Mark a deferred edit fresh when it returns to the committed projection."""

        host = self._host
        if text != host._projection_document.source_text:
            return
        if host._transient_edit_overlays.insertion_overlay is not None:
            return
        if host._transient_edit_overlays.deletion_overlay is not None:
            return
        host._projection_freshness_controller.clear_pending_after_immediate_apply()
        host._clear_transient_caret_geometry()
        host._rebuild_active_projection(commit_projection=True)

    def _can_defer_source_rebuild_for_edit(
        self,
        *,
        start: int,
        end: int,
        replaced_text: str,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        updated_text: str,
        normalized_text: str,
    ) -> tuple[bool, str]:
        """Return whether one edit can wait for controller-owned prompt state."""

        host = self._host
        return host._projection_freshness_controller.can_defer_source_rebuild_for_edit(
            blockers=host._projection_freshness_blockers(),
            start=start,
            end=end,
            replaced_text=replaced_text,
            replacement_text=replacement_text,
            origin=origin,
            updated_text=updated_text,
            normalized_text=normalized_text,
            edit_inside_projected_token=(
                self._source_insertion_is_inside_projected_token(start)
            ),
            delete_intersects_projected_token=(
                host._source_range_intersects_projected_token(start=start, end=end)
            ),
            typed_character_requires_immediate_projection=(
                bool(replacement_text)
                and host._typed_character_requires_immediate_projection(
                    replacement_text,
                    start=start,
                    end=end,
                )
            ),
            syntax_sensitive_autocomplete_prefix=(
                bool(replacement_text)
                and host._can_defer_syntax_sensitive_autocomplete_prefix(
                    start=start,
                    end=end,
                    replacement_text=replacement_text,
                    normalized_text=normalized_text,
                )
            ),
        )

    def _valid_transient_deletion_overlay(
        self,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return the current valid transient deletion overlay."""

        host = self._host
        return host._transient_edit_overlays.valid_deletion_overlay(
            freshness_is_stale_safe=(
                host._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_revision=host._source_revision,
        )

    def _transient_committed_source_revision(self) -> int:
        """Return the source revision owned by committed projection geometry."""

        host = self._host
        return (
            host._projection_freshness_controller.transient_committed_source_revision(
                current_source_revision=host._source_revision
            )
        )

    def _transient_content_right(self) -> float:
        """Return the document-local right edge used by transient overlay math."""

        content_width = self._host._layout.content_size().width()
        if content_width > 1.0:
            return content_width
        return float(self._host.viewport().width())

    def _deletion_targets_transient_insertion_overlay(
        self,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one delete only removes pending inserted overlay text."""

        host = self._host
        return host._transient_edit_overlays.deletion_targets_insertion_overlay(
            start=start,
            end=end,
            freshness_is_stale_safe=(
                host._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_revision=host._source_revision,
        )

    def _can_defer_transient_insertion_overlay(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> bool:
        """Return whether one insertion can be painted without changing layout."""

        host = self._host
        return host._transient_edit_overlays.can_defer_insertion_overlay(
            start=start,
            end=end,
            replacement_text=replacement_text,
            live_source_length=len(host.toPlainText()),
            committed_source_length=len(host._projection_document.source_text),
            caret_rect=host._current_caret_document_rect(),
            content_right=self._transient_content_right(),
            metrics=host._layout.metrics,
            freshness_is_stale_safe=(
                host._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_revision=host._source_revision,
        )

    def _transient_single_character_edit_caret_geometry(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        cursor_position: int,
        anchor_position: int,
        source_revision: int,
    ) -> PromptProjectionTransientCaretGeometry | None:
        """Return immediate caret geometry for one deferred single-character edit."""

        host = self._host
        return host._transient_edit_overlays.single_character_edit_caret_geometry(
            start=start,
            end=end,
            replacement_text=replacement_text,
            source_revision=source_revision,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            committed_source_revision=self._transient_committed_source_revision(),
            current_caret_document_rect=host._current_caret_document_rect(),
            metrics=host._layout.metrics,
            projection_document=host._projection_document,
            layout=host._layout,
        )

    def _transient_single_character_insertion_overlay(
        self,
        *,
        start: int,
        replacement_text: str,
        source_revision: int,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return text overlay for one deferred single-character insertion."""

        host = self._host
        return host._transient_edit_overlays.single_character_insertion_overlay(
            start=start,
            replacement_text=replacement_text,
            source_revision=source_revision,
            committed_source_revision=self._transient_committed_source_revision(),
            current_caret_document_rect=host._current_caret_document_rect(),
            freshness_is_stale_safe=(
                host._projection_freshness_controller.has_stale_projection_geometry()
            ),
            current_source_revision=host._source_revision,
        )

    def _transient_insertion_overlay_after_deletion(
        self,
        *,
        start: int,
        end: int,
        source_revision: int,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return remaining pending insertion overlay after a deferred delete."""

        host = self._host
        return host._transient_edit_overlays.insertion_overlay_after_deletion(
            start=start,
            end=end,
            source_revision=source_revision,
            freshness_is_stale_safe=(
                host._projection_freshness_controller.has_stale_projection_geometry()
            ),
            current_source_revision=host._source_revision,
        )

    def _transient_single_character_deletion_overlay(
        self,
        *,
        start: int,
        end: int,
        source_revision: int,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return erase geometry for one deferred single-character deletion."""

        host = self._host
        return host._transient_edit_overlays.single_character_deletion_overlay(
            start=start,
            end=end,
            source_revision=source_revision,
            committed_source_revision=self._transient_committed_source_revision(),
            previous_overlay=self._valid_transient_deletion_overlay(),
            layout=host._layout,
            viewport_width=float(host.viewport().width()),
            viewport_height=float(host.viewport().height()),
        )

    def _source_insertion_is_inside_projected_token(
        self,
        source_position: int,
    ) -> bool:
        """Return whether an insertion would edit a projected token interior."""

        return any(
            getattr(token, "source_start", -1)
            < source_position
            < getattr(token, "source_end", -1)
            for token in self._host._projection_document.tokens
        )

    def _apply_source_replacement_source_change(
        self,
        *,
        previous_text: str,
        source_change: PromptEditingSessionSourceChange[TProjectionPayload],
        undo_availability_change: PromptUndoAvailabilityChange | None,
        origin: PromptSourceEditOrigin,
    ) -> None:
        """Apply one editing-session source replacement to projection state."""

        host = self._host
        result = source_change
        self._emit_undo_availability_change(undo_availability_change)
        source_result = result.source_result
        start = source_result.requested_start
        end = source_result.requested_end
        replacement_text = source_result.requested_replacement_text
        updated_text = previous_text[:start] + replacement_text + previous_text[end:]
        if not result.source_changed:
            host.set_cursor_positions(
                cursor_position=result.cursor_state.cursor_position,
                anchor_position=result.cursor_state.anchor_position,
            )
            return
        can_defer_projection, deferral_reason = self._can_defer_source_rebuild_for_edit(
            start=start,
            end=end,
            replaced_text=previous_text[start:end],
            replacement_text=replacement_text,
            origin=origin,
            updated_text=updated_text,
            normalized_text=result.next_snapshot.source_text,
        )
        insertion_overlay_can_defer = (
            not replacement_text
            or not can_defer_projection
            or self._can_defer_transient_insertion_overlay(
                start=start,
                end=end,
                replacement_text=replacement_text,
            )
        )
        projection_decision = self._source_edit_projection_policy.decide(
            can_defer_projection=can_defer_projection,
            deferral_reason=deferral_reason,
            replacement_text=replacement_text,
            autocomplete_preview_active=host._session.autocomplete_preview is not None,
            insertion_overlay_can_defer=insertion_overlay_can_defer,
        )
        can_defer_projection = projection_decision.can_defer_projection
        deferral_reason = projection_decision.deferral_reason
        transient_caret_geometry = (
            self._transient_single_character_edit_caret_geometry(
                start=start,
                end=end,
                replacement_text=replacement_text,
                cursor_position=result.cursor_state.cursor_position,
                anchor_position=result.cursor_state.anchor_position,
                source_revision=result.next_snapshot.source_revision,
            )
            if can_defer_projection
            else None
        )
        transient_insertion_overlay = (
            self._transient_single_character_insertion_overlay(
                start=start,
                replacement_text=replacement_text,
                source_revision=result.next_snapshot.source_revision,
            )
            if can_defer_projection and replacement_text
            else None
        )
        transient_deletion_overlay = None
        optimistic_prompt_state = (
            self._semantic_remapper.optimistic_prompt_state_for_edit(
                current_document_view=host._document_view,
                current_render_plan=host._render_plan,
                previous_text=previous_text,
                next_text=result.next_snapshot.source_text,
                start=start,
                end=end,
                replacement_text=replacement_text,
            )
            if not can_defer_projection
            and self._semantic_remapper.should_use_optimistic_prompt_state_for_immediate_edit(
                deferral_reason=deferral_reason,
            )
            else None
        )
        if optimistic_prompt_state is not None:
            host._session.expanded_source_range = (
                self._semantic_remapper.remap_expanded_source_range_for_edit(
                    host._session.expanded_source_range,
                    start=start,
                    end=end,
                    delta=len(replacement_text) - (end - start),
                )
            )
        refresh_caret_after_prompt_state = False
        self._apply_editing_session_source_change(
            result,
            emit_text_changed=True,
            rebuild_immediately=not can_defer_projection,
            deferrable_projection=can_defer_projection,
            transient_caret_geometry=transient_caret_geometry,
            transient_insertion_overlay=transient_insertion_overlay,
            transient_deletion_overlay=transient_deletion_overlay,
            optimistic_prompt_state=optimistic_prompt_state,
            source_edit_start=start,
            source_edit_end=end,
            source_edit_replacement_text=replacement_text,
            previous_source_text=previous_text,
            refresh_caret_after_prompt_state=refresh_caret_after_prompt_state,
            projection_deferral_reason=deferral_reason,
            origin=origin,
        )

    def _restore_undo_state(
        self,
        restore_result: PromptEditingSessionRestoreResult[TProjectionPayload],
    ) -> None:
        """Restore one complete source, selection, and token-focus snapshot."""

        host = self._host
        state = restore_result.snapshot
        payload = cast(PromptProjectionRestorePayload | None, state.restoration_payload)
        if (
            payload is not None
            and payload.document_view.source_text == state.source_text
        ):
            host._document_view = payload.document_view
            host._render_plan = payload.render_plan
        else:
            host._document_view = PromptDocumentView(
                source_text=state.source_text,
                segments=(),
                emphasis_spans=(),
                wildcard_spans=(),
                lora_spans=(),
                syntax_spans=(),
                has_trailing_comma=False,
            )
            host._render_plan = PromptSyntaxRenderPlan(
                syntax_spans=(),
                renderer_views=(),
            )
        if payload is not None:
            host._cursor_state = payload.cursor_state
            host._anchor_state = payload.anchor_state
            host._sync_editing_session_to_caret_states()
            host._session.expanded_source_range = payload.expanded_source_range
        else:
            host._cursor_state = PromptProjectionCaretState(
                source_position=state.cursor_state.cursor_position
            )
            host._anchor_state = PromptProjectionCaretState(
                source_position=state.cursor_state.anchor_position
            )
            host._sync_editing_session_to_caret_states()
            host._session.expanded_source_range = None
        host._preferred_x = None
        host._caret_rect_override = None
        host._source_document_adapter.sync_default_font(host.font())
        host._source_document_adapter.replace_text(state.source_text)
        host._mark_source_text_changed(
            deferrable_projection=False,
            source_revision=restore_result.source_snapshot.source_revision,
        )
        host._rebuild_projection()
        host._ensure_caret_visible()
        host._restart_caret_blink_cycle()
        host.textChanged.emit()
        host.cursorPositionChanged.emit()


__all__ = [
    "PromptProjectionNoArgSignal",
    "PromptProjectionCaretSync",
    "PromptProjectionFreshnessOutcome",
    "PromptProjectionFreshnessState",
    "PromptProjectionOptimisticPromptState",
    "PromptProjectionRestorePayload",
    "PromptProjectionSignalOutcome",
    "PromptProjectionSourceChangeApplier",
    "PromptProjectionSourceChangeHost",
    "PromptProjectionSourceDocumentOutcome",
    "PromptProjectionSourceDocumentRangeEdit",
    "PromptProjectionSourceStateApplicationRequest",
    "PromptProjectionSourceStateApplyPath",
    "PromptProjectionSourceStateOutcome",
    "PromptProjectionSourceStateOwner",
    "PromptProjectionViewportInvalidation",
]
