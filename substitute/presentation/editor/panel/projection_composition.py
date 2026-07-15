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

"""Compose editor projection collaborators for panel projection orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from .clean_projection_refresh import EditorCleanProjectionRefreshController
from .cube_section_build_controller import CubeSectionBuildController
from .cube_section_staleness_controller import CubeSectionStalenessController
from .full_projection_load_pipeline import (
    EditorFullProjectionLoadPipeline,
    EditorFullProjectionLoadPorts,
)
from .hidden_build_scheduler import HiddenBuildScheduler, HiddenBuildSchedulerPorts
from .incremental_insert_pipeline import (
    EditorIncrementalInsertPipeline,
    EditorIncrementalInsertPorts,
)
from .projected_widget_builder import ProjectedWidgetBuilder
from .projection_active_session_controller import (
    EditorActiveProjectionSessionController,
)
from .projection_build_registry import CubeSectionBuildRegistry
from .projection_busy_adapter import EditorProjectionBusyAdapter
from .projection_lifecycle import (
    EditorProjectionLifecyclePipeline,
    EditorProjectionLifecyclePorts,
    EditorProjectionRuntimeIssueIntegration,
    ProjectionBuildRegistryPort,
    ProjectionLifecyclePanelPort,
)
from .projection_ports import EditorRefreshPanelProtocol
from .projection_preparation import (
    EditorProjectionPreparationController,
    ProjectionPromptContextPort,
    begin_behavior_refresh_transaction,
    end_behavior_refresh_transaction,
)
from .projection_session import (
    ActiveProjectionSessionRegistry,
    ProjectionCompletionRegistry,
    ProjectionSurfaceStateController,
)
from .projection_workflow_context import EditorProjectionWorkflowContext
from .rendering.render_reconciler import EditorPanelRenderReconciler
from .runtime_issue_projection_adapter import RuntimeIssueProjectionAdapter
from .visible_projection_commit import (
    EditorVisibleProjectionCommitPipeline,
    EditorVisibleProjectionCommitPorts,
    editor_panel_is_visible,
)


class EditorProjectionCoordinatorPort(Protocol):
    """Describe coordinator callbacks required while composition owns construction."""

    def invalidate_projection(self, *, reason: str) -> None:
        """Mark the projection dirty for the supplied reason."""


@dataclass(frozen=True, slots=True)
class EditorProjectionComposition:
    """Hold projection collaborators constructed for one editor panel."""

    build_registry: CubeSectionBuildRegistry
    projection_completions: ProjectionCompletionRegistry
    projection_sessions: ActiveProjectionSessionRegistry
    active_sessions: EditorActiveProjectionSessionController
    projection_state: ProjectionSurfaceStateController
    runtime_issues: EditorProjectionRuntimeIssueIntegration
    projection_preparation: EditorProjectionPreparationController
    render_reconciler: EditorPanelRenderReconciler
    workflow_context: EditorProjectionWorkflowContext
    projection_busy: EditorProjectionBusyAdapter
    clean_projection_refresh: EditorCleanProjectionRefreshController
    cube_section_staleness: CubeSectionStalenessController
    runtime_issue_projection: RuntimeIssueProjectionAdapter
    incremental_inserts: EditorIncrementalInsertPipeline
    projected_widget_builder: ProjectedWidgetBuilder
    hidden_build_scheduler: HiddenBuildScheduler
    cube_section_builds: CubeSectionBuildController
    visible_commits: EditorVisibleProjectionCommitPipeline
    projection_lifecycle: EditorProjectionLifecyclePipeline
    full_projection_loads: EditorFullProjectionLoadPipeline


def compose_editor_projection(
    panel: EditorRefreshPanelProtocol,
    coordinator: EditorProjectionCoordinatorPort,
) -> EditorProjectionComposition:
    """Build projection collaborators and wire their narrow ports."""

    build_registry = CubeSectionBuildRegistry()
    projection_completions = ProjectionCompletionRegistry()
    projection_sessions = ActiveProjectionSessionRegistry()
    projection_state = ProjectionSurfaceStateController(panel)
    runtime_issues = EditorProjectionRuntimeIssueIntegration(panel)
    render_reconciler = EditorPanelRenderReconciler(panel)
    workflow_context = EditorProjectionWorkflowContext(panel)
    projection_busy = EditorProjectionBusyAdapter(panel)
    clean_projection_refresh = EditorCleanProjectionRefreshController(panel)
    cube_section_builds = CubeSectionBuildController(panel)
    runtime_issue_projection = RuntimeIssueProjectionAdapter(
        panel=panel,
        runtime_issues=runtime_issues,
    )
    visible_commits = EditorVisibleProjectionCommitPipeline(
        EditorVisibleProjectionCommitPorts(
            active_workflow_id=workflow_context.active_workflow_id,
            panel_is_visible=lambda: editor_panel_is_visible(panel),
            is_projection_session_current=projection_sessions.is_current,
            reveal_projected_cube_builds=(
                lambda builds, workflow_id: (
                    render_reconciler.reveal_projected_cube_builds(
                        builds,
                        workflow_id=workflow_id,
                    )
                )
            ),
            mark_build_complete=build_registry.mark_complete,
            mark_build_failed=build_registry.mark_failed,
        )
    )
    active_sessions = EditorActiveProjectionSessionController(
        sessions=projection_sessions,
        completions=projection_completions,
        discard_pending_visible_commit=(
            lambda reason: visible_commits.discard_pending_visible_projection_commit(
                reason=reason
            )
        ),
    )
    projection_preparation = EditorProjectionPreparationController(
        panel=panel,
        prompt_context=cast(ProjectionPromptContextPort, panel),
        runtime_issues=runtime_issues,
        begin_behavior_transaction=(
            lambda reason, workflow_id: begin_behavior_refresh_transaction(
                panel,
                reason=reason,
                workflow_id=workflow_id,
            )
        ),
        end_behavior_transaction=(
            lambda reason, workflow_id, transaction_started: (
                end_behavior_refresh_transaction(
                    panel,
                    reason=reason,
                    workflow_id=workflow_id,
                    transaction_started=transaction_started,
                )
            )
        ),
    )
    cube_section_staleness = CubeSectionStalenessController(
        panel=panel,
        build_registry=build_registry,
        completion_registry=projection_completions,
        workflow_context=workflow_context,
    )
    hidden_build_scheduler = HiddenBuildScheduler(
        HiddenBuildSchedulerPorts(
            reveal_projected_cube_builds=(
                lambda builds, workflow_id: (
                    render_reconciler.reveal_projected_cube_builds(
                        builds,
                        workflow_id=workflow_id,
                    )
                )
            ),
            mark_build_complete=build_registry.mark_complete,
            mark_build_failed=build_registry.mark_failed,
        )
    )
    projection_lifecycle = EditorProjectionLifecyclePipeline(
        EditorProjectionLifecyclePorts(
            panel=cast(ProjectionLifecyclePanelPort, panel),
            build_registry=cast(ProjectionBuildRegistryPort, build_registry),
            projection_completions=projection_completions,
            visible_commits=visible_commits,
            render_reconciler=render_reconciler,
            active_projection_session=lambda: active_sessions.active_session,
            cancel_active_projection_session=(
                lambda session, reason: active_sessions.cancel(
                    session,
                    reason=reason,
                )
            ),
            invalidate_projection=(
                lambda reason: coordinator.invalidate_projection(reason=reason)
            ),
        )
    )
    incremental_inserts = EditorIncrementalInsertPipeline(
        EditorIncrementalInsertPorts(
            panel=panel,
            projection_sessions=projection_sessions,
            projection_completions=projection_completions,
            projection_preparation=projection_preparation,
            hidden_build_scheduler=hidden_build_scheduler,
            build_registry=build_registry,
            projection_lifecycle=projection_lifecycle,
            render_reconciler=render_reconciler,
        )
    )
    projected_widget_builder = ProjectedWidgetBuilder(
        panel=panel,
        build_registry=build_registry,
        projection_completions=projection_completions,
        projection_lifecycle=projection_lifecycle,
        runtime_issue_projection=runtime_issue_projection,
    )
    full_projection_loads = EditorFullProjectionLoadPipeline(
        EditorFullProjectionLoadPorts(
            panel=panel,
            active_sessions=active_sessions,
            projection_completions=projection_completions,
            runtime_issues=runtime_issues,
            projection_preparation=projection_preparation,
            projection_lifecycle=projection_lifecycle,
            projected_widget_builder=projected_widget_builder,
            render_reconciler=render_reconciler,
            hidden_build_scheduler=hidden_build_scheduler,
            projection_sessions=projection_sessions,
            projection_busy=projection_busy,
            build_registry=build_registry,
            visible_commits=visible_commits,
            projection_state=projection_state,
        )
    )
    return EditorProjectionComposition(
        build_registry=build_registry,
        projection_completions=projection_completions,
        projection_sessions=projection_sessions,
        active_sessions=active_sessions,
        projection_state=projection_state,
        runtime_issues=runtime_issues,
        projection_preparation=projection_preparation,
        render_reconciler=render_reconciler,
        workflow_context=workflow_context,
        projection_busy=projection_busy,
        clean_projection_refresh=clean_projection_refresh,
        cube_section_staleness=cube_section_staleness,
        runtime_issue_projection=runtime_issue_projection,
        incremental_inserts=incremental_inserts,
        projected_widget_builder=projected_widget_builder,
        hidden_build_scheduler=hidden_build_scheduler,
        cube_section_builds=cube_section_builds,
        visible_commits=visible_commits,
        projection_lifecycle=projection_lifecycle,
        full_projection_loads=full_projection_loads,
    )


__all__ = [
    "EditorProjectionComposition",
    "EditorProjectionCoordinatorPort",
    "compose_editor_projection",
]
