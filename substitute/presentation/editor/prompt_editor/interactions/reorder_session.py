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

"""Own prompt segment reorder commit-session state transitions."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptReorderLayoutView,
    PromptReorderStateView,
)

from ..models import PromptReorderCommitSnapshot, SegmentReorderSession


class PromptReorderSessionController:
    """Track authoritative reorder commit state during one Alt-held session.

    The overlay may prepare snapshots for pointer or keyboard movement, but this
    interaction owner decides which snapshot is authoritative for Alt release.
    Preview and animation code must not update this owner directly.
    """

    def __init__(self) -> None:
        """Initialize an empty reorder commit session."""

        self._session = SegmentReorderSession()
        self._latest_commit_snapshot: PromptReorderCommitSnapshot | None = None

    @property
    def session(self) -> SegmentReorderSession:
        """Return the current mutable session view used by controller commands."""

        return self._session

    @property
    def latest_commit_snapshot(self) -> PromptReorderCommitSnapshot | None:
        """Return the latest authoritative snapshot prepared for commit."""

        return self._latest_commit_snapshot

    def start(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        ordered_indices: tuple[int, ...],
        active_segment_index: int | None,
        selection_start: int | None,
        selection_end: int | None,
        selection_start_offset_within_active_chip: int | None,
        selection_end_offset_within_active_chip: int | None,
    ) -> None:
        """Start a reorder session from the document's current chip order."""

        self._session = SegmentReorderSession(
            is_active=True,
            original_ordered_indices=ordered_indices,
            current_ordered_indices=ordered_indices,
            original_reorder_state=reorder_state,
            current_reorder_state=reorder_state,
            active_segment_index=active_segment_index,
            dragged_segment_index=None,
            selection_start=selection_start,
            selection_end=selection_end,
            selection_start_offset_within_active_chip=selection_start_offset_within_active_chip,
            selection_end_offset_within_active_chip=selection_end_offset_within_active_chip,
            has_reordered=False,
        )
        self._latest_commit_snapshot = PromptReorderCommitSnapshot(
            reorder_state=reorder_state,
            layout_view=layout_view,
            ordered_chip_indices=ordered_indices,
            active_segment_index=active_segment_index,
            dragged_segment_index=None,
            has_reordered=False,
        )

    def capture_snapshot(self, snapshot: PromptReorderCommitSnapshot) -> None:
        """Capture one prepared drag or keyboard snapshot as commit truth."""

        self._latest_commit_snapshot = snapshot
        self._session.current_ordered_indices = tuple(snapshot.ordered_chip_indices)
        self._session.current_reorder_state = snapshot.reorder_state
        self._session.active_segment_index = snapshot.active_segment_index
        self._session.dragged_segment_index = snapshot.dragged_segment_index
        self._session.has_reordered = snapshot.has_reordered

    def replace_session(self, session: SegmentReorderSession) -> None:
        """Replace session data from a prepared interaction lifecycle state."""

        self._session = session

    def reset(self) -> None:
        """Clear session and snapshot state after close or cancellation."""

        self._session = SegmentReorderSession()
        self._latest_commit_snapshot = None


__all__ = ["PromptReorderSessionController"]
