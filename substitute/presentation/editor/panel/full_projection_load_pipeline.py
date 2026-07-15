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

"""Run full editor panel projection loads and staged refresh completion."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_timing,
    log_warning,
)

from .projection_models import (
    EditorFullProjectionBusyState,
    EditorFullProjectionLoadPlan,
    EditorFullProjectionLoadRequest,
    ProjectedCubeBuild,
)
from .projection_observability import (
    log_panel_projection_event,
    log_panel_projection_timing,
)
from .projection_preparation import BehaviorRefreshReason, EditorProjectionPreparation
from .projection_session import (
    ActiveProjectionSession,
    EditorSurfaceProjectionSignature,
)

_LOGGER = get_logger("presentation.editor.panel.full_projection_load_pipeline")


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
    """Describe completion callback ownership used by full loads."""

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
    """Describe projected widget build/reuse operations used by full loads."""

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


class EditorFullProjectionLoadPipeline:
    """Own full workflow projection orchestration and cleanup."""

    def __init__(self, ports: EditorFullProjectionLoadPorts) -> None:
        """Store explicit collaborators used by the full-load pipeline."""

        self._ports = ports

    def load_all_cubes(self, request: EditorFullProjectionLoadRequest) -> None:
        """Run the full projection load and schedule staged builds when needed."""

        plan = self._prepare_full_projection_load(request)
        if plan.projected_builds:
            self._schedule_projected_refresh(plan)
            return
        self._complete_live_refresh(plan)

    def _prepare_full_projection_load(
        self,
        request: EditorFullProjectionLoadRequest,
    ) -> EditorFullProjectionLoadPlan:
        """Prepare projection state and widget build records for a full load."""

        ports = self._ports
        projection_session = ports.active_sessions.start(
            workflow_id=request.workflow_id,
            cube_entries=request.cube_entries,
        )
        ports.projection_completions.register_projection_completion(
            projection_session,
            workflow_id=request.workflow_id,
            aliases={route_key for route_key, _ in request.cube_entries},
            on_complete=request.on_complete,
            reason="full_workflow_projection",
        )
        ports.projection_completions.claim_superseded_inserts(
            workflow_id=request.workflow_id,
            cube_entries=request.cube_entries,
            projection_session=projection_session,
        )
        self._log_projection_started(request)
        ports.runtime_issues.begin_live_node_definition_report_projection()
        try:
            preparation = ports.projection_preparation.prepare_projection(
                request.cube_entries,
                cube_states=request.cube_states,
                stack_order=request.stack_order,
                reason="full_workflow_projection",
                workflow_id=request.workflow_id,
                previous_cube_states=request.previous_cube_states,
                previous_stack_order=request.previous_stack_order,
                prompt_context_required=True,
            )
        except Exception:
            ports.active_sessions.cancel(
                projection_session,
                reason="full_projection_prepare_failed",
            )
            raise
        ports.projection_lifecycle.remove_closed_aliases(
            {route_key for route_key, _ in request.cube_entries}
        )
        try:
            ordered_widgets, projected_builds = self._build_ordered_widgets(
                request,
                preparation,
                projection_session,
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as error:
            self._cancel_prepared_widget_load(
                request,
                preparation,
                projection_session,
                error,
            )
            raise
        return EditorFullProjectionLoadPlan(
            request=request,
            projection_session=projection_session,
            preparation=preparation,
            ordered_widgets=tuple(ordered_widgets),
            projected_builds=tuple(projected_builds),
        )

    def _log_projection_started(
        self,
        request: EditorFullProjectionLoadRequest,
    ) -> None:
        """Log and trace the beginning of a full projection load."""

        log_info(
            _LOGGER,
            "Started editor full projection cube load",
            workflow_id=request.workflow_id,
            cube_section_count=len(request.cube_entries),
            stack_order_count=len(request.stack_order or []),
        )
        log_panel_projection_event(
            "full_projection.start",
            level="info",
            workflow_id=request.workflow_id,
            cube_section_count=len(request.cube_entries),
            stack_order_count=len(request.stack_order or []),
            projection_mode="live",
        )

    def _build_ordered_widgets(
        self,
        request: EditorFullProjectionLoadRequest,
        preparation: EditorProjectionPreparation,
        projection_session: ActiveProjectionSession,
    ) -> tuple[list[tuple[str, object]], list[ProjectedCubeBuild]]:
        """Build or reuse visible widgets while leaving staged builds hidden."""

        ports = self._ports
        phase_started_at = perf_counter()
        ordered_widgets, projected_builds = (
            ports.projected_widget_builder.build_ordered_widgets(
                request.cube_entries,
                workflow_id=request.workflow_id,
                snapshot_identity=preparation.snapshot_identity,
                projection_session=projection_session,
            )
        )
        log_timing(
            _LOGGER,
            "Built missing editor cube widgets",
            started_at=phase_started_at,
            workflow_id=request.workflow_id,
            cube_section_count=len(request.cube_entries),
            ordered_widget_count=len(ordered_widgets),
            existing_widget_count=len(ports.panel.cube_widgets),
            pending_build_count=len(projected_builds),
            level="debug",
        )
        if projected_builds:
            log_debug(
                _LOGGER,
                "Deferred editor cube layout repopulation until staged reveal",
                workflow_id=request.workflow_id,
                cube_section_count=len(request.cube_entries),
                ordered_widget_count=len(ordered_widgets),
                pending_build_count=len(projected_builds),
            )
            return ordered_widgets, projected_builds
        phase_started_at = perf_counter()
        ports.render_reconciler.reconcile_ordered_widgets(ordered_widgets)
        log_timing(
            _LOGGER,
            "Repopulated editor cube layout and scroll tracking",
            started_at=phase_started_at,
            workflow_id=request.workflow_id,
            cube_section_count=len(request.cube_entries),
            ordered_widget_count=len(ordered_widgets),
            level="debug",
        )
        return ordered_widgets, projected_builds

    def _cancel_prepared_widget_load(
        self,
        request: EditorFullProjectionLoadRequest,
        preparation: EditorProjectionPreparation,
        projection_session: ActiveProjectionSession,
        error: Exception,
    ) -> None:
        """Cancel a prepared full projection after widget preparation fails."""

        ports = self._ports
        ports.active_sessions.cancel(
            projection_session,
            reason="full_projection_widget_preparation_failed",
        )
        ports.projection_preparation.clear_prompt_context(
            preparation,
            reason="full_workflow_projection_error",
        )
        ports.projection_preparation.end_behavior_transaction(
            preparation,
            reason="full_workflow_projection",
        )
        log_warning(
            _LOGGER,
            "Failed during editor projection widget preparation",
            workflow_id=request.workflow_id,
            cube_section_count=len(request.cube_entries),
            error_type=type(error).__name__,
        )

    def _complete_live_refresh(self, plan: EditorFullProjectionLoadPlan) -> None:
        """Complete a full projection that did not need hidden staged builds."""

        ports = self._ports
        try:
            self._finish_refresh(plan)
            ports.active_sessions.resolve(
                plan.projection_session,
                reason="replacement_full_projection_complete",
            )
            log_panel_projection_event(
                "full_projection.live_complete",
                level="info",
                workflow_id=plan.request.workflow_id,
                cube_section_count=len(plan.request.cube_entries),
                pending_build_count=0,
                projection_mode="live",
            )
        except Exception:
            ports.active_sessions.cancel(
                plan.projection_session,
                reason="replacement_full_projection_failed",
            )
            raise
        finally:
            ports.projection_preparation.clear_prompt_context(
                plan.preparation,
                reason="full_workflow_projection_complete",
            )

    def _finish_refresh(self, plan: EditorFullProjectionLoadPlan) -> None:
        """Finish registries and clean state after a full projection commits."""

        ports = self._ports
        panel = ports.panel
        request = plan.request
        try:
            phase_started = perf_counter()
            panel.sync_prompt_editor_values_from_buffers()
            panel._refresh_link_widgets()
            log_timing(
                _LOGGER,
                "Refreshed editor widget registries after cube load",
                started_at=phase_started,
                workflow_id=request.workflow_id,
                cube_section_count=len(request.cube_entries),
                level="debug",
            )

            phase_started = perf_counter()
            ports.projection_lifecycle.refresh_visibility(
                message="Failed to refresh editor visibility after cube load",
                reason="full_workflow_projection",
                use_cached_snapshot=True,
            )
            log_timing(
                _LOGGER,
                "Refreshed editor visibility after cube load",
                started_at=phase_started,
                workflow_id=request.workflow_id,
                cube_section_count=len(request.cube_entries),
                level="debug",
            )
            log_timing(
                _LOGGER,
                "Completed editor cube load reconciliation",
                started_at=request.started_at,
                workflow_id=request.workflow_id,
                cube_section_count=len(request.cube_entries),
                existing_widget_count=len(panel.cube_widgets),
                pending_build_count=len(plan.projected_builds),
                level="debug",
            )
            log_panel_projection_timing(
                "full_projection.complete",
                started_at=request.started_at,
                workflow_id=request.workflow_id,
                cube_section_count=len(request.cube_entries),
                existing_widget_count=len(panel.cube_widgets),
                pending_build_count=len(plan.projected_builds),
                projection_mode="live",
            )
            clean_signature = ports.projection_state.current_projection_signature(
                workflow_id=request.workflow_id,
                cube_entries=request.cube_entries,
                cube_states=request.cube_states,
                stack_order=request.stack_order,
            )
            ports.projection_state.mark_projection_clean(clean_signature)
        finally:
            ports.projection_preparation.end_behavior_transaction(
                plan.preparation,
                reason="full_workflow_projection",
            )

    def _schedule_projected_refresh(self, plan: EditorFullProjectionLoadPlan) -> None:
        """Schedule hidden staged builds and visible commit handling."""

        ports = self._ports
        request = plan.request
        busy_state = self._begin_busy_state(plan)
        log_timing(
            _LOGGER,
            "Scheduled editor cube load reconciliation",
            started_at=request.started_at,
            workflow_id=request.workflow_id,
            cube_section_count=len(request.cube_entries),
            existing_widget_count=len(ports.panel.cube_widgets),
            pending_build_count=len(plan.projected_builds),
            busy_started=busy_state.started,
            level="debug",
        )
        ports.hidden_build_scheduler.schedule_projected_cube_builds(
            plan.projected_builds,
            lambda: self._finish_projected_refresh(plan, busy_state),
            lambda: self._cancel_projected_refresh(
                plan,
                busy_state,
                reason="workflow_projection_cancelled",
            ),
            workflow_id=request.workflow_id,
            is_current=lambda: ports.projection_sessions.is_current(
                plan.projection_session
            ),
            visible_commit=lambda completed_builds: self._commit_projected_refresh(
                plan,
                busy_state,
                completed_builds,
            ),
        )

    def _begin_busy_state(
        self,
        plan: EditorFullProjectionLoadPlan,
    ) -> EditorFullProjectionBusyState:
        """Begin the shell busy overlay for one staged projection."""

        busy_token = self._ports.projection_busy.begin_projection_busy(
            workflow_id=plan.request.workflow_id,
            pending_build_count=len(plan.projected_builds),
        )
        return EditorFullProjectionBusyState(
            token=busy_token,
            started=busy_token is not None,
        )

    def _finish_projected_refresh(
        self,
        plan: EditorFullProjectionLoadPlan,
        busy_state: EditorFullProjectionBusyState,
    ) -> None:
        """Finish a successful staged projection and release busy state."""

        ports = self._ports
        try:
            try:
                self._finish_refresh(plan)
                ports.active_sessions.resolve(
                    plan.projection_session,
                    reason="replacement_full_projection_complete",
                )
            except Exception:
                ports.active_sessions.cancel(
                    plan.projection_session,
                    reason="replacement_full_projection_failed",
                )
                raise
            finally:
                self._end_busy_state(plan, busy_state)
        finally:
            ports.projection_preparation.clear_prompt_context(
                plan.preparation,
                reason="full_workflow_projection_complete",
            )

    def _cancel_projected_refresh(
        self,
        plan: EditorFullProjectionLoadPlan,
        busy_state: EditorFullProjectionBusyState,
        *,
        reason: str,
    ) -> None:
        """Release staged projection resources after cancellation."""

        ports = self._ports
        try:
            for projected_build in plan.projected_builds:
                ports.build_registry.cancel(
                    projected_build.cube_alias,
                    projected_build.token,
                    reason,
                )
                ports.projected_widget_builder.discard_cancelled_projected_build(
                    projected_build,
                    workflow_id=plan.request.workflow_id,
                    reason=reason,
                )
            ports.active_sessions.cancel(
                plan.projection_session,
                reason=reason,
            )
            ports.projection_preparation.end_behavior_transaction(
                plan.preparation,
                reason="full_workflow_projection",
            )
        finally:
            self._end_busy_state(plan, busy_state)
            ports.projection_preparation.clear_prompt_context(
                plan.preparation,
                reason=f"full_workflow_projection_cancelled:{reason}",
            )

    def _commit_projected_refresh(
        self,
        plan: EditorFullProjectionLoadPlan,
        busy_state: EditorFullProjectionBusyState,
        completed_builds: Sequence[ProjectedCubeBuild],
    ) -> bool:
        """Commit or defer a finished staged projection batch."""

        return bool(
            self._ports.visible_commits.commit_or_defer(
                workflow_id=plan.request.workflow_id,
                projection_session=plan.projection_session,
                projected_builds=completed_builds,
                finish_refresh=lambda: self._finish_projected_refresh(
                    plan,
                    busy_state,
                ),
                cancel_refresh=lambda reason: self._cancel_projected_refresh(
                    plan,
                    busy_state,
                    reason=reason,
                ),
            )
        )

    def _end_busy_state(
        self,
        plan: EditorFullProjectionLoadPlan,
        busy_state: EditorFullProjectionBusyState,
    ) -> None:
        """Release shell busy presentation for a staged full projection."""

        self._ports.projection_busy.end_projection_busy(
            busy_state.token,
            workflow_id=plan.request.workflow_id,
            busy_started=busy_state.started,
            pending_build_count=len(plan.projected_builds),
        )
