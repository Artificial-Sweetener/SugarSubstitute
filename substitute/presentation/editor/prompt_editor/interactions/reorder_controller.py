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

"""Coordinate prompt segment reorder mode without owning preview projection."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Protocol, cast

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptMutationService,
    PromptReorderChipView,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderSessionView,
    PromptReorderStateView,
    PromptSyntaxProfile,
    PromptSyntaxService,
)

from ..commands import (
    PromptCommandSourceIdentity,
    PromptReorderCommandResult,
    PromptReorderLayoutCommitRequest,
)
from ..models import (
    PromptEditorInteractionMode,
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderCommitSnapshot,
    PromptReorderKeyboardMoveIntent,
    SegmentReorderSession,
)
from ..overlays import PromptReorderDragIntent
from ..projection.reorder_interaction_geometry import (
    PromptReorderLayoutPolicy,
    layout_view_key,
)
from ..projection.reorder_preview import PromptReorderPreviewState
from ..projection.reorder_preview_projection import (
    PromptReorderPreviewProjectionProvider,
    PromptReorderPreviewProjectionResult,
)
from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from .reorder_preview_sync import (
    PromptReorderPreviewSyncContext,
    PromptReorderPreviewSyncController,
)
from .reorder_session import PromptReorderSessionController


class _OverlaySignal(Protocol):
    """Describe the Qt signal seam required from reorder overlays."""

    def connect(self, callback: Callable[[], None]) -> object:
        """Connect one callback to the signal."""


class PromptReorderOverlayPort(Protocol):
    """Expose the reorder overlay operations used by interaction orchestration."""

    previewLayoutChanged: _OverlaySignal

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Set the callback used for pointer drag intent."""

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Set the callback used for prepared commit intent."""

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Set the callback used for cancel intent."""

    def set_chips(
        self,
        document_view: PromptDocumentView,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[PromptReorderChipView, ...],
        active_chip_index: int | None = None,
        source_revision: int | None = None,
    ) -> None:
        """Populate overlay hotspots from the current reorder-chip snapshot."""

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return prepared reorder state for controller-owned command commit."""

    def preview_reorder_state(self) -> PromptReorderStateView | None:
        """Return authoritative state represented by the active visual preview."""

    def base_drag_reorder_state(self) -> PromptReorderStateView | None:
        """Return authoritative state represented by the base-drag preview."""

    def preview_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the current visual preview layout."""

    def base_drag_layout_view(self) -> PromptReorderLayoutView | None:
        """Return the base drag layout when one exists."""

    def set_preview_snapshot(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Apply controller-built preview snapshots."""

    def dragged_segment_index(self) -> int | None:
        """Return the currently dragged segment index."""

    def drop_target(self) -> object | None:
        """Return the active drop target for diagnostics."""

    def has_base_drag_placement_geometry(self) -> bool:
        """Return whether drag hit testing has placement geometry."""

    def should_flush_initial_landing_shadow_sync(self) -> bool:
        """Return whether the first landing shadow sync should flush immediately."""

    def current_instrumentation_work_unit_id(self) -> int:
        """Return the current overlay work-unit id."""

    def instrumentation_gesture_id(self) -> int | None:
        """Return the current gesture id."""

    def instrumentation_event_id(self) -> int | None:
        """Return the current event id."""

    def is_drag_pointer_loop_active(self) -> bool:
        """Return whether overlay pointer processing is active."""

    def record_preview_scheduler_event(self, event: str) -> None:
        """Record scheduler event classifications."""

    def record_preview_sync_decision(self, *, immediate: bool) -> None:
        """Record preview scheduling decisions."""

    def record_preview_sync_elapsed(self, elapsed_ms: float) -> None:
        """Record preview-sync elapsed time."""

    def record_render_plan_elapsed(self, elapsed_ms: float) -> None:
        """Record render-plan elapsed time."""

    def refresh_geometry(self, *, reason: str = "unspecified") -> None:
        """Refresh overlay geometry."""

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Apply pending autoscroll geometry invalidation if one exists."""

    def needs_position_refresh(self, *, reason: str = "unspecified") -> bool:
        """Return whether viewport positioning inputs changed."""

    def move_active_chip_left(self) -> bool:
        """Move the active chip left when possible."""

    def move_active_chip_right(self) -> bool:
        """Move the active chip right when possible."""

    def move_active_chip_up(self) -> bool:
        """Move the active chip up when possible."""

    def move_active_chip_down(self) -> bool:
        """Move the active chip down when possible."""

    def cancel_drag(self) -> None:
        """Clear drag visuals without mutating source."""

    def show(self) -> None:
        """Show the overlay."""

    def close(self) -> bool:
        """Close the overlay."""

    def deleteLater(self) -> None:  # noqa: N802
        """Schedule overlay deletion."""


class PromptReorderOverlayFactory(Protocol):
    """Create reorder overlays for interaction owners without concrete imports."""

    def create_segment_overlay(
        self,
        editor: QWidget,
        *,
        layout_policy: PromptReorderLayoutPolicy,
    ) -> object:
        """Return one reorder overlay port bound to the supplied editor."""


class _SelectionLike(Protocol):
    """Describe the minimal selection wrapper used by reorder cursor helpers."""

    def isEmpty(self) -> bool:
        """Return whether the current selection is empty."""


class PromptReorderCursor(Protocol):
    """Describe the cursor operations needed by reorder session capture."""

    def position(self) -> int:
        """Return the current cursor position."""

    def selection(self) -> _SelectionLike:
        """Return a Qt-like selection wrapper."""

    def selectionStart(self) -> int:
        """Return the inclusive selection start."""

    def selectionEnd(self) -> int:
        """Return the exclusive selection end."""

    def setPosition(self, pos: int, mode: object | None = None) -> None:
        """Move or extend the cursor selection."""


class PromptReorderEditorHost(Protocol):
    """Expose editor APIs required by reorder interaction orchestration."""

    def textCursor(self) -> PromptReorderCursor:
        """Return the editor's live cursor object."""

    def setTextCursor(self, cursor: PromptReorderCursor) -> None:
        """Persist the supplied cursor selection back to the editor."""

    def toPlainText(self) -> str:
        """Return the editor's plain-text contents."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current source identity used by prepared commands."""

    def execute_reorder_action(
        self,
        request: PromptReorderLayoutCommitRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptReorderCommandResult[object]:
        """Execute one prepared prompt reorder action through commands."""

    def clear_reorder_preview_state(self) -> None:
        """Clear any active reorder preview state from the editor surface."""

    def set_reorder_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
    ) -> None:
        """Replace the explicit reorder preview state painted by the editor surface."""

    def setFocus(self) -> None:
        """Restore input focus to the editor after entering reorder mode."""


class PromptReorderHost(Protocol):
    """Expose non-visual collaborators needed by reorder orchestration."""

    def current_reorder_document_view(self) -> PromptDocumentView:
        """Return the current prompt document snapshot used for reorder entry."""

    def segment_reorder_enabled(self) -> bool:
        """Return whether segment reorder mode may be entered."""

    def clear_transient_state_for_reorder(self) -> None:
        """Clear autocomplete, syntax, and emphasis transients before reorder."""

    def apply_reorder_result(
        self,
        result: PromptReorderCommandResult[object],
    ) -> None:
        """Adopt prompt state returned by one reorder command."""


class PromptReorderController:
    """Own prompt segment reorder mode orchestration and commit intent."""

    _REORDER_PREVIEW_SYNC_INTERVAL_MS = 16

    def __init__(
        self,
        editor: PromptReorderEditorHost,
        *,
        host: PromptReorderHost,
        document_service: PromptDocumentService,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
        preview_projection_provider: PromptReorderPreviewProjectionProvider,
        overlay_factory: PromptReorderOverlayFactory,
    ) -> None:
        """Store collaborators used by reorder mode without taking preview ownership."""

        self._editor = editor
        self._host = host
        self._document_service = document_service
        self._mutation_service = mutation_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._preview_projection_provider = preview_projection_provider
        self._overlay_factory = overlay_factory
        self._interaction_mode = PromptEditorInteractionMode.TEXT_EDITING
        self._session_controller = PromptReorderSessionController()
        self._segment_overlay: PromptReorderOverlayPort | None = None
        self._preview_sync = PromptReorderPreviewSyncController(
            interval_ms=self._REORDER_PREVIEW_SYNC_INTERVAL_MS,
            run_sync=lambda: self._sync_reorder_preview_from_overlay(),
            pointer_revision=self._current_pointer_work_unit_id,
            record_scheduler_event=self._record_preview_scheduler_event,
        )

    @property
    def segment_overlay(self) -> PromptReorderOverlayPort | None:
        """Return the live segment reorder overlay when it exists."""

        return self._segment_overlay

    @property
    def interaction_mode(self) -> PromptEditorInteractionMode:
        """Return the active prompt-editor interaction mode."""

        return self._interaction_mode

    @property
    def segment_reorder_session(self) -> SegmentReorderSession:
        """Return the current reorder session for focused tests."""

        return self._session_controller.session

    @property
    def latest_commit_snapshot(self) -> PromptReorderCommitSnapshot | None:
        """Return the authoritative commit snapshot owned by this controller."""

        return self._session_controller.latest_commit_snapshot

    def enter_segment_reorder_mode(self) -> None:
        """Enter reorder mode and show the segment overlay when available."""

        self._show_segment_overlay()

    def cancel_segment_reorder_mode(
        self,
        *,
        restore_selection: bool = True,
    ) -> None:
        """Cancel reorder mode without mutating prompt source."""

        self.handle_reorder_cancel_intent(
            PromptReorderCancelIntent(
                reason="controller_cancel",
                restore_selection=restore_selection,
            )
        )

    def commit_and_close_segment_overlay(
        self,
        intent: PromptReorderCommitIntent | None = None,
    ) -> None:
        """Persist reordered prompt segments through the reorder command boundary."""

        if intent is None:
            intent = PromptReorderCommitIntent(reason="controller_commit")
        self.handle_reorder_commit_intent(intent)

    def handle_reorder_commit_intent(
        self,
        intent: PromptReorderCommitIntent,
    ) -> None:
        """Persist reordered prompt segments in response to a typed commit intent."""

        total_started_at = reorder_drag_started_at()
        overlay = self._segment_overlay
        if overlay is None:
            log_reorder_drag_timing(
                "interaction.commit_segment_overlay.noop",
                started_at=total_started_at,
                reason="no_overlay",
                intent_reason=intent.reason,
            )
            return

        snapshot = (
            intent.snapshot
            or self._session_controller.latest_commit_snapshot
            or overlay.commit_snapshot()
        )
        self._session_controller.capture_snapshot(snapshot)
        if not snapshot.has_reordered:
            self._close_segment_overlay(restore_selection=True)
            log_reorder_drag_timing(
                "interaction.commit_segment_overlay.noop",
                started_at=total_started_at,
                reason="unchanged_order",
                intent_reason=intent.reason,
            )
            return

        current_layout_view = snapshot.layout_view
        current_reorder_state = snapshot.reorder_state
        if current_reorder_state is None:
            self._close_segment_overlay(restore_selection=True)
            log_reorder_drag_timing(
                "interaction.commit_segment_overlay.noop",
                started_at=total_started_at,
                reason="missing_reorder_state",
                intent_reason=intent.reason,
            )
            return
        reorder_session = self._session_controller.session
        relative_selection_available = (
            reorder_session.selection_start_offset_within_active_chip is not None
            and reorder_session.selection_end_offset_within_active_chip is not None
        )
        phase_started_at = reorder_drag_started_at()
        self._close_segment_overlay(restore_selection=not relative_selection_available)
        close_elapsed_ms = log_reorder_drag_timing(
            "interaction.commit_segment_overlay.close",
            started_at=phase_started_at,
            relative_selection_available=relative_selection_available,
            intent_reason=intent.reason,
        )
        phase_started_at = reorder_drag_started_at()
        command_result = self._editor.execute_reorder_action(
            PromptReorderLayoutCommitRequest(
                selected_chip_index=reorder_session.active_segment_index,
                reorder_state=current_reorder_state,
                layout_view=current_layout_view,
                source_identity=self._editor.prompt_command_source_identity(),
                selection_start_offset_within_selected_chip=(
                    reorder_session.selection_start_offset_within_active_chip
                    if relative_selection_available
                    else None
                ),
                selection_end_offset_within_selected_chip=(
                    reorder_session.selection_end_offset_within_active_chip
                    if relative_selection_available
                    else None
                ),
            ),
            mutation_service=self._mutation_service,
            syntax_service=self._syntax_service,
            syntax_profile=self._syntax_profile,
        )
        command_elapsed_ms = log_reorder_drag_timing(
            "interaction.commit_segment_overlay.command",
            started_at=phase_started_at,
            active_chip_index=reorder_session.active_segment_index,
            intent_reason=intent.reason,
            row_count=0
            if current_layout_view is None
            else len(current_layout_view.rows),
            gap_count=0
            if current_layout_view is None
            else len(current_layout_view.gaps),
            text_length=(
                len(command_result.mutation.text)
                if command_result.mutation is not None
                else len(self._editor.toPlainText())
            ),
        )
        phase_started_at = reorder_drag_started_at()
        self._host.apply_reorder_result(command_result)
        apply_elapsed_ms = log_reorder_drag_timing(
            "interaction.commit_segment_overlay.apply_command_result",
            started_at=phase_started_at,
            relative_selection_available=relative_selection_available,
            intent_reason=intent.reason,
            text_length=(
                len(command_result.mutation.text)
                if command_result.mutation is not None
                else len(self._editor.toPlainText())
            ),
        )
        log_reorder_drag_timing(
            "interaction.commit_segment_overlay.total",
            started_at=total_started_at,
            relative_selection_available=relative_selection_available,
            intent_reason=intent.reason,
            close_elapsed_ms=f"{close_elapsed_ms:.3f}",
            command_elapsed_ms=f"{command_elapsed_ms:.3f}",
            apply_elapsed_ms=f"{apply_elapsed_ms:.3f}",
        )

    def position_segment_overlay(self) -> None:
        """Align the segment overlay with the visible editor viewport."""

        self._position_segment_overlay()

    def handle_reorder_cancel_intent(
        self,
        intent: PromptReorderCancelIntent,
    ) -> None:
        """Cancel reorder mode in response to a typed cancel intent."""

        self._cancel_segment_overlay(
            restore_selection=intent.restore_selection,
            reason=intent.reason,
        )

    def move_keyboard_reorder_chip(
        self,
        intent: PromptReorderKeyboardMoveIntent,
    ) -> None:
        """Apply one keyboard reorder step through synchronized preview geometry."""

        moved = self._apply_keyboard_move_intent(intent)
        if not moved and self.has_pending_reorder_preview_sync():
            self.flush_pending_reorder_preview_sync(
                reason="keyboard_reorder_prepare",
                forced=True,
            )
            moved = self._apply_keyboard_move_intent(intent)
        if moved:
            self._capture_keyboard_reorder_commit_snapshot()
            self.flush_pending_reorder_preview_sync(
                reason="keyboard_reorder_key",
                forced=True,
            )

    def has_pending_reorder_preview_sync(self) -> bool:
        """Return whether keyboard reorder should flush pending preview geometry."""

        return self._preview_sync.has_pending()

    def _apply_keyboard_move_intent(
        self,
        intent: PromptReorderKeyboardMoveIntent,
    ) -> bool:
        """Apply one typed keyboard reorder intent to the active overlay port."""

        overlay = self._segment_overlay
        if overlay is None:
            return False
        if intent.direction == "left":
            return overlay.move_active_chip_left()
        if intent.direction == "right":
            return overlay.move_active_chip_right()
        if intent.direction == "up":
            return overlay.move_active_chip_up()
        return overlay.move_active_chip_down()

    def _capture_keyboard_reorder_commit_snapshot(self) -> None:
        """Capture authoritative keyboard commit state before preview display sync."""

        self._sync_segment_reorder_session_from_overlay_snapshot()

    def reset_reorder_preview(self, *, reason: str) -> None:
        """Clear projection preview cache/state for one reorder lifecycle reason."""

        self._editor.clear_reorder_preview_state()
        self._preview_projection_provider.clear_cache(reason=reason)

    def schedule_reorder_preview_sync(
        self,
        *,
        reason: str = "preview_changed",
    ) -> None:
        """Coalesce expensive reorder preview projection work latest-wins."""

        overlay = self._segment_overlay
        self._preview_sync.schedule(
            reason=reason,
            context=self._preview_sync_context(overlay),
            record_decision=lambda immediate: self._record_preview_sync_decision(
                overlay,
                immediate=immediate,
            ),
            record_elapsed=self._record_preview_sync_elapsed(overlay),
        )

    def flush_pending_reorder_preview_sync(
        self,
        *,
        reason: str | None = None,
        forced: bool = False,
    ) -> None:
        """Apply the latest pending reorder preview sync immediately."""

        overlay = self._segment_overlay
        self._preview_sync.flush_pending(
            reason=reason,
            forced=forced,
            context=self._preview_sync_context(overlay),
            record_elapsed=self._record_preview_sync_elapsed(overlay),
        )

    def close_reorder_preview(self, *, reason: str) -> None:
        """Stop preview scheduling and clear projection preview cache/state."""

        self._preview_sync.clear()
        self._preview_projection_provider.clear_cache(reason=reason)

    def clear_reorder_preview_cache(self, *, reason: str) -> None:
        """Invalidate projection-owned reorder preview snapshots."""

        self._preview_projection_provider.clear_cache(reason=reason)

    def _sync_reorder_preview_from_overlay(self) -> None:
        """Build and apply the current reorder preview state from the overlay."""

        started_at = reorder_drag_started_at()
        overlay = self._segment_overlay
        if overlay is None:
            self._editor.clear_reorder_preview_state()
            log_reorder_drag_timing(
                "interaction.sync_preview.no_overlay",
                started_at=started_at,
                reason=self._preview_sync.active_reason,
            )
            return
        gesture_id = self._overlay_instrumentation_gesture_id(overlay)
        event_id = self._overlay_instrumentation_event_id(overlay)
        overlay.flush_pending_autoscroll_invalidation(
            reason="autoscroll_coalesced_preview_sync"
        )
        preview_layout_view = overlay.preview_layout_view()
        base_drag_layout_view = overlay.base_drag_layout_view()
        if preview_layout_view is None:
            self._sync_base_drag_only_preview(
                overlay,
                base_drag_layout_view=base_drag_layout_view,
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
            )
            return
        self._sync_active_preview(
            overlay,
            preview_layout_view=preview_layout_view,
            base_drag_layout_view=base_drag_layout_view,
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
        )

    def _sync_base_drag_only_preview(
        self,
        overlay: PromptReorderOverlayPort,
        *,
        base_drag_layout_view: PromptReorderLayoutView | None,
        started_at: float,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Sync the base-drag preview used before a target preview exists."""

        ordered_chip_indices = overlay.commit_snapshot().ordered_chip_indices
        if base_drag_layout_view is None:
            overlay.set_preview_snapshot(
                None,
                base_drag_snapshot=None,
                ordered_chip_indices=ordered_chip_indices,
            )
            self._editor.clear_reorder_preview_state()
            log_reorder_drag_timing(
                "interaction.sync_preview.clear",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                reason=self._preview_sync.active_reason,
                ordered_count=len(ordered_chip_indices),
            )
            return

        current_layout_view = self._document_service.build_reorder_layout_view(
            self._host.current_reorder_document_view()
        )
        current_result = self._build_reorder_preview_projection_result(
            current_layout_view,
            cache_namespace="current",
            layout_key=layout_view_key(current_layout_view),
            active_drop_target_identity=None,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        base_drag_result = self._build_reorder_preview_projection_result(
            base_drag_layout_view,
            reorder_state=overlay.base_drag_reorder_state(),
            cache_namespace="base_drag",
            layout_key=layout_view_key(base_drag_layout_view),
            active_drop_target_identity=None,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        assert current_result is not None
        assert base_drag_result is not None
        self._editor.set_reorder_preview_state(
            PromptReorderPreviewState(
                preview_snapshot=current_result.projection_snapshot,
                base_drag_snapshot=base_drag_result.projection_snapshot,
                ordered_chip_indices=ordered_chip_indices,
                dragged_chip_index=None,
                preview_layout_key=layout_view_key(current_layout_view),
                base_drag_layout_key=layout_view_key(base_drag_layout_view),
                active_drop_target_identity=None,
                instrumentation_gesture_id=gesture_id,
                instrumentation_event_id=event_id,
                instrumentation_reason=self._preview_sync.active_reason or "",
            )
        )
        overlay.set_preview_snapshot(
            None,
            base_drag_snapshot=base_drag_result.preview_snapshot,
            ordered_chip_indices=ordered_chip_indices,
        )
        log_reorder_drag_timing(
            "interaction.sync_preview.base_drag_only_total",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=self._preview_sync.active_reason,
            ordered_count=len(ordered_chip_indices),
        )

    def _sync_active_preview(
        self,
        overlay: PromptReorderOverlayPort,
        *,
        preview_layout_view: PromptReorderLayoutView,
        base_drag_layout_view: PromptReorderLayoutView | None,
        started_at: float,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Sync an active drop-target preview plus optional base-drag state."""

        phase_started_at = reorder_drag_started_at()
        active_drop_target_identity = self._active_drop_target_identity(
            self._overlay_drop_target(overlay)
        )
        preview_result = self._build_reorder_preview_projection_result(
            preview_layout_view,
            reorder_state=overlay.preview_reorder_state(),
            cache_namespace="preview",
            layout_key=layout_view_key(preview_layout_view),
            active_drop_target_identity=active_drop_target_identity,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        preview_elapsed_ms = log_reorder_drag_timing(
            "interaction.sync_preview.preview_projection_snapshot",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=self._preview_sync.active_reason,
            row_count=len(preview_layout_view.rows),
            gap_count=len(preview_layout_view.gaps),
            dragged_segment_index=overlay.dragged_segment_index(),
            target_kind=reorder_drag_target_kind(self._overlay_drop_target(overlay)),
        )
        phase_started_at = reorder_drag_started_at()
        base_drag_result = self._build_reorder_preview_projection_result(
            base_drag_layout_view,
            reorder_state=overlay.base_drag_reorder_state(),
            cache_namespace="base_drag",
            layout_key=layout_view_key(base_drag_layout_view),
            active_drop_target_identity=None,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        base_elapsed_ms = log_reorder_drag_timing(
            "interaction.sync_preview.base_drag_projection_snapshot",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=self._preview_sync.active_reason,
            row_count=0
            if base_drag_layout_view is None
            else len(base_drag_layout_view.rows),
            gap_count=0
            if base_drag_layout_view is None
            else len(base_drag_layout_view.gaps),
        )
        assert preview_result is not None
        ordered_chip_indices = overlay.commit_snapshot().ordered_chip_indices
        self._editor.set_reorder_preview_state(
            PromptReorderPreviewState(
                preview_snapshot=preview_result.projection_snapshot,
                base_drag_snapshot=(
                    None
                    if base_drag_result is None
                    else base_drag_result.projection_snapshot
                ),
                ordered_chip_indices=ordered_chip_indices,
                dragged_chip_index=overlay.dragged_segment_index(),
                preview_layout_key=layout_view_key(preview_layout_view),
                base_drag_layout_key=layout_view_key(base_drag_layout_view),
                active_drop_target_identity=active_drop_target_identity,
                instrumentation_gesture_id=gesture_id,
                instrumentation_event_id=event_id,
                instrumentation_reason=self._preview_sync.active_reason or "",
            )
        )
        overlay.set_preview_snapshot(
            preview_result.preview_snapshot,
            base_drag_snapshot=(
                None if base_drag_result is None else base_drag_result.preview_snapshot
            ),
            ordered_chip_indices=ordered_chip_indices,
        )
        log_reorder_drag_timing(
            "interaction.sync_preview.total",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=self._preview_sync.active_reason,
            ordered_count=len(ordered_chip_indices),
            dragged_segment_index=overlay.dragged_segment_index(),
            target_kind=reorder_drag_target_kind(self._overlay_drop_target(overlay)),
            preview_elapsed_ms=f"{preview_elapsed_ms:.3f}",
            base_elapsed_ms=f"{base_elapsed_ms:.3f}",
        )

    def _build_reorder_preview_projection_result(
        self,
        layout_view: PromptReorderLayoutView | None,
        *,
        reorder_state: PromptReorderStateView | None = None,
        cache_namespace: str,
        layout_key: Hashable | None,
        active_drop_target_identity: Hashable | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderPreviewProjectionResult | None:
        """Build one display-only preview result through the projection service."""

        overlay = self._segment_overlay
        record_render_plan_elapsed: Callable[[float], object] | None = None
        if overlay is not None:
            method = getattr(overlay, "record_render_plan_elapsed", None)
            if callable(method):
                record_render_plan_elapsed = cast(Callable[[float], object], method)
        return self._preview_projection_provider.build_projection_snapshot(
            document_view=self._host.current_reorder_document_view(),
            layout_view=layout_view,
            reorder_state=reorder_state,
            cache_namespace=cache_namespace,
            source_revision=self._current_source_revision() or 0,
            viewport_width=self._current_preview_viewport_width(),
            scroll_position=self._current_preview_scroll_position(),
            layout_key=layout_key,
            active_drop_target_identity=active_drop_target_identity,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=self._preview_sync.active_reason,
            record_render_plan_elapsed=record_render_plan_elapsed,
        )

    def _current_preview_viewport_width(self) -> int:
        """Return viewport width used by projection-owned preview cache keys."""

        viewport_method = getattr(self._editor, "viewport", None)
        if not callable(viewport_method):
            return 0
        viewport = cast(Callable[[], object], viewport_method)()
        width_method = getattr(viewport, "width", None)
        if not callable(width_method):
            return 0
        width = cast(Callable[[], object], width_method)()
        return width if isinstance(width, int) else 0

    def _current_preview_scroll_position(self) -> int:
        """Return scroll position used by projection-owned preview cache keys."""

        scrollbar_method = getattr(self._editor, "verticalScrollBar", None)
        if not callable(scrollbar_method):
            return 0
        scrollbar = cast(Callable[[], object], scrollbar_method)()
        value_method = getattr(scrollbar, "value", None)
        if not callable(value_method):
            return 0
        value = cast(Callable[[], object], value_method)()
        return value if isinstance(value, int) else 0

    def _preview_sync_context(
        self,
        overlay: PromptReorderOverlayPort | None,
    ) -> PromptReorderPreviewSyncContext:
        """Build the overlay-derived context consumed by preview-sync scheduling."""

        dragged_segment_index = None
        base_drag_layout_ready = False
        if overlay is not None:
            dragged_segment_index = overlay.dragged_segment_index()
            base_drag_layout_ready = overlay.base_drag_layout_view() is not None
        return PromptReorderPreviewSyncContext(
            gesture_id=self._overlay_instrumentation_gesture_id(overlay),
            event_id=self._overlay_instrumentation_event_id(overlay),
            pointer_active=self._overlay_pointer_loop_active(overlay),
            dragged_segment_index=dragged_segment_index,
            base_drag_layout_ready=base_drag_layout_ready,
            requires_immediate_drag_geometry=(
                self._preview_sync_requires_immediate_drag_geometry()
            ),
            requires_initial_landing_shadow=(
                self._preview_sync_requires_initial_landing_shadow(overlay)
            ),
        )

    @staticmethod
    def _record_preview_sync_elapsed(
        overlay: object | None,
    ) -> Callable[[float], None] | None:
        """Return the overlay elapsed-time counter hook when one is exposed."""

        method = getattr(overlay, "record_preview_sync_elapsed", None)
        if not callable(method):
            return None
        return cast(Callable[[float], None], method)

    def _preview_sync_requires_immediate_drag_geometry(self) -> bool:
        """Return whether drag hit testing is blocked on base-drag geometry."""

        overlay = self._segment_overlay
        if overlay is None:
            return False
        dragged_segment_index = getattr(overlay, "dragged_segment_index", None)
        base_drag_layout_view = getattr(overlay, "base_drag_layout_view", None)
        if (
            not callable(dragged_segment_index)
            or not callable(base_drag_layout_view)
            or dragged_segment_index() is None
            or base_drag_layout_view() is None
        ):
            return False
        has_geometry = getattr(overlay, "has_base_drag_placement_geometry", None)
        if not callable(has_geometry):
            return True
        return not bool(cast(Callable[[], object], has_geometry)())

    def _preview_sync_requires_initial_landing_shadow(
        self,
        overlay: object | None,
    ) -> bool:
        """Return whether one bounded first-shadow sync should run immediately."""

        if overlay is None:
            return False
        dragged_segment_index = getattr(overlay, "dragged_segment_index", None)
        base_drag_layout_view = getattr(overlay, "base_drag_layout_view", None)
        if (
            not callable(dragged_segment_index)
            or not callable(base_drag_layout_view)
            or dragged_segment_index() is None
            or base_drag_layout_view() is None
        ):
            return False
        should_flush = getattr(
            overlay,
            "should_flush_initial_landing_shadow_sync",
            None,
        )
        if not callable(should_flush):
            return False
        return bool(cast(Callable[[], object], should_flush)())

    def _record_preview_sync_decision(
        self,
        overlay: object | None,
        *,
        immediate: bool,
    ) -> None:
        """Record preview-sync scheduling decisions when overlays expose counters."""

        method = getattr(overlay, "record_preview_sync_decision", None)
        if not callable(method):
            return
        cast(Callable[..., object], method)(immediate=immediate)

    def _current_pointer_work_unit_id(self) -> int | None:
        """Return the active overlay work-unit id used by preview scheduling."""

        overlay = self._segment_overlay
        if overlay is None:
            return None
        method = getattr(overlay, "current_instrumentation_work_unit_id", None)
        if not callable(method):
            return None
        return cast(int | None, method())

    def _record_preview_scheduler_event(self, event: str) -> None:
        """Record scheduler event classifications on the active overlay."""

        overlay = self._segment_overlay
        if overlay is None:
            return
        method = getattr(overlay, "record_preview_scheduler_event", None)
        if not callable(method):
            return
        cast(Callable[[str], object], method)(event)

    @staticmethod
    def _overlay_instrumentation_gesture_id(
        overlay: object | None,
    ) -> int | None:
        """Return a safe diagnostics gesture id from real overlays or test doubles."""

        method = getattr(overlay, "instrumentation_gesture_id", None)
        if not callable(method):
            return None
        value = cast(Callable[[], object], method)()
        return value if isinstance(value, int) else None

    @staticmethod
    def _overlay_instrumentation_event_id(
        overlay: object | None,
    ) -> int | None:
        """Return a safe diagnostics event id from real overlays or test doubles."""

        method = getattr(overlay, "instrumentation_event_id", None)
        if not callable(method):
            return None
        value = cast(Callable[[], object], method)()
        return value if isinstance(value, int) else None

    @staticmethod
    def _overlay_drop_target(overlay: object | None) -> object | None:
        """Return the active diagnostics drop target when the overlay exposes it."""

        method = getattr(overlay, "drop_target", None)
        if not callable(method):
            return None
        return cast(Callable[[], object | None], method)()

    @staticmethod
    def _active_drop_target_identity(target: object | None) -> Hashable | None:
        """Return a prompt-safe cache identity for one active reorder target."""

        if isinstance(target, PromptLineDropTarget):
            return ("line", target.row_index, target.insertion_index)
        if isinstance(target, PromptGapBlankLineDropTarget):
            return ("gap", target.gap_index, target.blank_line_index)
        if isinstance(target, Hashable):
            return target
        return None

    @staticmethod
    def _overlay_pointer_loop_active(overlay: object | None) -> bool:
        """Return whether the overlay is currently processing a pointer event."""

        method = getattr(overlay, "is_drag_pointer_loop_active", None)
        if not callable(method):
            return False
        return bool(cast(Callable[[], object], method)())

    def _show_segment_overlay(self) -> None:
        """Create and display the transient chip overlay used for segment reordering."""

        total_started_at = reorder_drag_started_at()
        if not self._host.segment_reorder_enabled():
            log_reorder_drag_timing(
                "interaction.show_segment_overlay.noop",
                started_at=total_started_at,
                reason="feature_disabled",
            )
            return
        if self._segment_overlay is not None:
            log_reorder_drag_timing(
                "interaction.show_segment_overlay.noop",
                started_at=total_started_at,
                reason="already_visible",
            )
            return

        document_view = self._host.current_reorder_document_view()
        phase_started_at = reorder_drag_started_at()
        reorder_session_view: PromptReorderSessionView = (
            self._document_service.build_reorder_session_view(document_view)
        )
        session_view_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.session_view",
            started_at=phase_started_at,
            chip_count=len(reorder_session_view.chips),
            row_count=len(reorder_session_view.layout_view.rows),
            gap_count=len(reorder_session_view.layout_view.gaps),
            text_length=len(document_view.source_text),
        )
        chips = reorder_session_view.chips
        if not chips:
            log_reorder_drag_timing(
                "interaction.show_segment_overlay.noop",
                started_at=total_started_at,
                reason="no_chips",
                session_view_elapsed_ms=f"{session_view_elapsed_ms:.3f}",
            )
            return
        reorder_layout_view = reorder_session_view.layout_view

        phase_started_at = reorder_drag_started_at()
        self._host.clear_transient_state_for_reorder()
        clear_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.clear_transient_state",
            started_at=phase_started_at,
        )
        active_segment_index = self._active_segment_index_for_reorder()
        selection_start, selection_end = self._segment_reorder_selection_bounds()
        (
            selection_start_offset_within_active_chip,
            selection_end_offset_within_active_chip,
        ) = self._segment_reorder_selection_offsets_within_active_chip(
            active_segment_index
        )
        ordered_indices = tuple(chip.index for chip in chips)
        self._session_controller.start(
            layout_view=reorder_layout_view,
            reorder_state=reorder_session_view.reorder_state,
            ordered_indices=ordered_indices,
            active_segment_index=active_segment_index,
            selection_start=selection_start,
            selection_end=selection_end,
            selection_start_offset_within_active_chip=selection_start_offset_within_active_chip,
            selection_end_offset_within_active_chip=selection_end_offset_within_active_chip,
        )
        self._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER
        self.reset_reorder_preview(reason="overlay_show")

        phase_started_at = reorder_drag_started_at()
        editor_widget = cast(QWidget, self._editor)
        self._segment_overlay = cast(
            PromptReorderOverlayPort,
            self._overlay_factory.create_segment_overlay(
                editor_widget,
                layout_policy=self._document_service,
            ),
        )
        overlay_init_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.overlay_init",
            started_at=phase_started_at,
        )
        self._segment_overlay.set_drag_handler(self._handle_reorder_drag_intent)
        self._segment_overlay.set_commit_handler(self._handle_overlay_commit_intent)
        self._segment_overlay.set_cancel_handler(self.handle_reorder_cancel_intent)
        self._segment_overlay.previewLayoutChanged.connect(
            lambda: self.schedule_reorder_preview_sync(reason="overlay_preview_changed")
        )
        phase_started_at = reorder_drag_started_at()
        self._segment_overlay.set_chips(
            document_view,
            reorder_layout_view,
            reorder_state=reorder_session_view.reorder_state,
            chips=chips,
            active_chip_index=active_segment_index,
            source_revision=self._current_source_revision(),
        )
        set_chips_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.set_chips",
            started_at=phase_started_at,
            chip_count=len(chips),
            row_count=len(reorder_layout_view.rows),
            gap_count=len(reorder_layout_view.gaps),
        )
        phase_started_at = reorder_drag_started_at()
        self._position_segment_overlay()
        self._segment_overlay.show()
        self._editor.setFocus()
        show_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.show",
            started_at=phase_started_at,
        )
        log_reorder_drag_timing(
            "interaction.show_segment_overlay.total",
            started_at=total_started_at,
            chip_count=len(chips),
            row_count=len(reorder_layout_view.rows),
            gap_count=len(reorder_layout_view.gaps),
            active_chip_index=active_segment_index,
            session_view_elapsed_ms=f"{session_view_elapsed_ms:.3f}",
            clear_elapsed_ms=f"{clear_elapsed_ms:.3f}",
            overlay_init_elapsed_ms=f"{overlay_init_elapsed_ms:.3f}",
            set_chips_elapsed_ms=f"{set_chips_elapsed_ms:.3f}",
            show_elapsed_ms=f"{show_elapsed_ms:.3f}",
        )

    def _current_source_revision(self) -> int | None:
        """Return the source revision used to invalidate drag-proxy rendering."""

        source_identity = self._editor.prompt_command_source_identity()
        return None if source_identity is None else source_identity.source_revision

    def _position_segment_overlay(self) -> None:
        """Align the segment overlay with the visible editor viewport."""

        if self._segment_overlay is None:
            return
        needs_position_refresh = getattr(
            self._segment_overlay,
            "needs_position_refresh",
            None,
        )
        if callable(needs_position_refresh) and not bool(
            cast(Callable[..., object], needs_position_refresh)(
                reason="interaction_position_overlay"
            )
        ):
            return
        self._segment_overlay.refresh_geometry(reason="interaction_position_overlay")

    def _active_segment_index_for_reorder(self) -> int | None:
        """Resolve the segment that should stay active through one reorder session."""

        cursor = self._editor.textCursor()
        candidate_positions: list[int]
        if cursor.selection().isEmpty():
            candidate_positions = [cursor.position()]
        else:
            selection_start = cursor.selectionStart()
            selection_end = max(selection_start, cursor.selectionEnd() - 1)
            candidate_positions = [selection_start, selection_end]

        document_view = self._host.current_reorder_document_view()
        chips = self._document_service.reorder_chips(document_view)
        for position in candidate_positions:
            chip = self._document_service.reorder_chip_at_position(
                document_view,
                position,
            )
            if chip is not None:
                return chip.index
        for position in candidate_positions:
            chip = self._nearest_preceding_reorder_chip(
                chips=chips,
                position=position,
            )
            if chip is not None:
                return chip.index
        return None

    @staticmethod
    def _nearest_preceding_reorder_chip(
        *,
        chips: tuple[PromptReorderChipView, ...],
        position: int,
    ) -> PromptReorderChipView | None:
        """Return the chip before a separator or line-end cursor boundary."""

        preceding_chips = [chip for chip in chips if chip.selection_end <= position]
        if not preceding_chips:
            return None
        return max(preceding_chips, key=lambda chip: chip.selection_end)

    def _segment_reorder_selection_bounds(self) -> tuple[int, int]:
        """Capture the current cursor or selection bounds before reorder mode starts."""

        cursor = self._editor.textCursor()
        if cursor.selection().isEmpty():
            position = cursor.position()
            return position, position
        return cursor.selectionStart(), cursor.selectionEnd()

    def _segment_reorder_selection_offsets_within_active_chip(
        self,
        active_segment_index: int | None,
    ) -> tuple[int | None, int | None]:
        """Capture selection offsets relative to the active chip when self-contained."""

        if active_segment_index is None:
            return None, None

        active_chip = self._reorder_chip_by_index(active_segment_index)
        if active_chip is None:
            return None, None

        cursor = self._editor.textCursor()
        selection_start = cursor.selectionStart()
        selection_end = cursor.selectionEnd()
        if not (
            self._position_within_reorder_chip(selection_start, active_chip)
            and self._position_within_reorder_chip(selection_end, active_chip)
        ):
            return None, None

        chip_start = active_chip.selection_start
        return selection_start - chip_start, selection_end - chip_start

    def _reorder_chip_by_index(
        self,
        chip_index: int,
    ) -> PromptReorderChipView | None:
        """Return the cached reorder chip matching one active chip index."""

        document_view = self._host.current_reorder_document_view()
        for chip in self._document_service.reorder_chips(document_view):
            if chip.index == chip_index:
                return chip
        return None

    @staticmethod
    def _position_within_reorder_chip(
        position: int,
        chip: PromptReorderChipView,
    ) -> bool:
        """Return whether one cursor boundary belongs to the supplied chip range."""

        return chip.selection_start <= position <= chip.selection_end

    def _handle_reorder_drag_intent(self, intent: PromptReorderDragIntent) -> None:
        """Consume pointer drag intent without taking over overlay rendering."""

        log_reorder_drag_event(
            "interaction.drag_intent",
            phase=intent.phase,
            segment_index=intent.segment_index,
            global_x=intent.global_position.x(),
            global_y=intent.global_position.y(),
        )

    def _handle_overlay_commit_intent(self, intent: PromptReorderCommitIntent) -> None:
        """Consume overlay drop commits as prepared interaction state only."""

        if intent.snapshot is not None:
            self._session_controller.capture_snapshot(intent.snapshot)
        log_reorder_drag_event(
            "interaction.overlay_commit_intent",
            reason=intent.reason,
            has_snapshot=intent.snapshot is not None,
            has_reordered=(
                False if intent.snapshot is None else intent.snapshot.has_reordered
            ),
        )

    def _sync_segment_reorder_session_from_overlay_snapshot(self) -> None:
        """Capture the latest overlay snapshot into the typed session model."""

        overlay = self._segment_overlay
        if overlay is None:
            return
        self._session_controller.capture_snapshot(overlay.commit_snapshot())

    def _cancel_segment_overlay(
        self,
        *,
        restore_selection: bool = True,
        reason: str = "cancel",
    ) -> None:
        """Close reorder mode without mutating text."""

        overlay = self._segment_overlay
        if overlay is None:
            return

        overlay.cancel_drag()
        self._sync_segment_reorder_session_from_overlay_snapshot()
        log_reorder_drag_event(
            "interaction.cancel_segment_overlay",
            reason=reason,
            restore_selection=restore_selection,
        )
        self._close_segment_overlay(restore_selection=restore_selection)

    def _close_segment_overlay(self, *, restore_selection: bool) -> None:
        """Dispose the overlay and return the controller to normal text editing."""

        self.close_reorder_preview(reason="overlay_close")
        overlay = self._segment_overlay
        if overlay is not None:
            self._editor.clear_reorder_preview_state()
            overlay.close()
            overlay.deleteLater()
            self._segment_overlay = None

        if restore_selection:
            self._restore_segment_reorder_selection()

        self._session_controller.reset()
        self._interaction_mode = PromptEditorInteractionMode.TEXT_EDITING

    def _restore_segment_reorder_selection(self) -> None:
        """Restore the cursor or selection captured before reorder mode opened."""

        selection_start = self._session_controller.session.selection_start
        selection_end = self._session_controller.session.selection_end
        if selection_start is None or selection_end is None:
            return

        cursor = self._editor.textCursor()
        self._set_cursor_selection(
            cursor,
            start=selection_start,
            end=selection_end,
        )
        self._editor.setTextCursor(cursor)

    @staticmethod
    def _set_cursor_selection(
        cursor: PromptReorderCursor,
        *,
        start: int,
        end: int,
    ) -> None:
        """Select one half-open source range on the supplied cursor."""

        cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)


__all__ = [
    "PromptReorderController",
    "PromptReorderCursor",
    "PromptReorderEditorHost",
    "PromptReorderHost",
    "PromptReorderOverlayFactory",
    "PromptReorderOverlayPort",
]
