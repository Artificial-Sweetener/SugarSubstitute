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

"""Define focused collaborators for incremental editor insertion."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from .incremental_insert_motion import IncrementalInsertMotionPort
from .projection_build_registry import CubeSectionBuildReuseDecision
from .projection_preparation import (
    BehaviorRefreshReason,
    CubeDefinitionIdentity,
    EditorProjectionPreparation,
)
from .projection_session_models import ActiveProjectionSession, InsertCompletionPhase


class IncrementalInsertPanelPort(Protocol):
    """Describe panel state and widget hooks used by incremental inserts."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]

    def _begin_build_cube_widget(self, cube_alias: str, cube_state: object) -> object:
        """Begin a deferred cube-section build."""

    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None:
        """Synchronize prompt editor values for one cube."""

    def refresh_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh link widgets for one cube."""


class IncrementalInsertSessionRegistryPort(Protocol):
    """Describe active full-projection lookup used by incremental inserts."""

    def owns(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
    ) -> ActiveProjectionSession | None:
        """Return the active projection session owning one cube alias."""


class IncrementalInsertCompletionPort(Protocol):
    """Describe pending insert completion registry operations."""

    def register_pending_insert(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        completion_phase: InsertCompletionPhase,
        on_complete: Callable[[], None] | None,
    ) -> None:
        """Register a pending insert completion callback."""

    def forget_pending_insert(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        reason: str,
    ) -> None:
        """Forget a pending insert completion callback."""

    def cancel_pending_insert(
        self,
        *,
        workflow_id: str,
        cube_alias: str,
        token: object,
        reason: str,
        cancel_superseded: bool,
    ) -> None:
        """Cancel a pending insert completion callback."""


class IncrementalInsertSessionCompletionPort(Protocol):
    """Describe completion attachment to an active full projection."""

    def attach_insert(
        self,
        *,
        session: ActiveProjectionSession,
        workflow_id: str,
        cube_alias: str,
        completion_phase: InsertCompletionPhase,
        on_complete: Callable[[], None] | None,
        reason: str,
    ) -> None:
        """Attach an insert completion to an active full projection."""


class IncrementalInsertPreparationPort(Protocol):
    """Describe projection preparation operations used by incremental inserts."""

    def prepare_projection(
        self,
        cube_entries: Sequence[tuple[str, object]],
        *,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: BehaviorRefreshReason,
        workflow_id: str,
        previous_cube_states: dict[str, object] | None,
        previous_stack_order: list[str] | None,
        prompt_context_required: bool = False,
    ) -> EditorProjectionPreparation:
        """Prepare panel state for insert projection."""

    def end_behavior_transaction(
        self,
        preparation: EditorProjectionPreparation,
        *,
        reason: BehaviorRefreshReason,
    ) -> None:
        """End behavior refresh transaction for insert projection."""


class IncrementalInsertHiddenBuildSchedulerPort(Protocol):
    """Describe deferred build-session scheduling used by incremental inserts."""

    def schedule_cube_build_session(
        self,
        build_session: object,
        *,
        on_first_usable: Callable[[], None] | None = None,
        on_complete: Callable[[], None],
        is_current: Callable[[], bool] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Schedule one cube build session across event-loop turns."""


class IncrementalInsertBuildRegistryPort(Protocol):
    """Describe build registry operations used by incremental inserts."""

    def reuse_decision(
        self,
        alias: str,
        widget: object,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> CubeSectionBuildReuseDecision:
        """Return whether an existing widget remains reusable."""

    def start(
        self,
        *,
        alias: str,
        widget: object,
        session: object | None,
        snapshot_identity: object | None,
        definition_identity: CubeDefinitionIdentity | None,
    ) -> object:
        """Start tracking one active build."""

    def is_current(self, alias: str, token: object) -> bool:
        """Return whether the token still owns the alias build."""

    def mark_complete(self, alias: str, token: object) -> bool:
        """Mark one active build complete."""

    def cancel(self, alias: str, token: object, reason: str) -> bool:
        """Cancel one active build."""


class IncrementalInsertLifecyclePort(Protocol):
    """Describe lifecycle cleanup and visibility refresh used by inserts."""

    def discard_cube_widget(self, cube_alias: str, *, reason: str) -> None:
        """Discard a stale cube widget."""

    def refresh_visibility(
        self,
        *,
        message: str,
        reason: BehaviorRefreshReason,
        use_cached_snapshot: bool = False,
    ) -> None:
        """Refresh behavior-derived visibility state."""


class IncrementalInsertRenderReconcilerPort(Protocol):
    """Describe layout and reveal operations used by incremental inserts."""

    def reconcile_ordered_widgets(
        self,
        ordered_widgets: Sequence[tuple[str, object]],
    ) -> None:
        """Publish ordered widgets to the panel layout."""

    def finalize_cube_widget_for_reveal(
        self,
        cube_alias: str,
        cube_widget: object,
        *,
        reason: str,
        workflow_id: str,
    ) -> None:
        """Finalize one widget for visible reveal."""

    def set_cube_widget_update_wash(self, widget: object, *, visible: bool) -> None:
        """Apply or remove update-wash styling on one widget."""


@dataclass(frozen=True, slots=True)
class EditorIncrementalInsertPorts:
    """Group explicit collaborators required by incremental insert orchestration."""

    panel: IncrementalInsertPanelPort
    projection_sessions: IncrementalInsertSessionRegistryPort
    projection_completions: IncrementalInsertCompletionPort
    session_completions: IncrementalInsertSessionCompletionPort
    projection_preparation: IncrementalInsertPreparationPort
    hidden_build_scheduler: IncrementalInsertHiddenBuildSchedulerPort
    build_registry: IncrementalInsertBuildRegistryPort
    projection_lifecycle: IncrementalInsertLifecyclePort
    render_reconciler: IncrementalInsertRenderReconcilerPort
    motion: IncrementalInsertMotionPort


__all__ = ["EditorIncrementalInsertPorts"]
