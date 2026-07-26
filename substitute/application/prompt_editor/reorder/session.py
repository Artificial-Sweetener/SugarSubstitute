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

"""Own immutable prompt reorder session and commit transitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto

from substitute.application.prompt_editor.reorder.commit import (
    PromptReorderLayoutCommitRequest,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderStateView,
)


@dataclass(frozen=True, slots=True)
class PromptReorderSessionState:
    """Expose one immutable snapshot of the active reorder use case."""

    is_active: bool = False
    original_ordered_indices: tuple[int, ...] = ()
    current_ordered_indices: tuple[int, ...] = ()
    original_reorder_state: PromptReorderStateView | None = None
    current_reorder_state: PromptReorderStateView | None = None
    active_segment_index: int | None = None
    dragged_segment_index: int | None = None
    selection_start: int | None = None
    selection_end: int | None = None
    selection_start_offset_within_active_chip: int | None = None
    selection_end_offset_within_active_chip: int | None = None
    has_reordered: bool = False


@dataclass(frozen=True, slots=True)
class PromptReorderCommitSnapshot:
    """Describe authoritative reordered state prepared for source commit."""

    reorder_state: PromptReorderStateView | None
    layout_view: PromptReorderLayoutView | None
    ordered_chip_indices: tuple[int, ...]
    active_segment_index: int | None
    dragged_segment_index: int | None
    has_reordered: bool


class PromptReorderCommitOutcome(Enum):
    """Classify whether a prepared snapshot can enter source mutation."""

    UNCHANGED = auto()
    MISSING_STATE = auto()
    COMMIT = auto()


@dataclass(frozen=True, slots=True)
class PromptReorderCloseTransition:
    """Carry optional source selection restoration for one finished session."""

    selection_start: int | None
    selection_end: int | None


@dataclass(frozen=True, slots=True)
class PromptReorderCommitPlan:
    """Carry the complete application decision consumed by commit execution."""

    outcome: PromptReorderCommitOutcome
    request: PromptReorderLayoutCommitRequest | None
    close_transition: PromptReorderCloseTransition


class PromptReorderSessionOwner:
    """Own session truth, commit snapshots, and close restoration policy."""

    def __init__(self) -> None:
        """Initialize an inactive immutable session."""

        self._state = PromptReorderSessionState()
        self._latest_commit_snapshot: PromptReorderCommitSnapshot | None = None

    @property
    def state(self) -> PromptReorderSessionState:
        """Return the immutable current session snapshot."""

        return self._state

    @property
    def latest_commit_snapshot(self) -> PromptReorderCommitSnapshot | None:
        """Return the newest snapshot accepted as commit truth."""

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
        """Start a session from one application document projection."""

        self._state = PromptReorderSessionState(
            is_active=True,
            original_ordered_indices=ordered_indices,
            current_ordered_indices=ordered_indices,
            original_reorder_state=reorder_state,
            current_reorder_state=reorder_state,
            active_segment_index=active_segment_index,
            selection_start=selection_start,
            selection_end=selection_end,
            selection_start_offset_within_active_chip=selection_start_offset_within_active_chip,
            selection_end_offset_within_active_chip=selection_end_offset_within_active_chip,
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
        """Adopt one pointer or keyboard snapshot as authoritative truth."""

        self._latest_commit_snapshot = snapshot
        self._state = replace(
            self._state,
            current_ordered_indices=tuple(snapshot.ordered_chip_indices),
            current_reorder_state=snapshot.reorder_state,
            active_segment_index=snapshot.active_segment_index,
            dragged_segment_index=snapshot.dragged_segment_index,
            has_reordered=snapshot.has_reordered,
        )

    def finish_commit(
        self,
        snapshot: PromptReorderCommitSnapshot,
        *,
        source_revision: int | None,
        source_length: int | None,
    ) -> PromptReorderCommitPlan:
        """Resolve one commit and atomically finish its application session."""

        self.capture_snapshot(snapshot)
        state = self._state
        reorder_state = snapshot.reorder_state
        relative_selection_available = (
            state.selection_start_offset_within_active_chip is not None
            and state.selection_end_offset_within_active_chip is not None
        )
        if not snapshot.has_reordered:
            outcome = PromptReorderCommitOutcome.UNCHANGED
        elif reorder_state is None:
            outcome = PromptReorderCommitOutcome.MISSING_STATE
        else:
            outcome = PromptReorderCommitOutcome.COMMIT
        request = None
        if outcome is PromptReorderCommitOutcome.COMMIT:
            if reorder_state is None:
                raise RuntimeError("Commit outcome requires authoritative state.")
            request = PromptReorderLayoutCommitRequest(
                selected_chip_index=state.active_segment_index,
                reorder_state=reorder_state,
                layout_view=snapshot.layout_view,
                source_revision=source_revision,
                source_length=source_length,
                selection_start_offset_within_selected_chip=(
                    state.selection_start_offset_within_active_chip
                    if relative_selection_available
                    else None
                ),
                selection_end_offset_within_selected_chip=(
                    state.selection_end_offset_within_active_chip
                    if relative_selection_available
                    else None
                ),
            )
        plan = PromptReorderCommitPlan(
            outcome=outcome,
            request=request,
            close_transition=self.close(
                restore_selection=not relative_selection_available
            ),
        )
        return plan

    def close(self, *, restore_selection: bool) -> PromptReorderCloseTransition:
        """Finish the session and return its optional selection-restoration effect."""

        state = self._state
        transition = PromptReorderCloseTransition(
            selection_start=state.selection_start if restore_selection else None,
            selection_end=state.selection_end if restore_selection else None,
        )
        self._state = PromptReorderSessionState()
        self._latest_commit_snapshot = None
        return transition

    def replace_state(self, state: PromptReorderSessionState) -> None:
        """Replace state from an explicitly prepared lifecycle snapshot."""

        self._state = state


__all__ = [
    "PromptReorderCloseTransition",
    "PromptReorderCommitOutcome",
    "PromptReorderCommitPlan",
    "PromptReorderCommitSnapshot",
    "PromptReorderSessionOwner",
    "PromptReorderSessionState",
]
