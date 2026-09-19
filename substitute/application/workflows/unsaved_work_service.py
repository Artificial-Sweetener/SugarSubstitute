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

"""Own authoritative explicit-save state for workflow documents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class UnsavedWorkDecision(str, Enum):
    """Name the three safe responses to an unsaved-work boundary."""

    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class WorkflowDocumentState:
    """Describe whether one workflow differs from its explicit save target."""

    dirty: bool = False
    source_path: Path | None = None


class UnsavedWorkService:
    """Track explicit document saves independently from recovery autosaves."""

    def __init__(self) -> None:
        """Create an empty workflow-document registry."""

        self._states: dict[str, WorkflowDocumentState] = {}

    def state_for(self, workflow_id: str) -> WorkflowDocumentState:
        """Return one workflow state, defaulting an unknown document to clean."""

        return self._states.get(workflow_id, WorkflowDocumentState())

    def mark_dirty(self, workflow_id: str) -> None:
        """Record that one workflow changed after its last explicit save."""

        previous = self.state_for(workflow_id)
        self._states[workflow_id] = WorkflowDocumentState(
            dirty=True,
            source_path=previous.source_path,
        )

    def mark_saved(self, workflow_id: str, source_path: Path) -> None:
        """Record a successful explicit save or loaded source baseline."""

        self._states[workflow_id] = WorkflowDocumentState(
            dirty=False,
            source_path=Path(source_path),
        )

    def restore(
        self,
        workflow_id: str,
        *,
        dirty: bool,
        source_path: Path | None,
    ) -> None:
        """Restore authoritative document state from a recovery snapshot."""

        self._states[workflow_id] = WorkflowDocumentState(
            dirty=dirty,
            source_path=Path(source_path) if source_path is not None else None,
        )

    def dirty_workflow_ids(self, ordered_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Return dirty workflow ids in their visible tab order."""

        return tuple(
            workflow_id
            for workflow_id in ordered_ids
            if self.state_for(workflow_id).dirty
        )

    def rename(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Move document state with a renamed workflow identity."""

        state = self._states.pop(old_workflow_id, None)
        if state is not None:
            self._states[new_workflow_id] = state

    def remove(self, workflow_id: str) -> None:
        """Forget document state after a confirmed workflow close."""

        self._states.pop(workflow_id, None)


__all__ = [
    "UnsavedWorkDecision",
    "UnsavedWorkService",
    "WorkflowDocumentState",
]
