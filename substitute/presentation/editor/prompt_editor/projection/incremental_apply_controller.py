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

"""Coordinate incremental projection apply paths outside the projection surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QFont

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)

from .applicator import PromptProjectionApplicator
from .canonical_edit_reflow import PromptProjectionCanonicalEditReflow
from .freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .incremental_editor import (
    PromptProjectionIncrementalEdit,
    PromptProjectionIncrementalEditor,
    PromptProjectionPlainTextApplyStatus,
    PromptProjectionPlainTextApplyResult,
    projection_affecting_render_plan_ranges,
    render_plan_ranges_match_after_source_edit,
    single_source_text_edit,
)
from .layout_engine import (
    PromptProjectionIncrementalLayoutResult,
    PromptProjectionLayout,
)
from .layout_checkpoint import PromptProjectionLayoutCheckpoint
from .diagnostics_painter import PromptDiagnosticPainter
from .model import (
    PromptProjectionCaretState,
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from .observability import (
    log_projection_timing,
    projection_observability_started_at,
)
from .session import PromptProjectionSession
from .semantic_transition import semantic_projection_change_range
from .transient_edit_overlays import (
    PromptProjectionTransientCaretGeometry,
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)


class PromptProjectionApplyPath(Enum):
    """Name the projection apply path selected for one source-state update."""

    PAINT_ONLY = "paint_only"
    SCHEDULED = "scheduled"
    FAST_TRAILING = "fast_trailing"
    INCREMENTAL = "incremental"
    REFLOW = "reflow"
    CHECKPOINT_RESTORE = "checkpoint_restore"
    DEFERRED_WRAP = "deferred_wrap"
    FULL_REBUILD = "full_rebuild"
    DROPPED_STALE = "dropped_stale"
    FAILED = "failed"


_WRAP_REFLOW_DEFERRABLE_REASONS = frozenset(
    (
        "plain_single_character",
        "plain_single_character_delete",
        "plain_single_character_delete_requires_layout",
        "syntax_sensitive_autocomplete_prefix",
    )
)


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceChangeApplyRequest:
    """Carry one committed source edit considered for projection catch-up."""

    text: str
    previous_source_text: str | None
    source_edit_start: int | None
    source_edit_end: int | None
    source_edit_replacement_text: str | None
    previous_projection_freshness: ProjectionFreshness
    previous_document_view: PromptDocumentView
    previous_render_plan: PromptSyntaxRenderPlan
    previous_deletion_overlay: PromptProjectionTransientDeletionOverlay | None
    next_cursor_state: PromptProjectionCaretState
    next_anchor_state: PromptProjectionCaretState
    can_preserve_diagnostic_fragment_cache: bool
    projection_deferral_reason: str
    restore_checkpoint: PromptProjectionLayoutCheckpoint | None = None


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceChangeApplyOutcome:
    """Describe how projection state handled one committed source edit."""

    apply_path: PromptProjectionApplyPath
    fast_projection_applied: bool = False
    wrap_reflow_deferred: bool = False


class PromptProjectionRectSignal(Protocol):
    """Expose the QRect signal used for targeted backing-fill invalidation."""

    def emit(self, rect: QRect) -> None:
        """Emit one invalidated viewport rectangle."""


class PromptProjectionApplyViewport(Protocol):
    """Expose the viewport update operations needed by projection apply sinks."""

    def rect(self) -> QRect:
        """Return the current viewport rectangle."""

    def width(self) -> int:
        """Return the viewport width."""

    def height(self) -> int:
        """Return the viewport height."""

    def update(self, rect: QRect | None = None) -> None:
        """Schedule a full or partial viewport repaint."""


class PromptProjectionSourceLineChromeContext(Protocol):
    """Expose source-line geometry context needed for transient fallback overlays."""

    content_left_inset: float


class PromptProjectionIncrementalApplyHost(Protocol):
    """Expose surface-owned state and sinks for incremental projection apply."""

    _projection_applicator: PromptProjectionApplicator
    _projection_freshness_controller: PromptProjectionFreshnessController
    _document_view: PromptDocumentView
    _render_plan: PromptSyntaxRenderPlan
    _projection_document: PromptProjectionDocument
    _layout: PromptProjectionLayout
    _display_mode: PromptProjectionDisplayMode
    _session: PromptProjectionSession
    _scene_error_keys: frozenset[str]
    _diagnostic_painter: PromptDiagnosticPainter
    _source_revision: int
    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _caret_rect_override: QRectF | None
    _transient_edit_overlays: PromptProjectionTransientEditOverlayController
    _source_line_chrome: PromptProjectionSourceLineChromeContext
    _last_rendered_active_span_range: tuple[int, int] | None
    backingFillInvalidated: PromptProjectionRectSignal

    def viewport(self) -> PromptProjectionApplyViewport:
        """Return the projection viewport."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return current blockers for deferred projection work."""

    def _reorder_preview_is_active(self) -> bool:
        """Return whether display-only reorder preview projection is active."""

    def _visible_scroll_bar(self) -> object:
        """Ensure scrollbar state is materialized before layout changes."""

    def _active_span_range(self) -> tuple[int, int] | None:
        """Return the active projected span range."""

    def _decoration_accent_ranges(self) -> tuple[tuple[int, int], ...]:
        """Return source ranges that should receive decoration accents."""

    def _sync_editing_session_to_caret_states(self) -> object:
        """Mirror projection caret state into the editing-session owner."""

    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Synchronize surface layout metrics after projection changes."""

    def _rebuild_active_projection(self, *, commit_projection: bool = False) -> None:
        """Rebuild active projection layout after committed projection changes."""

    def _clear_transient_caret_geometry(self) -> None:
        """Clear transient caret geometry after committed projection catch-up."""

    def _clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Clear cached diagnostic fragments."""

    def _preserve_diagnostic_fragment_cache_for_incremental_edit(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        next_layout_revision: int,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Preserve unaffected diagnostic fragments for a local edit."""

    def _update_incremental_plain_text_projection_paint(
        self,
        layout_result: PromptProjectionIncrementalLayoutResult,
    ) -> None:
        """Repaint lines dirtied by an accepted incremental text edit."""

    def _typed_character_requires_immediate_projection(
        self,
        character: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether one typed character must rebuild projection now."""

    def _can_defer_syntax_sensitive_autocomplete_prefix(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalized_text: str,
    ) -> bool:
        """Return whether a syntax-sensitive autocomplete prefix may defer."""

    def _source_range_intersects_projected_token(
        self,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether a source range crosses projected token geometry."""

    def font(self) -> QFont:
        """Return the current surface font."""

    def _current_caret_document_rect(self) -> QRectF:
        """Return the current document-local caret rectangle."""

    def _update_transient_insertion_overlay_paint(
        self,
        previous_overlay: object | None,
        next_overlay: object | None,
    ) -> None:
        """Repaint transient insertion overlay changes."""

    def _update_transient_deletion_overlay_paint(
        self,
        previous_overlay: object | None,
        next_overlay: object | None,
    ) -> None:
        """Repaint transient deletion overlay changes."""

    def _rebuild_projection(self) -> None:
        """Run the surface-owned full projection rebuild sink."""


class PromptProjectionIncrementalApplyController:
    """Select and apply incremental projection catch-up paths."""

    def __init__(self, host: PromptProjectionIncrementalApplyHost) -> None:
        """Create the controller around a surface-owned effect sink."""

        self._host = host
        self._incremental_editor = PromptProjectionIncrementalEditor()
        self._canonical_edit_reflow = PromptProjectionCanonicalEditReflow(
            host._projection_applicator
        )

    def try_apply_source_changed_prompt_state_without_geometry_rebuild(
        self,
        *,
        previous_source_text: str | None,
    ) -> bool:
        """Reject source-changed paint reuse so canonical layout owns geometry."""

        _ = previous_source_text
        return False

    def try_restore_history_layout_checkpoint(
        self,
        checkpoint: PromptProjectionLayoutCheckpoint | None,
    ) -> bool:
        """Restore exact history geometry and publish its canonical projection."""

        if checkpoint is None:
            return False
        host = self._host
        blockers = host._projection_freshness_blockers()
        if (
            blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED
            or blockers.reorder_preview_active
            or blockers.autocomplete_preview_active
            or blockers.exact_weight_edit_active
            or blockers.expanded_source_range_active
            or checkpoint.projection_document.source_text
            != host._document_view.source_text
            or not host._layout.try_restore_history_checkpoint(checkpoint)
        ):
            return False
        host._projection_document = checkpoint.projection_document
        host._last_rendered_active_span_range = host._active_span_range()
        host._diagnostic_painter.advance_layout_revision(
            reason="projection_history_checkpoint_restore"
        )
        host._clear_diagnostic_fragment_cache(
            reason="projection_history_checkpoint_restore"
        )
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host.viewport().update()
        return True

    def can_apply_fast_trailing_insert_for_prompt_state(
        self,
        render_plan: PromptSyntaxRenderPlan,
        *,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Return whether semantic apply may reuse trailing insert geometry."""

        if (
            render_plan.document_semantics_identity
            != previous_render_plan.document_semantics_identity
        ):
            return False
        render_ranges = projection_affecting_render_plan_ranges(render_plan)
        previous_render_ranges = projection_affecting_render_plan_ranges(
            previous_render_plan
        )
        if (
            render_plan.syntax_spans == previous_render_plan.syntax_spans
            and render_ranges == previous_render_ranges
        ):
            return True
        return len(render_ranges) <= len(self._host._projection_document.tokens)

    def try_apply_scheduled_incremental_prompt_state_projection(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Apply scheduled safe-typing state without rebuilding when still local."""

        previous_text = self._host._projection_document.source_text
        next_text = document_view.source_text
        edit = single_source_text_edit(previous_text, next_text)
        if edit is None:
            if previous_text != next_text:
                return False
            return self.try_apply_local_semantic_projection_transition(
                document_view=document_view,
                render_plan=render_plan,
                previous_render_plan=previous_render_plan,
            )
        if not render_plan_ranges_match_after_source_edit(
            previous_render_plan,
            render_plan,
            edit=edit,
        ):
            return False
        result = self.try_apply_incremental_plain_text_projection(
            previous_text=previous_text,
            next_text=next_text,
            start=edit.start,
            end=edit.end,
            replacement_text=edit.replacement_text,
        )
        return result.status in {
            PromptProjectionPlainTextApplyStatus.APPLIED,
            PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW,
        }

    def try_apply_local_semantic_projection_transition(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Apply one bounded token-topology transition through local reflow."""

        host = self._host
        blockers = host._projection_freshness_blockers()
        if (
            blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED
            or blockers.reorder_preview_active
            or blockers.autocomplete_preview_active
            or blockers.exact_weight_edit_active
            or blockers.expanded_source_range_active
            or host._projection_document.source_text != document_view.source_text
        ):
            return False
        changed_range = semantic_projection_change_range(
            previous_render_plan,
            render_plan,
        )
        if changed_range is None:
            return False
        start, end = changed_range
        if not 0 <= start < end <= len(document_view.source_text):
            return False

        projection_document = host._projection_applicator.build_projection(
            document_view,
            render_plan,
            display_mode=host._display_mode,
            session=host._session,
            active_span_range=None,
            decoration_accent_ranges=host._decoration_accent_ranges(),
            scene_error_keys=host._scene_error_keys,
        )
        previous_cursor_state = host._cursor_state
        previous_anchor_state = host._anchor_state
        layout_result = host._layout.set_projection_after_source_edit(
            projection_document,
            prompt_document_view=document_view,
            edit_start=start,
            edit_end=end,
            replacement_text=document_view.source_text[start:end],
        )
        host._projection_document = projection_document
        host._last_rendered_active_span_range = host._active_span_range()
        host._diagnostic_painter.advance_layout_revision(
            reason="projection_local_semantic_transition"
        )
        host._clear_diagnostic_fragment_cache(
            reason="projection_local_semantic_transition"
        )
        host._cursor_state = projection_document.caret_map.resolve_state(
            previous_cursor_state
        )
        host._anchor_state = projection_document.caret_map.resolve_state(
            previous_anchor_state
        )
        host._sync_editing_session_to_caret_states()
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host._update_incremental_plain_text_projection_paint(layout_result)
        return True

    def try_apply_fast_trailing_plain_insert_projection(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Apply a trailing plain-text insertion without full relayout."""

        host = self._host
        previous_text = host._projection_document.source_text
        if host._projection_applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            document_view.source_text,
            start=len(previous_text),
            end=len(previous_text),
        ):
            return False
        next_document = self._incremental_editor.fast_trailing_plain_insert_document(
            previous_document=host._projection_document,
            next_text=document_view.source_text,
            render_plan=render_plan,
        )
        if next_document is None:
            return False
        if not host._layout.try_apply_trailing_plain_insert(
            next_document,
            prompt_document_view=document_view,
        ):
            return False

        previous_cursor_state = host._cursor_state
        previous_anchor_state = host._anchor_state
        host._projection_document = next_document
        host._last_rendered_active_span_range = host._active_span_range()
        host._diagnostic_painter.advance_layout_revision(
            reason="projection_fast_insert"
        )
        host._clear_diagnostic_fragment_cache(reason="projection_fast_insert")
        host._cursor_state = next_document.caret_map.resolve_state(
            previous_cursor_state
        )
        host._anchor_state = next_document.caret_map.resolve_state(
            previous_anchor_state
        )
        host._sync_editing_session_to_caret_states()
        host._caret_rect_override = None
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host.viewport().update()
        return True

    def try_apply_fast_trailing_newline_insert_projection(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_text: str,
        start: int,
        end: int,
    ) -> bool:
        """Apply a trailing hard-line insertion without full relayout."""

        host = self._host
        if host._projection_applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            document_view.source_text,
            start=start,
            end=end,
        ):
            return False
        next_document = self._incremental_editor.fast_trailing_newline_insert_document(
            previous_document=host._projection_document,
            previous_text=previous_text,
            next_text=document_view.source_text,
            start=start,
            end=end,
            render_plan=render_plan,
        )
        if next_document is None:
            return False
        if not host._layout.try_apply_trailing_newline_insert(
            next_document,
            prompt_document_view=document_view,
        ):
            return False

        previous_cursor_state = host._cursor_state
        previous_anchor_state = host._anchor_state
        host._projection_document = next_document
        host._last_rendered_active_span_range = host._active_span_range()
        host._diagnostic_painter.advance_layout_revision(
            reason="projection_fast_newline_insert"
        )
        host._clear_diagnostic_fragment_cache(reason="projection_fast_newline_insert")
        host._cursor_state = next_document.caret_map.resolve_state(
            previous_cursor_state
        )
        host._anchor_state = next_document.caret_map.resolve_state(
            previous_anchor_state
        )
        host._sync_editing_session_to_caret_states()
        host._caret_rect_override = None
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host.viewport().update()
        return True

    def try_apply_fast_trailing_plain_delete_projection(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> bool:
        """Apply a trailing plain-text deletion without full relayout."""

        host = self._host
        if host._projection_applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            next_text,
            start=start,
            end=end,
        ):
            return False
        next_document = self._incremental_editor.fast_trailing_plain_delete_document(
            previous_document=host._projection_document,
            previous_text=previous_text,
            next_text=next_text,
            start=start,
            end=end,
        )
        if next_document is None:
            return False
        if not host._layout.try_apply_trailing_plain_delete(
            next_document,
            prompt_document_view=host._document_view,
        ):
            return False

        host._projection_document = next_document
        host._last_rendered_active_span_range = host._active_span_range()
        next_diagnostic_layout_revision = (
            host._diagnostic_painter.advance_layout_revision(
                reason="projection_fast_delete"
            )
        )
        host._preserve_diagnostic_fragment_cache_for_incremental_edit(
            start=start,
            end=end,
            replacement_text="",
            next_layout_revision=next_diagnostic_layout_revision,
        )
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host.viewport().update()
        return True

    def try_apply_fast_trailing_newline_delete_projection(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> bool:
        """Apply a trailing hard-line deletion without full relayout."""

        host = self._host
        if host._projection_applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            next_text,
            start=start,
            end=end,
        ):
            return False
        next_document = self._incremental_editor.fast_trailing_newline_delete_document(
            previous_document=host._projection_document,
            previous_text=previous_text,
            next_text=next_text,
            start=start,
            end=end,
        )
        if next_document is None:
            return False
        if not host._layout.try_apply_trailing_newline_delete(
            next_document,
            prompt_document_view=host._document_view,
        ):
            return False

        host._projection_document = next_document
        host._last_rendered_active_span_range = host._active_span_range()
        host._diagnostic_painter.advance_layout_revision(
            reason="projection_fast_newline_delete"
        )
        host._clear_diagnostic_fragment_cache(reason="projection_fast_newline_delete")
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host.viewport().update()
        return True

    def try_apply_incremental_plain_text_projection(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
        replacement_text: str,
    ) -> PromptProjectionPlainTextApplyResult:
        """Apply a supported middle plain edit without full relayout."""

        host = self._host
        if host._projection_applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            next_text,
            start=start,
            end=end,
        ):
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED
            )
        edit = PromptProjectionIncrementalEdit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            previous_source_text=previous_text,
            next_source_text=next_text,
        )
        host._layout.content_size().height()
        apply_result = self._incremental_editor.try_apply_plain_text_layout_edit(
            edit,
            layout=host._layout,
            previous_document=host._projection_document,
            document_view=host._document_view,
            render_plan=host._render_plan,
            display_mode=host._display_mode,
            session=host._session,
            active_span_range=None,
            decoration_accent_ranges=host._decoration_accent_ranges(),
            scene_error_keys=host._scene_error_keys,
        )
        if (
            apply_result.status is PromptProjectionPlainTextApplyStatus.REJECTED
            and apply_result.projection_document is not None
        ):
            self._apply_prebuilt_source_edit_reflow(
                apply_result.projection_document,
                start=start,
                end=end,
                replacement_text=replacement_text,
            )
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW,
                projection_document=apply_result.projection_document,
            )
        if apply_result.status is not PromptProjectionPlainTextApplyStatus.APPLIED:
            return apply_result
        if (
            apply_result.projection_document is None
            or apply_result.layout_result is None
        ):
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED
            )

        host._projection_document = apply_result.projection_document
        host._last_rendered_active_span_range = host._active_span_range()
        next_diagnostic_layout_revision = (
            host._diagnostic_painter.advance_layout_revision(
                reason="projection_incremental_plain_text"
            )
        )
        host._preserve_diagnostic_fragment_cache_for_incremental_edit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            next_layout_revision=next_diagnostic_layout_revision,
            fragment_y_delta=(
                apply_result.layout_result.content_height_delta
                if apply_result.layout_result.content_height_changed
                else 0.0
            ),
        )
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host._update_incremental_plain_text_projection_paint(apply_result.layout_result)
        return apply_result

    def _apply_prebuilt_source_edit_reflow(
        self,
        projection_document: PromptProjectionDocument,
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> None:
        """Relayout an already-validated canonical projection document."""

        host = self._host
        layout_result = host._layout.set_projection_after_source_edit(
            projection_document,
            prompt_document_view=host._document_view,
            edit_start=start,
            edit_end=end,
            replacement_text=replacement_text,
        )
        host._projection_document = projection_document
        host._last_rendered_active_span_range = host._active_span_range()
        host._diagnostic_painter.advance_layout_revision(
            reason="projection_prebuilt_reflow"
        )
        host._clear_diagnostic_fragment_cache(reason="projection_prebuilt_reflow")
        host._rebuild_active_projection(commit_projection=True)
        host._clear_transient_caret_geometry()
        host._update_incremental_plain_text_projection_paint(layout_result)

    def defer_wrap_reflow_projection_update(
        self,
        *,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Schedule one wrap-only plain edit reflow off the keypress lane."""

        host = self._host
        if not host._projection_freshness_controller.can_defer_wrap_reflow_projection_update(
            host._projection_freshness_blockers()
        ):
            return False
        host._projection_freshness_controller.mark_source_text_changed(
            deferrable_projection=True,
            source_revision=host._source_revision,
        )
        host._projection_freshness_controller.schedule_safe_typing_update(
            document_view=host._document_view,
            render_plan=host._render_plan,
            source_revision=host._source_revision,
            previous_document_view=previous_document_view,
            previous_render_plan=previous_render_plan,
        )
        return True

    def try_defer_immediate_projection_fallback_update(
        self,
        *,
        previous_text: str | None,
        next_text: str,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
        previous_deletion_overlay: PromptProjectionTransientDeletionOverlay | None,
        projection_deferral_reason: str,
    ) -> bool:
        """Schedule a safe typed-edit fallback instead of rebuilding now."""

        if not self._can_defer_immediate_projection_fallback_edit(
            previous_text=previous_text,
            next_text=next_text,
            start=start,
            end=end,
            replacement_text=replacement_text,
            projection_deferral_reason=projection_deferral_reason,
        ):
            return False
        if not self.defer_wrap_reflow_projection_update(
            previous_document_view=previous_document_view,
            previous_render_plan=previous_render_plan,
        ):
            return False

        host = self._host
        previous_insertion_overlay = host._transient_edit_overlays.insertion_overlay
        transient_caret_geometry = self._transient_fallback_caret_geometry_for_edit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            cursor_state=cursor_state,
            anchor_state=anchor_state,
        )
        transient_insertion_overlay = (
            self._transient_fallback_insertion_overlay_for_edit(
                start=start,
                end=end,
                replacement_text=replacement_text,
            )
        )
        transient_deletion_overlay = self._transient_fallback_deletion_overlay_for_edit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            previous_overlay=previous_deletion_overlay,
        )
        host._transient_edit_overlays.set_overlays(
            caret_geometry=transient_caret_geometry,
            insertion_overlay=transient_insertion_overlay,
            deletion_overlay=transient_deletion_overlay,
        )
        host._update_transient_insertion_overlay_paint(
            previous_insertion_overlay,
            transient_insertion_overlay,
        )
        host._update_transient_deletion_overlay_paint(
            previous_deletion_overlay,
            transient_deletion_overlay,
        )
        return True

    def apply_source_change_projection(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Select the source-change projection apply path and run its sink."""

        host = self._host
        fast_projection_applied = False
        wrap_reflow_deferred = False
        incremental_plain_edit_attempted = False
        plain_apply_result: PromptProjectionPlainTextApplyResult | None = None

        apply_started_at = projection_observability_started_at()
        checkpoint_restored = self.try_restore_history_layout_checkpoint(
            request.restore_checkpoint
        )
        fast_projection_applied = checkpoint_restored or (
            self.try_apply_source_changed_prompt_state_without_geometry_rebuild(
                previous_source_text=request.previous_source_text
            )
        )
        apply_path = (
            PromptProjectionApplyPath.CHECKPOINT_RESTORE
            if checkpoint_restored
            else (
                PromptProjectionApplyPath.PAINT_ONLY
                if fast_projection_applied
                else PromptProjectionApplyPath.FULL_REBUILD
            )
        )
        if (
            not fast_projection_applied
            and request.source_edit_start is not None
            and request.source_edit_end is not None
            and request.previous_source_text is not None
        ):
            if self._can_extend_deferred_plain_source_edit(
                previous_projection_freshness=(request.previous_projection_freshness),
                start=request.source_edit_start,
                end=request.source_edit_end,
                replacement_text=request.source_edit_replacement_text or "",
                normalized_text=request.text,
                projection_deferral_reason=request.projection_deferral_reason,
            ):
                wrap_reflow_deferred = self.defer_wrap_reflow_projection_update(
                    previous_document_view=request.previous_document_view,
                    previous_render_plan=request.previous_render_plan,
                )
                if wrap_reflow_deferred:
                    apply_path = PromptProjectionApplyPath.DEFERRED_WRAP
            elif request.source_edit_replacement_text == "":
                fast_projection_applied = (
                    self.try_apply_fast_trailing_plain_delete_projection(
                        previous_text=request.previous_source_text,
                        next_text=request.text,
                        start=request.source_edit_start,
                        end=request.source_edit_end,
                    )
                    or self.try_apply_fast_trailing_newline_delete_projection(
                        previous_text=request.previous_source_text,
                        next_text=request.text,
                        start=request.source_edit_start,
                        end=request.source_edit_end,
                    )
                )
                if fast_projection_applied:
                    apply_path = PromptProjectionApplyPath.FAST_TRAILING
            elif request.source_edit_replacement_text == "\n":
                fast_projection_applied = (
                    self.try_apply_fast_trailing_newline_insert_projection(
                        document_view=host._document_view,
                        render_plan=host._render_plan,
                        previous_text=request.previous_source_text,
                        start=request.source_edit_start,
                        end=request.source_edit_end,
                    )
                )
                if fast_projection_applied:
                    apply_path = PromptProjectionApplyPath.FAST_TRAILING
            else:
                incremental_plain_edit_attempted = True
                can_try_plain_insert_fast_path = not (
                    request.source_edit_replacement_text
                    and host._typed_character_requires_immediate_projection(
                        request.source_edit_replacement_text,
                        start=request.source_edit_start,
                        end=request.source_edit_end,
                    )
                    and not host._can_defer_syntax_sensitive_autocomplete_prefix(
                        start=request.source_edit_start,
                        end=request.source_edit_end,
                        replacement_text=(request.source_edit_replacement_text),
                        normalized_text=request.text,
                    )
                )
                fast_projection_applied = (
                    can_try_plain_insert_fast_path
                    and self.try_apply_fast_trailing_plain_insert_projection(
                        document_view=host._document_view,
                        render_plan=host._render_plan,
                    )
                )
                if fast_projection_applied:
                    apply_path = PromptProjectionApplyPath.FAST_TRAILING
                if not fast_projection_applied:
                    plain_apply_result = (
                        self.try_apply_incremental_plain_text_projection(
                            previous_text=request.previous_source_text,
                            next_text=request.text,
                            start=request.source_edit_start,
                            end=request.source_edit_end,
                            replacement_text=(
                                request.source_edit_replacement_text or ""
                            ),
                        )
                    )
                    fast_projection_applied = plain_apply_result.status in {
                        PromptProjectionPlainTextApplyStatus.APPLIED,
                        PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW,
                    }
                    if fast_projection_applied:
                        apply_path = (
                            PromptProjectionApplyPath.REFLOW
                            if plain_apply_result.status
                            is PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW
                            else PromptProjectionApplyPath.INCREMENTAL
                        )
                    if (
                        plain_apply_result.status
                        is PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW
                        and _can_defer_wrap_reflow_for_reason(
                            request.projection_deferral_reason
                        )
                    ):
                        wrap_reflow_deferred = self.defer_wrap_reflow_projection_update(
                            previous_document_view=(request.previous_document_view),
                            previous_render_plan=request.previous_render_plan,
                        )
                        if wrap_reflow_deferred:
                            apply_path = PromptProjectionApplyPath.DEFERRED_WRAP
            if (
                not fast_projection_applied
                and not incremental_plain_edit_attempted
                and not wrap_reflow_deferred
            ):
                plain_apply_result = self.try_apply_incremental_plain_text_projection(
                    previous_text=request.previous_source_text,
                    next_text=request.text,
                    start=request.source_edit_start,
                    end=request.source_edit_end,
                    replacement_text=request.source_edit_replacement_text or "",
                )
                fast_projection_applied = plain_apply_result.status in {
                    PromptProjectionPlainTextApplyStatus.APPLIED,
                    PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW,
                }
                if fast_projection_applied:
                    apply_path = (
                        PromptProjectionApplyPath.REFLOW
                        if plain_apply_result.status
                        is PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW
                        else PromptProjectionApplyPath.INCREMENTAL
                    )
                if (
                    plain_apply_result.status
                    is PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW
                    and _can_defer_wrap_reflow_for_reason(
                        request.projection_deferral_reason
                    )
                ):
                    wrap_reflow_deferred = self.defer_wrap_reflow_projection_update(
                        previous_document_view=request.previous_document_view,
                        previous_render_plan=request.previous_render_plan,
                    )
                    if wrap_reflow_deferred:
                        apply_path = PromptProjectionApplyPath.DEFERRED_WRAP
        if not fast_projection_applied and not wrap_reflow_deferred:
            wrap_reflow_deferred = self.try_defer_immediate_projection_fallback_update(
                previous_text=request.previous_source_text,
                next_text=request.text,
                start=request.source_edit_start,
                end=request.source_edit_end,
                replacement_text=request.source_edit_replacement_text,
                cursor_state=request.next_cursor_state,
                anchor_state=request.next_anchor_state,
                previous_document_view=request.previous_document_view,
                previous_render_plan=request.previous_render_plan,
                previous_deletion_overlay=request.previous_deletion_overlay,
                projection_deferral_reason=request.projection_deferral_reason,
            )
            if wrap_reflow_deferred:
                apply_path = PromptProjectionApplyPath.DEFERRED_WRAP
        if not fast_projection_applied and not wrap_reflow_deferred:
            if (
                plain_apply_result is not None
                and plain_apply_result.projection_document is not None
            ):
                assert request.source_edit_start is not None
                assert request.source_edit_end is not None
                self._apply_prebuilt_source_edit_reflow(
                    plain_apply_result.projection_document,
                    start=request.source_edit_start,
                    end=request.source_edit_end,
                    replacement_text=request.source_edit_replacement_text or "",
                )
                fast_projection_applied = True
                apply_path = PromptProjectionApplyPath.REFLOW
            elif (
                request.source_edit_start is not None
                and request.source_edit_end is not None
                and request.previous_source_text is not None
                and (
                    canonical_document := (
                        self._canonical_edit_reflow.try_build_document(
                            previous_document=host._projection_document,
                            previous_source_text=request.previous_source_text,
                            document_view=host._document_view,
                            render_plan=host._render_plan,
                            start=request.source_edit_start,
                            end=request.source_edit_end,
                            replacement_text=(
                                request.source_edit_replacement_text or ""
                            ),
                            blockers=host._projection_freshness_blockers(),
                            session=host._session,
                            decoration_accent_ranges=(host._decoration_accent_ranges()),
                            scene_error_keys=host._scene_error_keys,
                        )
                    )
                )
                is not None
            ):
                self._apply_prebuilt_source_edit_reflow(
                    canonical_document,
                    start=request.source_edit_start,
                    end=request.source_edit_end,
                    replacement_text=request.source_edit_replacement_text or "",
                )
                fast_projection_applied = True
                apply_path = PromptProjectionApplyPath.REFLOW
            else:
                host._rebuild_projection()
                apply_path = PromptProjectionApplyPath.FULL_REBUILD
        if (
            request.can_preserve_diagnostic_fragment_cache
            and wrap_reflow_deferred
            and not fast_projection_applied
        ):
            host._clear_diagnostic_fragment_cache(
                reason="source_changed_deferred_projection"
            )
        log_projection_timing(
            "incremental_apply.source_change",
            started_at=apply_started_at,
            text_length=len(request.text),
            apply_path=apply_path.value,
            fast_projection_applied=fast_projection_applied,
            wrap_reflow_deferred=wrap_reflow_deferred,
            incremental_plain_edit_attempted=incremental_plain_edit_attempted,
        )

        return PromptProjectionSourceChangeApplyOutcome(
            apply_path=apply_path,
            fast_projection_applied=fast_projection_applied,
            wrap_reflow_deferred=wrap_reflow_deferred,
        )

    def _can_extend_deferred_plain_source_edit(
        self,
        *,
        previous_projection_freshness: ProjectionFreshness,
        start: int,
        end: int,
        replacement_text: str,
        normalized_text: str,
        projection_deferral_reason: str,
    ) -> bool:
        """Return whether deferred plain-source edit state can be extended."""

        if not _can_defer_wrap_reflow_for_reason(projection_deferral_reason):
            return False
        host = self._host
        typed_character_requires_projection = bool(
            replacement_text
            and host._typed_character_requires_immediate_projection(
                replacement_text,
                start=start,
                end=end,
            )
        )
        syntax_sensitive_prefix = bool(
            replacement_text
            and host._can_defer_syntax_sensitive_autocomplete_prefix(
                start=start,
                end=end,
                replacement_text=replacement_text,
                normalized_text=normalized_text,
            )
        )
        return (
            host._projection_freshness_controller.can_extend_deferred_plain_source_edit(
                previous_projection_freshness=previous_projection_freshness,
                start=start,
                end=end,
                replacement_text=replacement_text,
                typed_character_requires_immediate_projection=(
                    typed_character_requires_projection
                ),
                syntax_sensitive_autocomplete_prefix=syntax_sensitive_prefix,
            )
        )

    def _transient_fallback_committed_source_revision(self) -> int:
        """Return committed source revision for fallback overlay estimates."""

        host = self._host
        return host._projection_freshness_controller.transient_fallback_committed_source_revision(
            current_source_revision=host._source_revision
        )

    def _transient_content_right(self) -> float:
        """Return the document-local right edge used by transient overlay math."""

        content_width = self._host._layout.content_size().width()
        if content_width > 1.0:
            return content_width
        return float(self._host.viewport().width())

    def _transient_fallback_caret_geometry_for_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> PromptProjectionTransientCaretGeometry | None:
        """Return provisional caret geometry while fallback projection is pending."""

        host = self._host
        return host._transient_edit_overlays.fallback_caret_geometry_for_edit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            cursor_state=cursor_state,
            anchor_state=anchor_state,
            source_revision=host._source_revision,
            committed_source_revision=self._transient_fallback_committed_source_revision(),
            current_caret_document_rect=host._current_caret_document_rect(),
            metrics=host._layout.metrics,
            content_right=self._transient_content_right(),
            document_margin=host._layout.document_margin,
            source_line_content_left_inset=host._source_line_chrome.content_left_inset,
            projection_document=host._projection_document,
            layout=host._layout,
        )

    def _transient_fallback_insertion_overlay_for_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return provisional inserted text while fallback projection is pending."""

        host = self._host
        return host._transient_edit_overlays.fallback_insertion_overlay_for_edit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            source_revision=host._source_revision,
            committed_source_revision=self._transient_fallback_committed_source_revision(),
            current_caret_document_rect=host._current_caret_document_rect(),
            metrics=host._layout.metrics,
            content_right=self._transient_content_right(),
            document_margin=host._layout.document_margin,
            source_line_content_left_inset=host._source_line_chrome.content_left_inset,
        )

    def _transient_fallback_deletion_overlay_for_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None = None,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return provisional erase geometry while fallback projection is pending."""

        host = self._host
        return host._transient_edit_overlays.fallback_deletion_overlay_for_edit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            source_revision=host._source_revision,
            committed_source_revision=self._transient_fallback_committed_source_revision(),
            previous_overlay=previous_overlay,
            layout=host._layout,
            viewport_width=float(host.viewport().width()),
            viewport_height=float(host.viewport().height()),
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
            live_source_length=len(host._document_view.source_text),
            committed_source_length=len(host._projection_document.source_text),
            caret_rect=host._current_caret_document_rect(),
            content_right=self._transient_content_right(),
            metrics=host._layout.metrics,
            freshness_is_stale_safe=(
                host._projection_freshness_controller.has_stale_projection_geometry()
            ),
            source_revision=host._source_revision,
        )

    def _can_defer_immediate_projection_fallback_edit(
        self,
        *,
        previous_text: str | None,
        next_text: str,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
        projection_deferral_reason: str,
    ) -> bool:
        """Return whether an immediate-rebuild edit may become stale-safe."""

        host = self._host
        replacement = "" if replacement_text is None else replacement_text
        typed_character_requires_projection = bool(
            replacement_text
            and start is not None
            and end is not None
            and host._typed_character_requires_immediate_projection(
                replacement_text,
                start=start,
                end=end,
            )
        )
        syntax_sensitive_prefix = bool(
            replacement_text
            and start is not None
            and end is not None
            and host._can_defer_syntax_sensitive_autocomplete_prefix(
                start=start,
                end=end,
                replacement_text=replacement_text,
                normalized_text=next_text,
            )
        )
        can_defer, _reason = (
            host._projection_freshness_controller.can_defer_immediate_projection_fallback_edit(
                blockers=host._projection_freshness_blockers(),
                previous_text=previous_text,
                next_text=next_text,
                start=start,
                end=end,
                replacement_text=replacement_text,
                projection_deferral_reason=projection_deferral_reason,
                insertion_inside_projected_token=(
                    start is not None
                    and replacement_text not in {None, ""}
                    and self._source_insertion_is_inside_projected_token(start)
                ),
                deletion_intersects_projected_token=(
                    start is not None
                    and end is not None
                    and replacement_text == ""
                    and host._source_range_intersects_projected_token(
                        start=start,
                        end=end,
                    )
                ),
                transient_insertion_overlay_deferrable=(
                    start is not None
                    and end is not None
                    and replacement_text not in {None, ""}
                    and self._can_defer_transient_insertion_overlay(
                        start=start,
                        end=end,
                        replacement_text=replacement,
                    )
                ),
                typed_character_requires_immediate_projection=(
                    typed_character_requires_projection
                ),
                syntax_sensitive_autocomplete_prefix=syntax_sensitive_prefix,
            )
        )
        return can_defer

    def _source_insertion_is_inside_projected_token(
        self,
        source_position: int,
    ) -> bool:
        """Return whether an insertion would edit a projected token interior."""

        return any(
            token.source_start < source_position < token.source_end
            for token in self._host._projection_document.tokens
        )


def _can_defer_wrap_reflow_for_reason(projection_deferral_reason: str) -> bool:
    """Return whether policy allowed one immediate edit to remain stale-safe."""

    return projection_deferral_reason in _WRAP_REFLOW_DEFERRABLE_REASONS


__all__ = [
    "PromptProjectionApplyPath",
    "PromptProjectionIncrementalApplyController",
    "PromptProjectionIncrementalApplyHost",
    "PromptProjectionSourceChangeApplyOutcome",
    "PromptProjectionSourceChangeApplyRequest",
]
