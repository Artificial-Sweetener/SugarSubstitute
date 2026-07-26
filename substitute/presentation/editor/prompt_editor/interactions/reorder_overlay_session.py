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

"""Own one Qt reorder-overlay session over application reorder lifecycle policy."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from substitute.application.prompt_editor.reorder.lifecycle import (
    PromptReorderEntryRequest,
    PromptReorderLifecycleOwner,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCloseTransition,
    PromptReorderCommitSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..models import PromptEditorInteractionMode
from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_cursor_selection import (
    PromptReorderCursor,
    PromptReorderCursorSelectionAdapter,
    PromptReorderCursorSurface,
)
from .reorder_overlay_port import (
    PromptReorderDragIntent,
    PromptReorderOverlayFactory,
    PromptReorderOverlayPort,
)
from .reorder_preview_publication import PromptReorderPreviewPublicationOwner


class PromptReorderOverlaySessionEditor(
    PromptReorderCursorSurface,
    Protocol,
):
    """Expose the narrow Qt editor boundary used by one reorder overlay session."""

    def textCursor(self) -> PromptReorderCursor:
        """Return the editor cursor used to prepare one reorder entry request."""

    def prompt_command_source_identity(self) -> PromptSourceIdentity | None:
        """Return the source identity attached to overlay chip facts."""

    def setFocus(self) -> None:
        """Restore focus after the overlay receives its prepared chip facts."""


class PromptReorderOverlaySessionHost(Protocol):
    """Expose non-Qt entry facts and transient cleanup for one overlay session."""

    def current_reorder_document_view(self) -> PromptDocumentView:
        """Return the immutable prompt document used to prepare reorder chips."""

    def segment_reorder_enabled(self) -> bool:
        """Return whether the active prompt field supports segment reordering."""

    def clear_transient_state_for_reorder(self) -> None:
        """Clear competing transient UI before a reorder session becomes active."""


class PromptReorderOverlaySessionOwner:
    """Own overlay construction, binding, interaction state, and Qt teardown."""

    def __init__(
        self,
        editor: PromptReorderOverlaySessionEditor,
        *,
        host: PromptReorderOverlaySessionHost,
        document_service: PromptDocumentService,
        lifecycle: PromptReorderLifecycleOwner,
        preview_publication: PromptReorderPreviewPublicationOwner,
        overlay_factory: PromptReorderOverlayFactory,
    ) -> None:
        """Store focused session collaborators without taking source-command ownership."""

        self._editor = editor
        self._host = host
        self._document_service = document_service
        self._lifecycle = lifecycle
        self._preview_publication = preview_publication
        self._overlay_factory = overlay_factory
        self._cursor_selection = PromptReorderCursorSelectionAdapter()
        self._overlay: PromptReorderOverlayPort | None = None
        self._interaction_mode = PromptEditorInteractionMode.TEXT_EDITING

    @property
    def overlay(self) -> PromptReorderOverlayPort | None:
        """Return the live overlay owned by this presentation session."""

        return self._overlay

    @property
    def interaction_mode(self) -> PromptEditorInteractionMode:
        """Return the interaction mode controlled by this overlay session."""

        return self._interaction_mode

    def enter(self) -> None:
        """Create and bind one overlay only when entry policy approves it."""

        total_started_at = reorder_drag_started_at()
        if not self._host.segment_reorder_enabled():
            log_reorder_drag_timing(
                "interaction.show_segment_overlay.noop",
                started_at=total_started_at,
                reason="feature_disabled",
            )
            return
        if self._overlay is not None:
            log_reorder_drag_timing(
                "interaction.show_segment_overlay.noop",
                started_at=total_started_at,
                reason="already_visible",
            )
            return

        document_view = self._host.current_reorder_document_view()
        cursor = self._editor.textCursor()
        phase_started_at = reorder_drag_started_at()
        entry_plan = self._lifecycle.prepare_entry(
            PromptReorderEntryRequest(
                document_view=document_view,
                cursor_position=cursor.position(),
                selection_start=cursor.selectionStart(),
                selection_end=cursor.selectionEnd(),
                selection_empty=cursor.selection().isEmpty(),
            )
        )
        session_view_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.session_view",
            started_at=phase_started_at,
            chip_count=0 if entry_plan is None else len(entry_plan.session_view.chips),
            row_count=(
                0
                if entry_plan is None
                else len(entry_plan.session_view.layout_view.rows)
            ),
            gap_count=(
                0
                if entry_plan is None
                else len(entry_plan.session_view.layout_view.gaps)
            ),
            text_length=len(document_view.source_text),
        )
        if entry_plan is None:
            log_reorder_drag_timing(
                "interaction.show_segment_overlay.noop",
                started_at=total_started_at,
                reason="no_chips",
                session_view_elapsed_ms=f"{session_view_elapsed_ms:.3f}",
            )
            return

        phase_started_at = reorder_drag_started_at()
        self._host.clear_transient_state_for_reorder()
        clear_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.clear_transient_state",
            started_at=phase_started_at,
        )
        self._lifecycle.start(entry_plan)
        self._interaction_mode = PromptEditorInteractionMode.SEGMENT_REORDER
        self._preview_publication.reset(reason="overlay_show")

        phase_started_at = reorder_drag_started_at()
        assembly = self._overlay_factory.create_segment_overlay(
            cast(QWidget, self._editor),
            layout_policy=self._document_service,
        )
        overlay = assembly.overlay
        self._overlay = overlay
        self._preview_publication.bind_session(
            overlay=overlay,
            build_facts=assembly.preview_build_facts,
            sync_context=assembly.preview_sync_context,
        )
        overlay_init_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.overlay_init",
            started_at=phase_started_at,
        )
        overlay.set_drag_handler(self._handle_drag_intent)
        overlay.set_commit_handler(self._handle_commit_intent)
        overlay.set_cancel_handler(self._handle_cancel_intent)
        assembly.preview_layout_changed.connect(self._schedule_preview)

        phase_started_at = reorder_drag_started_at()
        overlay.show()
        overlay_prepare_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.prepare",
            started_at=phase_started_at,
        )
        reorder_session_view = entry_plan.session_view
        phase_started_at = reorder_drag_started_at()
        overlay.set_chips(
            document_view,
            reorder_session_view.layout_view,
            reorder_session_view.reorder_state,
            chips=reorder_session_view.chips,
            active_chip_index=entry_plan.selection.active_segment_index,
            source_identity=self._editor.prompt_command_source_identity(),
        )
        set_chips_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.set_chips",
            started_at=phase_started_at,
            chip_count=len(reorder_session_view.chips),
            row_count=len(reorder_session_view.layout_view.rows),
            gap_count=len(reorder_session_view.layout_view.gaps),
        )
        phase_started_at = reorder_drag_started_at()
        self._editor.setFocus()
        show_elapsed_ms = log_reorder_drag_timing(
            "interaction.show_segment_overlay.show",
            started_at=phase_started_at,
        )
        log_reorder_drag_timing(
            "interaction.show_segment_overlay.total",
            started_at=total_started_at,
            chip_count=len(reorder_session_view.chips),
            row_count=len(reorder_session_view.layout_view.rows),
            gap_count=len(reorder_session_view.layout_view.gaps),
            active_chip_index=entry_plan.selection.active_segment_index,
            session_view_elapsed_ms=f"{session_view_elapsed_ms:.3f}",
            clear_elapsed_ms=f"{clear_elapsed_ms:.3f}",
            overlay_init_elapsed_ms=f"{overlay_init_elapsed_ms:.3f}",
            overlay_prepare_elapsed_ms=f"{overlay_prepare_elapsed_ms:.3f}",
            set_chips_elapsed_ms=f"{set_chips_elapsed_ms:.3f}",
            show_elapsed_ms=f"{show_elapsed_ms:.3f}",
        )

    def cancel(self, intent: PromptReorderCancelIntent) -> None:
        """Cancel one active overlay and apply its application close transition."""

        overlay = self._overlay
        if overlay is None:
            return
        overlay.cancel_drag()
        close_transition = self._lifecycle.prepare_cancel(
            overlay.commit_snapshot(),
            restore_selection=intent.restore_selection,
        )
        log_reorder_drag_event(
            "interaction.cancel_segment_overlay",
            reason=intent.reason,
            restore_selection=intent.restore_selection,
        )
        self.close(close_transition)

    def close(self, transition: PromptReorderCloseTransition) -> None:
        """Release one active session in paint-safe overlay-before-editor order."""

        self._preview_publication.close(reason="overlay_close")
        overlay = self._overlay
        if overlay is not None:
            overlay.close()
            overlay.deleteLater()
            self._overlay = None
        self._preview_publication.clear_published_state()
        self._preview_publication.unbind_session()
        self._cursor_selection.restore(self._editor, transition)
        self._interaction_mode = PromptEditorInteractionMode.TEXT_EDITING

    def move_keyboard(self, intent: PromptReorderKeyboardMoveIntent) -> None:
        """Apply one keyboard move and flush the resulting display generation."""

        moved = self._move_active_chip(intent)
        if not moved and self._preview_publication.has_pending():
            self._preview_publication.flush(
                reason="keyboard_reorder_prepare",
                forced=True,
            )
            moved = self._move_active_chip(intent)
        if not moved:
            return
        self._capture_overlay_snapshot()
        self._preview_publication.flush(reason="keyboard_reorder_key", forced=True)

    def position(self) -> None:
        """Refresh geometry only when the session's viewport key has changed."""

        overlay = self._overlay
        if overlay is None or self._preview_publication.publishing:
            return
        if not overlay.needs_position_refresh(reason="interaction_position_overlay"):
            return
        overlay.refresh_geometry(reason="interaction_position_overlay")

    def commit_snapshot(self) -> PromptReorderCommitSnapshot | None:
        """Return the current overlay snapshot without changing application state."""

        overlay = self._overlay
        return None if overlay is None else overlay.commit_snapshot()

    def _move_active_chip(self, intent: PromptReorderKeyboardMoveIntent) -> bool:
        """Apply one keyboard request against the active overlay when available."""

        overlay = self._overlay
        return overlay is not None and overlay.move_active_chip(intent)

    def _capture_overlay_snapshot(self) -> None:
        """Capture overlay commit truth before publication can build a preview frame."""

        snapshot = self.commit_snapshot()
        if snapshot is not None:
            self._lifecycle.capture_snapshot(snapshot)

    def _handle_drag_intent(self, intent: PromptReorderDragIntent) -> None:
        """Record a pointer drag intent without taking visual ownership from the overlay."""

        log_reorder_drag_event(
            "interaction.drag_intent",
            phase=intent.phase,
            segment_index=intent.segment_index,
            global_x=intent.global_position.x(),
            global_y=intent.global_position.y(),
        )

    def _handle_commit_intent(self, intent: PromptReorderCommitIntent) -> None:
        """Accept prepared pointer commit truth without mutating prompt source."""

        if intent.snapshot is not None:
            self._lifecycle.capture_snapshot(intent.snapshot)
        log_reorder_drag_event(
            "interaction.overlay_commit_intent",
            reason=intent.reason,
            has_snapshot=intent.snapshot is not None,
            has_reordered=(
                False if intent.snapshot is None else intent.snapshot.has_reordered
            ),
        )

    def _handle_cancel_intent(self, intent: PromptReorderCancelIntent) -> None:
        """Route the overlay's typed cancel intent through its owning session."""

        self.cancel(intent)

    def _schedule_preview(self) -> None:
        """Schedule one latest-wins preview update for the active overlay session."""

        self._preview_publication.schedule(reason="overlay_preview_changed")


__all__ = [
    "PromptReorderOverlaySessionEditor",
    "PromptReorderOverlaySessionHost",
    "PromptReorderOverlaySessionOwner",
]
