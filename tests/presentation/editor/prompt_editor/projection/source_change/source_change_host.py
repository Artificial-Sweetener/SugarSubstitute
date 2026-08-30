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

"""Provide the source-change transaction host double."""

from __future__ import annotations


from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_buffer import (
    PromptSourceSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorState,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    PromptProjectionFreshnessBlockers,
)
from substitute.presentation.editor.prompt_editor.projection.edit_to_frame import (
    PromptLayoutEditToFrameCoordinator,
)
from substitute.presentation.editor.prompt_editor.projection.tokens import (
    PromptProjectionInlineObjectRendererRegistry,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)

from .projection_state import (
    _EditPipelineRecorder,
    _ProjectionDocument,
    _ScrollBarRecorder,
    _SignalRecorder,
    _ViewportRecorder,
)
from .source_state import (
    _FreshnessControllerRecorder,
    _MouseRecorder,
    _SessionRecorder,
    _SourceDocumentRecorder,
)


class _ProjectionApplicatorRecorder:
    """Record canonical-topology queries for the source-change host."""

    def __init__(self, host: _SourceChangeHost) -> None:
        """Store the host carrying configured query results."""

        self._host = host

    def source_edit_requires_canonical_rebuild(
        self,
        previous_source_text: str,
        next_source_text: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return the configured topology result and record its inputs."""

        self._host.source_topology_checks.append(
            (previous_source_text, next_source_text, start, end)
        )
        return self._host.source_edit_requires_canonical_rebuild


class _SourceChangeHost:
    """Fake source-change host that records applier-side effects."""

    def __init__(self) -> None:
        """Create a host with default immediate-apply behavior."""

        self.textChanged = _SignalRecorder()
        self.cursorPositionChanged = _SignalRecorder()
        self._session = _SessionRecorder()
        self._mouse_handler = _MouseRecorder()
        self._source_document_adapter = _SourceDocumentRecorder()
        self._projection_freshness_controller = _FreshnessControllerRecorder()
        self._edit_pipeline = _EditPipelineRecorder()
        document_view = PromptDocumentView(
            source_text="alpha",
            segments=(),
            emphasis_spans=(),
            wildcard_spans=(),
            lora_spans=(),
            syntax_spans=(),
            region_structure=PromptRegionStructureView.empty(len("alpha")),
            has_trailing_comma=False,
        )
        render_plan = PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        )
        self._editor_state = PromptEditorState[
            PromptDocumentView,
            PromptSyntaxRenderPlan,
            _ProjectionDocument,
            object,
            object,
        ](
            source=PromptSourceSnapshot(source_text="alpha", source_revision=7),
            semantic_document=document_view,
            render_plan=render_plan,
            projection_document=_ProjectionDocument("alpha"),
        )
        self._layout = PromptLayoutEditToFrameCoordinator(
            PromptProjectionInlineObjectRendererRegistry(())
        )
        self._caret_visibility_prompt_state_revision = 0
        self._cursor_state = PromptProjectionCaretState(source_position=0)
        self._anchor_state = PromptProjectionCaretState(source_position=0)
        self._caret_rect_override: QRectF | None = None
        self._transient_edit_overlays = PromptProjectionTransientEditOverlayController()
        self._preferred_x: float | None = 3.0
        self._scroll_bar = _ScrollBarRecorder()
        self._viewport = _ViewportRecorder()
        self.marked_source_changes: list[tuple[bool, int]] = []
        self.cursor_position_updates: list[tuple[int, int]] = []
        self.undo_available_emissions: list[bool] = []
        self.redo_available_emissions: list[bool] = []
        self.geometry_warm_reasons: list[str] = []
        self.caret_state_updates: list[tuple[int, int, str]] = []
        self.deferred_caret_updates: list[tuple[int, int]] = []
        self.rebuilds = 0
        self.autocomplete_preview_clear_count = 0
        self.layout_sync_commits = 0
        self.horizontal_origin_marks = 0
        self.transient_insert_paint_updates = 0
        self.transient_delete_paint_updates = 0
        self.caret_visibility_checks = 0
        self.caret_blink_restarts = 0
        self.implicit_parenthesis_depth = 0
        self.source_edit_requires_canonical_rebuild = False
        self.source_topology_checks: list[tuple[str, str, int, int]] = []
        self._projection_applicator = _ProjectionApplicatorRecorder(self)

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record undo availability emission."""

        self.undo_available_emissions.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record redo availability emission."""

        self.redo_available_emissions.append(available)

    def notify_implicit_parenthesis_authored(self, nesting_depth: int) -> None:
        """Record nested implicit emphasis education notification."""

        self.implicit_parenthesis_depth = nesting_depth

    def set_cursor_positions(
        self, *, cursor_position: int, anchor_position: int
    ) -> None:
        """Record cursor position updates."""

        self.cursor_position_updates.append((cursor_position, anchor_position))

    def verticalScrollBar(self) -> _ScrollBarRecorder:  # noqa: N802
        """Return the fake scrollbar."""

        return self._scroll_bar

    def viewport(self) -> _ViewportRecorder:
        """Return the fake viewport."""

        return self._viewport

    def font(self) -> QFont:
        """Return a stable font for mirror sync."""

        return QFont()

    def toPlainText(self) -> str:  # noqa: N802
        """Return the live source text for transient overlay decisions."""

        return self._editor_state.semantic.document.source_text

    def clear_autocomplete_preview_state(self) -> None:
        """Record authoritative autocomplete preview owner clears."""

        self.autocomplete_preview_clear_count += 1
        self._session.set_autocomplete_preview(None)

    def _schedule_projection_geometry_reuse_warm(self, *, reason: str) -> None:
        """Record geometry warm scheduling."""

        self.geometry_warm_reasons.append(reason)

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return an unblocked projection context for source-change tests."""

        return PromptProjectionFreshnessBlockers(
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            reorder_preview_active=False,
            autocomplete_preview_active=self._session.autocomplete_preview is not None,
            exact_weight_edit_active=False,
            expanded_source_range_active=False,
        )

    def _current_caret_document_rect(self) -> QRectF:
        """Return stable caret geometry for transient overlay tests."""

        return QRectF(1.0, 2.0, 3.0, 12.0)

    def _mark_source_text_changed(
        self,
        *,
        deferrable_projection: bool,
        source_snapshot: PromptSourceSnapshot,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> None:
        """Record source change freshness inputs."""

        _ = clear_diagnostic_fragment_cache
        source_identity = self._editor_state.publish_source(source_snapshot)
        self.marked_source_changes.append(
            (deferrable_projection, source_identity.source_revision)
        )

    def _rebuild_projection(self) -> None:
        """Record a projection rebuild."""

        self.rebuilds += 1

    def _clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Accept diagnostic cache clear calls."""

        _ = reason

    def _set_deferred_source_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Record deferred caret states."""

        self.deferred_caret_updates.append(
            (cursor_state.source_position, anchor_state.source_position)
        )

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
        """Record caret state updates."""

        _ = reset_preferred_x
        _ = caret_rect_override
        _ = collapse_expanded_token
        _ = preserve_unmapped_source_positions
        self.caret_state_updates.append(
            (cursor_state.source_position, anchor_state.source_position, reason)
        )

    def _sync_editing_session_to_caret_states(self) -> None:
        """Accept editing-session sync calls."""

    def _ensure_caret_visible(self) -> None:
        """Record caret visibility checks."""

        self.caret_visibility_checks += 1

    def _update_transient_insertion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
    ) -> None:
        """Record insertion overlay paint updates."""

        _ = previous_overlay
        _ = next_overlay
        self.transient_insert_paint_updates += 1

    def _update_transient_deletion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Record deletion overlay paint updates."""

        _ = previous_overlay
        _ = next_overlay
        self.transient_delete_paint_updates += 1

    def _restart_caret_blink_cycle(self) -> None:
        """Record caret blink restart."""

        self.caret_blink_restarts += 1

    def _clear_transient_caret_geometry(self) -> None:
        """Clear transient caret state."""

        self._transient_edit_overlays.clear()

    def _sync_layout_state(self, *, commit_projection: bool = False) -> None:
        """Record layout sync calls."""

        if commit_projection:
            self.layout_sync_commits += 1

    def _mark_source_edit_horizontal_movement_origin(self) -> None:
        """Record horizontal movement origin marking."""

        self.horizontal_origin_marks += 1
