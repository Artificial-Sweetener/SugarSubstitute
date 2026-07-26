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

"""Prepare complete reorder-session transitions without presentation dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.selection import (
    PromptReorderSelectionCapturePolicy,
    PromptReorderSelectionCapture,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCloseTransition,
    PromptReorderCommitPlan,
    PromptReorderCommitSnapshot,
    PromptReorderSessionOwner,
    PromptReorderSessionState,
)
from substitute.application.prompt_editor.reorder.views import PromptReorderSessionView


@dataclass(frozen=True, slots=True)
class PromptReorderEntryRequest:
    """Describe source and cursor facts required to start one reorder session."""

    document_view: PromptDocumentView
    cursor_position: int
    selection_start: int
    selection_end: int
    selection_empty: bool


@dataclass(frozen=True, slots=True)
class PromptReorderEntryPlan:
    """Carry the immutable document and selection facts for overlay publication."""

    session_view: PromptReorderSessionView
    selection: PromptReorderSelectionCapture


class PromptReorderLifecycleOwner:
    """Own entry, snapshot, commit, and close transitions for one reorder session."""

    def __init__(self, document_service: PromptDocumentService) -> None:
        """Initialize the application services and inactive session truth."""

        self._document_service = document_service
        self._selection_capture = PromptReorderSelectionCapturePolicy()
        self._session_owner = PromptReorderSessionOwner()

    @property
    def session_state(self) -> PromptReorderSessionState:
        """Return immutable session truth for presentation and diagnostics."""

        return self._session_owner.state

    @property
    def latest_commit_snapshot(self) -> PromptReorderCommitSnapshot | None:
        """Return the latest snapshot accepted by the session transition owner."""

        return self._session_owner.latest_commit_snapshot

    def prepare_entry(
        self,
        request: PromptReorderEntryRequest,
    ) -> PromptReorderEntryPlan | None:
        """Build and start a session only when the source contains reorderable chips."""

        session_view = self._document_service.build_reorder_session_view(
            request.document_view
        )
        chips = session_view.chips
        if not chips:
            return None
        selection = self._selection_capture.capture(
            chips,
            cursor_position=request.cursor_position,
            selection_start=request.selection_start,
            selection_end=request.selection_end,
            selection_empty=request.selection_empty,
        )
        return PromptReorderEntryPlan(session_view=session_view, selection=selection)

    def start(self, entry_plan: PromptReorderEntryPlan) -> None:
        """Start session truth after presentation has accepted reorder entry."""

        session_view = entry_plan.session_view
        selection = entry_plan.selection
        ordered_indices = tuple(chip.index for chip in session_view.chips)
        self._session_owner.start(
            layout_view=session_view.layout_view,
            reorder_state=session_view.reorder_state,
            ordered_indices=ordered_indices,
            active_segment_index=selection.active_segment_index,
            selection_start=selection.selection_start,
            selection_end=selection.selection_end,
            selection_start_offset_within_active_chip=(
                selection.selection_start_offset_within_active_chip
            ),
            selection_end_offset_within_active_chip=(
                selection.selection_end_offset_within_active_chip
            ),
        )

    def capture_snapshot(self, snapshot: PromptReorderCommitSnapshot) -> None:
        """Accept one overlay-produced snapshot as authoritative commit truth."""

        self._session_owner.capture_snapshot(snapshot)

    def resolve_commit(
        self,
        snapshot: PromptReorderCommitSnapshot,
        *,
        source_revision: int | None,
        source_length: int | None,
    ) -> PromptReorderCommitPlan:
        """Resolve source mutation eligibility and atomically close the session."""

        return self._session_owner.finish_commit(
            snapshot,
            source_revision=source_revision,
            source_length=source_length,
        )

    def prepare_cancel(
        self,
        snapshot: PromptReorderCommitSnapshot,
        *,
        restore_selection: bool,
    ) -> PromptReorderCloseTransition:
        """Capture final overlay truth and close without preparing source mutation."""

        self._session_owner.capture_snapshot(snapshot)
        return self._session_owner.close(restore_selection=restore_selection)

    def replace_state(self, state: PromptReorderSessionState) -> None:
        """Restore an explicitly prepared session state at a lifecycle boundary."""

        self._session_owner.replace_state(state)


__all__ = [
    "PromptReorderEntryPlan",
    "PromptReorderEntryRequest",
    "PromptReorderLifecycleOwner",
]
