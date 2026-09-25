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

"""Define focused collaborators for full editor projection loads."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from .projection_models import ProjectedCubeBuild
from .projection_preparation import BehaviorRefreshReason, EditorProjectionPreparation
from .projection_session_models import ActiveProjectionSession
from .projection_surface_state import EditorSurfaceProjectionSignature


class FullProjectionLoadPanelPort(Protocol):
    """Describe panel state used by full projection load orchestration."""

    cube_widgets: dict[str, object]

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Synchronize prompt editor widgets from cube buffers."""

    def _refresh_link_widgets(self) -> None:
        """Refresh link widgets after projection publication."""


class FullProjectionActiveSessionPort(Protocol):
    """Describe active projection session ownership used by full loads."""

    def start(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
    ) -> ActiveProjectionSession:
        """Start a full projection session."""

    def resolve(self, session: ActiveProjectionSession, *, reason: str) -> None:
        """Resolve a successful projection session."""

    def cancel(self, session: ActiveProjectionSession, *, reason: str) -> None:
        """Cancel an abandoned projection session."""


class FullProjectionCompletionPort(Protocol):
    """Describe pending completion ownership used by full loads."""

    def register_projection_completion(
        self,
        session: ActiveProjectionSession,
        *,
        workflow_id: str,
        aliases: set[str],
        on_complete: Callable[[], None] | None,
        reason: BehaviorRefreshReason,
    ) -> None:
        """Register a full-projection completion callback."""


class FullProjectionSessionCompletionPort(Protocol):
    """Describe session completion attachment used by full loads."""

    def claim_superseded_inserts(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        projection_session: ActiveProjectionSession,
    ) -> None:
        """Claim superseded incremental insert completions."""


class FullProjectionRuntimeIssuePort(Protocol):
    """Describe runtime issue projection setup used by full loads."""

    def begin_live_node_definition_report_projection(self) -> None:
        """Start live node definition report projection."""


class FullProjectionPreparationPort(Protocol):
    """Describe projection preparation operations used by full loads."""

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
        """Prepare panel state for projection."""

    def clear_prompt_context(
        self,
        preparation: EditorProjectionPreparation,
        *,
        reason: str,
    ) -> None:
        """Clear prompt context created for projection."""

    def end_behavior_transaction(
        self,
        preparation: EditorProjectionPreparation,
        *,
        reason: BehaviorRefreshReason,
    ) -> None:
        """End behavior refresh transaction created for projection."""


class FullProjectionLifecyclePort(Protocol):
    """Describe lifecycle cleanup and visibility refresh used by full loads."""

    def remove_closed_aliases(self, live_aliases: set[str]) -> None:
        """Remove widgets for aliases not present in the new projection."""

    def refresh_visibility(
        self,
        *,
        message: str,
        reason: BehaviorRefreshReason,
        use_cached_snapshot: bool = False,
    ) -> None:
        """Refresh behavior-derived visibility state."""


class FullProjectionWidgetBuilderPort(Protocol):
    """Describe projected widget build and reuse operations used by full loads."""

    def build_ordered_widgets(
        self,
        cube_entries: Sequence[tuple[str, object]],
        *,
        workflow_id: str,
        snapshot_identity: object | None,
        projection_session: ActiveProjectionSession,
    ) -> tuple[list[tuple[str, object]], list[ProjectedCubeBuild]]:
        """Build or reuse cube widgets for a projection."""

    def discard_cancelled_projected_build(
        self,
        projected_build: ProjectedCubeBuild,
        *,
        workflow_id: str,
        reason: str,
    ) -> None:
        """Discard one unrevealed projected build."""


class FullProjectionRenderReconcilerPort(Protocol):
    """Describe layout reconciliation used by full loads."""

    def reconcile_ordered_widgets(
        self,
        ordered_widgets: Sequence[tuple[str, object]],
    ) -> None:
        """Publish ordered widgets to the panel layout."""


class FullProjectionHiddenBuildSchedulerPort(Protocol):
    """Describe hidden staged build scheduling used by full loads."""

    def schedule_projected_cube_builds(
        self,
        projected_builds: Sequence[ProjectedCubeBuild],
        on_complete: Callable[[], None],
        on_cancel: Callable[[], None],
        *,
        workflow_id: str,
        is_current: Callable[[], bool] | None = None,
        visible_commit: Callable[[Sequence[ProjectedCubeBuild]], bool] | None = None,
        partial_visible_commit: Callable[[Sequence[ProjectedCubeBuild]], bool]
        | None = None,
    ) -> None:
        """Schedule hidden projected cube builds."""


class FullProjectionSessionRegistryPort(Protocol):
    """Describe projection session currency checks used by staged builds."""

    def is_current(self, session: ActiveProjectionSession) -> bool:
        """Return whether the supplied session still owns projection publication."""


class FullProjectionBusyPort(Protocol):
    """Describe busy presentation used by staged full loads."""

    def begin_projection_busy(
        self,
        *,
        workflow_id: str,
        pending_build_count: int,
    ) -> object | None:
        """Begin busy presentation for a staged projection."""

    def end_projection_busy(
        self,
        busy_token: object | None,
        *,
        workflow_id: str,
        busy_started: bool,
        pending_build_count: int,
    ) -> None:
        """End busy presentation for a staged projection."""


class FullProjectionBuildRegistryPort(Protocol):
    """Describe projected build cancellation used by full loads."""

    def cancel(self, alias: str, token: object, reason: str) -> bool:
        """Cancel one projected build by ownership token."""


class FullProjectionVisibleCommitPort(Protocol):
    """Describe visible commit publication used by staged full loads."""

    def commit_or_defer(
        self,
        *,
        workflow_id: str,
        projection_session: ActiveProjectionSession,
        projected_builds: Sequence[ProjectedCubeBuild],
        finish_refresh: Callable[[], None],
        cancel_refresh: Callable[[str], None],
    ) -> bool:
        """Commit staged builds immediately or defer until visible."""

    def commit_partial_visible_projection(
        self,
        *,
        workflow_id: str,
        projection_session: ActiveProjectionSession,
        projected_builds: Sequence[ProjectedCubeBuild],
    ) -> bool:
        """Publish one usable batch without resolving the full projection."""


class FullProjectionStatePort(Protocol):
    """Describe clean projection signature state used by full loads."""

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature:
        """Return the structural projection signature."""

    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None:
        """Mark the projected surface clean for the supplied signature."""


@dataclass(frozen=True, slots=True)
class EditorFullProjectionLoadPorts:
    """Group explicit collaborators required by full projection loads."""

    panel: FullProjectionLoadPanelPort
    active_sessions: FullProjectionActiveSessionPort
    projection_completions: FullProjectionCompletionPort
    session_completions: FullProjectionSessionCompletionPort
    runtime_issues: FullProjectionRuntimeIssuePort
    projection_preparation: FullProjectionPreparationPort
    projection_lifecycle: FullProjectionLifecyclePort
    projected_widget_builder: FullProjectionWidgetBuilderPort
    render_reconciler: FullProjectionRenderReconcilerPort
    hidden_build_scheduler: FullProjectionHiddenBuildSchedulerPort
    projection_sessions: FullProjectionSessionRegistryPort
    projection_busy: FullProjectionBusyPort
    build_registry: FullProjectionBuildRegistryPort
    visible_commits: FullProjectionVisibleCommitPort
    projection_state: FullProjectionStatePort


__all__ = ["EditorFullProjectionLoadPorts", "FullProjectionLoadPanelPort"]
