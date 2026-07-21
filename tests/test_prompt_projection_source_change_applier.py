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

"""Guard the Phase 22 projection source-state application contract."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import is_dataclass

from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)
from substitute.presentation.editor.prompt_editor.editing_session.edit_controller import (
    PromptMutationSignalIntent,
    PromptProjectionRestoreApplication,
    PromptProjectionSourceApplicationMode,
    PromptProjectionSourceChangeApplication,
)
from substitute.presentation.editor.prompt_editor.projection.source_change_applier import (
    PromptProjectionCaretSync,
    PromptProjectionFreshnessOutcome,
    PromptProjectionFreshnessState,
    PromptProjectionSignalOutcome,
    PromptProjectionSourceChangeApplier,
    PromptProjectionSourceDocumentOutcome,
    PromptProjectionSourceDocumentRangeEdit,
    PromptProjectionSourceStateApplicationRequest,
    PromptProjectionSourceStateApplyPath,
    PromptProjectionSourceStateOutcome,
    PromptProjectionViewportInvalidation,
)
from substitute.presentation.editor.prompt_editor.projection.incremental_apply_controller import (
    PromptProjectionApplyPath,
    PromptProjectionSourceChangeApplyOutcome,
    PromptProjectionSourceChangeApplyRequest,
)
from substitute.presentation.editor.prompt_editor.projection.freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessBlockers,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretState,
    PromptProjectionDisplayMode,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetrics,
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.projection.layout_checkpoint import (
    PromptProjectionLayoutCheckpoint,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)


@dataclass(frozen=True, slots=True)
class _ProjectionPayload:
    """Carry projection restore state for source-change applier tests."""

    cursor_state: PromptProjectionCaretState
    anchor_state: PromptProjectionCaretState
    expanded_source_range: tuple[int, int] | None
    document_view: PromptDocumentView
    render_plan: PromptSyntaxRenderPlan
    layout_checkpoint: PromptProjectionLayoutCheckpoint | None = None


def _ensure_qapp() -> QApplication:
    """Return a QApplication for tests that touch Qt font metrics."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


class _SignalRecorder:
    """Record no-arg signal emissions."""

    def __init__(self) -> None:
        """Create an empty signal recorder."""

        self.count = 0

    def emit(self) -> None:
        """Record one signal emission."""

        self.count += 1


class _ViewportRecorder:
    """Record viewport repaint requests."""

    def __init__(self) -> None:
        """Create an empty viewport recorder."""

        self.update_count = 0
        self._width = 320
        self._height = 120

    def width(self) -> int:
        """Return a stable viewport width."""

        return self._width

    def height(self) -> int:
        """Return a stable viewport height."""

        return self._height

    def update(self) -> None:
        """Record one viewport update request."""

        self.update_count += 1


class _ScrollBarRecorder:
    """Record scrollbar value changes."""

    def __init__(self) -> None:
        """Create an empty scrollbar recorder."""

        self.values: list[int] = []

    def setValue(self, value: int) -> None:  # noqa: N802
        """Record one scrollbar value."""

        self.values.append(value)


class _SourceDocumentRecorder:
    """Record source document mirror operations."""

    def __init__(self) -> None:
        """Create an empty source-document recorder."""

        self.font_syncs = 0
        self.range_fallback_calls: list[tuple[str, str | None, int | None]] = []
        self.replacements: list[str] = []

    def sync_default_font(self, font: QFont) -> None:
        """Record a default font sync."""

        _ = font
        self.font_syncs += 1

    def replace_with_range_fallback(
        self,
        *,
        next_text: str,
        previous_text: str | None,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> bool:
        """Record one source mirror range/fallback update."""

        _ = end
        _ = replacement_text
        self.range_fallback_calls.append((next_text, previous_text, start))
        return True

    def replace_text(self, text: str) -> None:
        """Record one full source mirror replacement."""

        self.replacements.append(text)


class _SessionRecorder:
    """Record session state touched by source-change application."""

    def __init__(self) -> None:
        """Create empty session state."""

        self.diagnostics: tuple[object, ...] = ()
        self.autocomplete_preview: object | None = None
        self.expanded_source_range: tuple[int, int] | None = None
        self.autocomplete_preview_updates: list[object | None] = []

    def set_diagnostics(self, diagnostics: tuple[object, ...]) -> None:
        """Record diagnostic replacement."""

        self.diagnostics = diagnostics

    def set_autocomplete_preview(self, preview: object | None) -> None:
        """Record autocomplete preview replacement."""

        self.autocomplete_preview = preview
        self.autocomplete_preview_updates.append(preview)


class _MouseRecorder:
    """Record source-change pointer cleanup."""

    def __init__(self) -> None:
        """Create an empty mouse recorder."""

        self.cleared = 0

    def clear_pointer_state_for_source_replacement(self) -> None:
        """Record pointer cleanup."""

        self.cleared += 1


class _FreshnessControllerRecorder:
    """Record freshness-controller calls used by source-change tests."""

    def __init__(self) -> None:
        """Create an empty freshness controller recorder."""

        self.freshness = ProjectionFreshness.UNAVAILABLE
        self.pending_clear_count = 0
        self.can_defer_projection = False
        self.deferral_reason = "safe_typing"

    def clear_pending_after_immediate_apply(self) -> None:
        """Record pending update clearing through the freshness owner."""

        self.pending_clear_count += 1

    def has_stale_projection_geometry(self) -> bool:
        """Return whether deferred overlay geometry may be consumed."""

        return self.freshness is ProjectionFreshness.STALE_SAFE

    def transient_committed_source_revision(
        self,
        *,
        current_source_revision: int,
    ) -> int:
        """Return the committed source revision for transient overlays."""

        return current_source_revision

    def can_defer_source_rebuild_for_edit(
        self,
        *,
        blockers: PromptProjectionFreshnessBlockers,
        start: int,
        end: int,
        replaced_text: str,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        updated_text: str,
        normalized_text: str,
        edit_inside_projected_token: bool,
        delete_intersects_projected_token: bool,
        typed_character_requires_immediate_projection: bool,
        syntax_sensitive_autocomplete_prefix: bool,
    ) -> tuple[bool, str]:
        """Return configured deferral state through the freshness owner."""

        _ = blockers
        _ = start
        _ = end
        _ = replaced_text
        _ = replacement_text
        _ = origin
        _ = updated_text
        _ = normalized_text
        _ = edit_inside_projected_token
        _ = delete_intersects_projected_token
        _ = typed_character_requires_immediate_projection
        _ = syntax_sensitive_autocomplete_prefix
        return self.can_defer_projection, self.deferral_reason


class _ProjectionDocument:
    """Carry committed projection source text for deferred checks."""

    def __init__(self, source_text: str) -> None:
        """Store committed source text."""

        self.source_text = source_text
        self.tokens: tuple[object, ...] = ()


class _LayoutRecorder:
    """Provide the minimal layout context consumed by transient overlay owners."""

    document_margin = 4.0

    def __init__(self) -> None:
        """Create a layout recorder with real projection metrics."""

        _ensure_qapp()
        self.metrics: PromptProjectionMetrics = PromptProjectionMetricsFactory().create(
            base_font=QFont(),
            document_margin=self.document_margin,
            wrap_width=120.0,
        )

    def content_size(self) -> QSizeF:
        """Return a stable content size."""

        return QSizeF(120.0, 24.0)


class _IncrementalApplyControllerRecorder:
    """Record source-change projection application through the Phase 22.7 owner."""

    def __init__(self) -> None:
        """Create a controller fake with incremental success defaults."""

        self.requests: list[PromptProjectionSourceChangeApplyRequest] = []

    def apply_source_change_projection(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionSourceChangeApplyOutcome:
        """Record the request and report incremental catch-up."""

        self.requests.append(request)
        return PromptProjectionSourceChangeApplyOutcome(
            apply_path=PromptProjectionApplyPath.INCREMENTAL,
            fast_projection_applied=True,
        )


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
        self._incremental_apply_controller = _IncrementalApplyControllerRecorder()
        self._document_view = PromptDocumentView(
            source_text="alpha",
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
        )
        self._projection_document = _ProjectionDocument("alpha")
        self._layout = _LayoutRecorder()
        self._source_revision = 7
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

        return self._document_view.source_text

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
            autocomplete_preview_active=False,
            exact_weight_edit_active=False,
            expanded_source_range_active=False,
        )

    def _typed_character_requires_immediate_projection(
        self,
        character: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Treat no test character as syntax-sensitive."""

        _ = character
        _ = start
        _ = end
        return False

    def _can_defer_syntax_sensitive_autocomplete_prefix(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        normalized_text: str,
    ) -> bool:
        """Allow syntax-sensitive autocomplete prefix deferral in tests."""

        _ = start
        _ = end
        _ = replacement_text
        _ = normalized_text
        return True

    def _source_range_intersects_projected_token(
        self,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return whether a fake projected token intersects the source range."""

        _ = start
        _ = end
        return False

    def _source_edit_requires_canonical_rebuild(
        self,
        previous_source_text: str,
        next_source_text: str,
        *,
        start: int,
        end: int,
    ) -> bool:
        """Return configured source-local projection topology safety."""

        self.source_topology_checks.append(
            (previous_source_text, next_source_text, start, end)
        )
        return self.source_edit_requires_canonical_rebuild

    def _current_caret_document_rect(self) -> QRectF:
        """Return stable caret geometry for transient overlay tests."""

        return QRectF(1.0, 2.0, 3.0, 12.0)

    def _mark_source_text_changed(
        self,
        *,
        deferrable_projection: bool,
        source_revision: int,
        clear_diagnostic_fragment_cache: bool = True,
    ) -> None:
        """Record source change freshness inputs."""

        _ = clear_diagnostic_fragment_cache
        self._source_revision = source_revision
        self.marked_source_changes.append((deferrable_projection, source_revision))

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


def _session(source_text: str) -> PromptEditingSession[str]:
    """Return one editing session for projection contract tests."""

    cursor_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(source_text: str) -> PromptUndoSnapshot[str]:
    """Return one passive undo snapshot for projection contract tests."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=source_text,
    )


def _projection_payload(source_text: str) -> _ProjectionPayload:
    """Return one projection restore payload for applier owner tests."""

    cursor_position = len(source_text)
    return _ProjectionPayload(
        cursor_state=PromptProjectionCaretState(source_position=cursor_position),
        anchor_state=PromptProjectionCaretState(source_position=cursor_position),
        expanded_source_range=(0, len(source_text)),
        document_view=PromptDocumentView(
            source_text=source_text,
            segments=(),
            emphasis_spans=(),
            wildcard_spans=(),
            lora_spans=(),
            syntax_spans=(),
            has_trailing_comma=False,
        ),
        render_plan=PromptSyntaxRenderPlan(
            syntax_spans=(),
            renderer_views=(),
        ),
    )


def _projection_session(source_text: str) -> PromptEditingSession[_ProjectionPayload]:
    """Return one editing session with projection restore payloads."""

    cursor_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _projection_undo_snapshot(
    source_text: str,
) -> PromptUndoSnapshot[_ProjectionPayload]:
    """Return one undo snapshot carrying projection restore payload state."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        source_revision=7,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=_projection_payload(source_text),
    )


def _source_change_application() -> PromptProjectionSourceChangeApplication[str]:
    """Return one committed source-change application from the Phase 21 contract."""

    session = _session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )
    return PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        mode=PromptProjectionSourceApplicationMode.SOURCE_REPLACEMENT,
        source_edit_start=5,
        source_edit_end=5,
        source_edit_replacement_text=" beta",
        signal_intent=PromptMutationSignalIntent(
            emit_text_changed=True,
            emit_cursor_position_changed=True,
        ),
    )


def test_source_state_request_wraps_phase21_application_without_command_details() -> (
    None
):
    """The projection contract should consume committed applications only."""

    application = _source_change_application()

    request = PromptProjectionSourceStateApplicationRequest(
        application=application,
        current_source_revision=7,
        current_projection_source_text="alpha",
        reason="source_replacement",
    )

    assert request.application is application
    assert request.current_source_revision == 7
    assert request.current_projection_source_text == "alpha"
    assert request.reason == "source_replacement"


def test_source_change_applier_applies_source_replacement_through_ports() -> None:
    """Committed replacement should update mirror, caret, diagnostics, and signals."""

    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        signal_intent=PromptMutationSignalIntent(emit_text_changed=True),
    )
    host = _SourceChangeHost()
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    assert host.marked_source_changes == [(False, 8)]
    assert host._source_document_adapter.font_syncs == 1
    assert host._source_document_adapter.range_fallback_calls == [
        ("alpha beta", "alpha", 5)
    ]
    assert host._mouse_handler.cleared == 1
    assert host.caret_state_updates == [(10, 10, "fast_source_replace")]
    assert host.textChanged.count == 1
    assert host.cursorPositionChanged.count == 1
    assert host.horizontal_origin_marks == 1


def test_source_change_applier_uses_semantic_remapper_for_optimistic_state() -> None:
    """Immediate source changes should consume the pure semantic remap service."""

    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text="!",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        signal_intent=PromptMutationSignalIntent(emit_text_changed=True),
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.deferral_reason = (
        "plain_single_character_requires_layout"
    )
    host._session.expanded_source_range = (0, 5)
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    assert host._document_view.source_text == "alpha!"
    assert host._render_plan.renderer_views == ()
    assert host._session.expanded_source_range == (0, 6)


def test_source_change_applier_rebuilds_source_derived_projection_structure() -> None:
    """Scene-like structure changes should bypass stale-safe text deferral."""

    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text="x",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        signal_intent=PromptMutationSignalIntent(emit_text_changed=True),
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.can_defer_projection = True
    host.source_edit_requires_canonical_rebuild = True
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    request = host._incremental_apply_controller.requests[-1]
    assert request.projection_deferral_reason == "source_projection_topology_changed"
    assert host.source_topology_checks[-1] == ("alpha", "alphax", 5, 5)
    assert host.marked_source_changes[-1] == (
        False,
        source_change.next_snapshot.source_revision,
    )
    assert host._document_view.source_text == "alphax"


def test_source_change_applier_preserves_no_op_source_change_as_cursor_update() -> None:
    """No-op source replacements should not mirror text or emit source signals."""

    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=2,
        end=2,
        replacement_text="",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=False,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
    )
    host = _SourceChangeHost()
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    assert host.cursor_position_updates == [(2, 2)]
    assert host._source_document_adapter.range_fallback_calls == []
    assert host.textChanged.count == 0
    assert host.cursorPositionChanged.count == 0


def test_source_change_applier_handles_full_source_scroll_and_geometry_warm() -> None:
    """Full-source applications should preserve reset-scroll and warm intents."""

    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=0,
        end=5,
        replacement_text="omega",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        mode=PromptProjectionSourceApplicationMode.FULL_SOURCE,
        source_edit_start=0,
        source_edit_end=5,
        source_edit_replacement_text="omega",
        reset_scroll_to_top=True,
        schedule_geometry_reuse_warm_reason="full_source",
        signal_intent=PromptMutationSignalIntent(emit_text_changed=True),
    )
    host = _SourceChangeHost()
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    assert host._scroll_bar.values == [0]
    assert host.geometry_warm_reasons == ["full_source"]
    assert host._source_document_adapter.range_fallback_calls == [("omega", "alpha", 0)]
    assert host.textChanged.count == 1


def test_source_change_applier_rebuilds_preview_active_replacements() -> None:
    """Autocomplete preview requires immediate projection for source replacements."""

    _ensure_qapp()
    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text="x",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        signal_intent=PromptMutationSignalIntent(emit_text_changed=True),
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.can_defer_projection = True
    host._session.autocomplete_preview = object()
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    assert host.marked_source_changes == [(False, 8)]
    assert host.autocomplete_preview_clear_count == 1
    assert host._session.autocomplete_preview_updates == [None]
    assert host._source_document_adapter.range_fallback_calls == [
        ("alphax", "alpha", 5)
    ]
    assert host.caret_state_updates == [(6, 6, "fast_source_replace")]
    assert host._transient_edit_overlays.insertion_overlay is None
    assert host.transient_insert_paint_updates == 0
    assert host.transient_delete_paint_updates == 0
    assert host.textChanged.count == 1


def test_source_change_applier_rebuilds_whitespace_replacements() -> None:
    """Whitespace edits require immediate projection to clear stale inline previews."""

    _ensure_qapp()
    session = _projection_session("alpha")
    source_change = session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" ",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    application = PromptProjectionSourceChangeApplication(
        source_change=source_change,
        previous_source_text="alpha",
        origin=PromptSourceEditOrigin.TYPED,
        signal_intent=PromptMutationSignalIntent(emit_text_changed=True),
    )
    host = _SourceChangeHost()
    host._projection_freshness_controller.can_defer_projection = True
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_source_change_application(application)

    assert host.marked_source_changes == [(False, 8)]
    assert host._source_document_adapter.range_fallback_calls == [
        ("alpha ", "alpha", 5)
    ]
    assert host.caret_state_updates == [(6, 6, "fast_source_replace")]
    assert host._transient_edit_overlays.insertion_overlay is None
    assert host.textChanged.count == 1


def test_source_change_applier_restores_undo_state_through_ports() -> None:
    """Restore applications should route exact history state through projection ports."""

    session = _projection_session("alpha")
    session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_projection_undo_snapshot("alpha"),
    )
    restore_result = session.undo(_projection_undo_snapshot("alpha beta"))
    assert restore_result is not None
    application = PromptProjectionRestoreApplication(
        restore_result=restore_result,
        signal_intent=PromptMutationSignalIntent(
            undo_availability_change=restore_result.availability_change,
        ),
    )
    host = _SourceChangeHost()
    applier = PromptProjectionSourceChangeApplier[_ProjectionPayload](host)

    applier.apply_restore_application(application)

    assert host._source_document_adapter.replacements == ["alpha"]
    assert host._document_view.source_text == "alpha"
    assert host._session.expanded_source_range == (0, 5)
    assert host.marked_source_changes == [(False, 9)]
    assert host.rebuilds == 0
    assert len(host._incremental_apply_controller.requests) == 1
    projection_request = host._incremental_apply_controller.requests[0]
    assert projection_request.previous_source_text == "alpha"
    assert projection_request.text == "alpha"
    assert projection_request.projection_deferral_reason == "history_restore"
    assert host.caret_visibility_checks == 1
    assert host.caret_blink_restarts == 1
    assert host.textChanged.count == 1
    assert host.cursorPositionChanged.count == 1


def test_source_state_outcome_represents_deferred_overlay_path() -> None:
    """Deferred typing should have typed viewport, caret, and freshness effects."""

    outcome = PromptProjectionSourceStateOutcome(
        apply_path=PromptProjectionSourceStateApplyPath.DEFERRED_OVERLAY,
        source_revision=8,
        source_document=PromptProjectionSourceDocumentOutcome(
            range_edit=PromptProjectionSourceDocumentRangeEdit(
                previous_text="alpha",
                next_text="alphax",
                start=5,
                end=5,
                replacement_text="x",
            )
        ),
        viewport=PromptProjectionViewportInvalidation(
            update_rects=("transient-insertion",),
            invalidate_paint_cache=True,
        ),
        caret=PromptProjectionCaretSync(
            cursor_position=6,
            anchor_position=6,
            ensure_visible=True,
            restart_blink=True,
            use_transient_geometry=True,
            mark_horizontal_movement_origin=True,
        ),
        freshness=PromptProjectionFreshnessOutcome(
            source_revision=8,
            state=PromptProjectionFreshnessState.STALE_SAFE,
            schedule_reason="safe_typing",
            last_source_edit_deferrable=True,
        ),
        signals=PromptProjectionSignalOutcome(
            emit_text_changed=True,
            emit_cursor_position_changed=True,
        ),
        clear_autocomplete_preview=True,
        clear_pointer_state=True,
        remap_diagnostics=True,
    )

    assert outcome.apply_path is PromptProjectionSourceStateApplyPath.DEFERRED_OVERLAY
    assert outcome.source_document.range_edit is not None
    assert outcome.source_document.range_edit.replacement_text == "x"
    assert outcome.viewport.update_rects == ("transient-insertion",)
    assert outcome.caret.use_transient_geometry is True
    assert outcome.freshness.state is PromptProjectionFreshnessState.STALE_SAFE
    assert outcome.signals.emit_text_changed is True
    assert outcome.clear_autocomplete_preview is True
    assert outcome.remap_diagnostics is True


def test_source_state_outcome_represents_cancelled_and_rebuild_fallback_paths() -> None:
    """The baseline contract must name stale cancellation and rebuild recovery."""

    cancelled = PromptProjectionSourceStateOutcome(
        apply_path=PromptProjectionSourceStateApplyPath.CANCELLED_STALE,
        freshness=PromptProjectionFreshnessOutcome(cancel_pending=True),
    )
    fallback = PromptProjectionSourceStateOutcome(
        apply_path=PromptProjectionSourceStateApplyPath.FULL_REBUILD,
        viewport=PromptProjectionViewportInvalidation(
            update_viewport=True,
            invalidate_layout=True,
            invalidate_paint_cache=True,
            invalidate_diagnostic_fragments=True,
        ),
        freshness=PromptProjectionFreshnessOutcome(
            state=PromptProjectionFreshnessState.FRESH,
            committed_metrics_changed=True,
        ),
    )

    assert cancelled.apply_path is PromptProjectionSourceStateApplyPath.CANCELLED_STALE
    assert cancelled.freshness.cancel_pending is True
    assert fallback.apply_path is PromptProjectionSourceStateApplyPath.FULL_REBUILD
    assert fallback.viewport.invalidate_layout is True
    assert fallback.freshness.committed_metrics_changed is True


def test_source_state_outcome_represents_restore_application_signals() -> None:
    """Undo/redo restore inputs should become source-state signal/caret effects."""

    session = _session("alpha")
    session.replace_source_range(
        start=5,
        end=5,
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )
    restore_result = session.undo(_undo_snapshot("alpha beta"))
    assert restore_result is not None
    application = PromptProjectionRestoreApplication(
        restore_result=restore_result,
        signal_intent=PromptMutationSignalIntent(
            undo_availability_change=restore_result.availability_change,
            emit_text_changed=True,
            emit_cursor_position_changed=True,
        ),
    )

    request = PromptProjectionSourceStateApplicationRequest(
        application=application,
        current_source_revision=8,
        current_projection_source_text="alpha beta",
        reason="undo",
    )
    outcome = PromptProjectionSourceStateOutcome(
        apply_path=PromptProjectionSourceStateApplyPath.FULL_REBUILD,
        source_revision=restore_result.source_snapshot.source_revision,
        source_document=PromptProjectionSourceDocumentOutcome(full_text="alpha"),
        caret=PromptProjectionCaretSync(cursor_position=5, anchor_position=5),
        signals=PromptProjectionSignalOutcome(
            emit_text_changed=application.signal_intent.emit_text_changed,
            emit_cursor_position_changed=(
                application.signal_intent.emit_cursor_position_changed
            ),
        ),
    )

    assert isinstance(request.application, PromptProjectionRestoreApplication)
    assert outcome.source_document.full_text == "alpha"
    assert outcome.caret.cursor_position == 5
    assert outcome.signals.emit_cursor_position_changed is True


def test_source_state_contract_values_are_passive_dataclasses() -> None:
    """The Phase 22.1 contract should stay passive and easy to move behind owners."""

    passive_types = (
        PromptProjectionCaretSync,
        PromptProjectionFreshnessOutcome,
        PromptProjectionSignalOutcome,
        PromptProjectionSourceDocumentOutcome,
        PromptProjectionSourceDocumentRangeEdit,
        PromptProjectionSourceStateApplicationRequest,
        PromptProjectionSourceStateOutcome,
        PromptProjectionViewportInvalidation,
    )

    assert all(is_dataclass(passive_type) for passive_type in passive_types)
