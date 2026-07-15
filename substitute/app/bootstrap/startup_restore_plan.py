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

"""Build startup restore plans and start restore asset preloading."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from substitute.app.bootstrap.startup_restore_workspace import (
    restored_workspace_workflow_count,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.app.bootstrap.workspace_restore_asset_preload import (
    WorkspaceRestoreAssetPreloadHandle,
)
from substitute.application.workspace_state import (
    InitialWorkspaceRestorePlan,
    InitialWorkspaceRestorePlanService,
    SnapshotNormalizationService,
)
from substitute.domain.onboarding import InstallationContext
from substitute.domain.workspace_snapshot import WorkspaceSnapshot


class StartupRestoreRuntimeServices(Protocol):
    """Expose runtime repositories needed for initial restore planning."""

    @property
    def session_snapshot_repository(self) -> Any:
        """Return the session snapshot repository."""

    @property
    def restore_projection_cache_repository(self) -> Any:
        """Return the restore projection cache repository."""

    @property
    def execution_runtime(self) -> Any:
        """Return the process execution runtime."""


class StartupRestoreAssetPreloadHandle(Protocol):
    """Preload restored workspace assets for startup lifetime."""

    def start(self) -> None:
        """Start restore asset preloading."""

    def shutdown(self) -> None:
        """Release restore asset preload resources."""


class StartupRestoreResourceRegistry(Protocol):
    """Register restore resources owned for the startup lifetime."""

    def register_workspace_restore_asset_preload(
        self,
        preload: StartupRestoreAssetPreloadHandle,
    ) -> object:
        """Register one restore asset preload handle."""


class StartupRestorePlanService(Protocol):
    """Build one startup restore plan."""

    def build(self) -> InitialWorkspaceRestorePlan:
        """Return one initial workspace restore plan."""


class StartupRestorePlanServiceFactory(Protocol):
    """Create startup restore-plan services."""

    def __call__(
        self,
        *,
        repository: Any,
        normalizer: SnapshotNormalizationService,
        restore_projection_repository: Any,
        restore_projection_target_key: str,
    ) -> StartupRestorePlanService:
        """Create one restore-plan service."""


class _RestoreAssetPreloadExecutionDispatcher:
    """Satisfy runtime completion routing for restore preload fire-and-forget work."""

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Run callbacks directly because restore preload has no GUI completion path."""

        _ = reason
        callback()


@dataclass(frozen=True)
class StartupRestorePlanPreparation:
    """Startup restore plan plus optional preload handle."""

    restore_plan: InitialWorkspaceRestorePlan
    restore_asset_preload: StartupRestoreAssetPreloadHandle | None


def prepare_startup_restore_plan(
    *,
    startup_timer: StartupTimer,
    installation_context: InstallationContext,
    runtime_services: StartupRestoreRuntimeServices,
    startup_resources: StartupRestoreResourceRegistry,
    restore_projection_target_key_for_context: Callable[[InstallationContext], str],
    plan_service_factory: StartupRestorePlanServiceFactory | None = None,
    preload_handle_factory: Callable[
        [WorkspaceSnapshot], StartupRestoreAssetPreloadHandle
    ]
    | None = None,
) -> StartupRestorePlanPreparation:
    """Build the initial restore plan and start image-asset preloading when needed."""

    factory = (
        InitialWorkspaceRestorePlanService
        if plan_service_factory is None
        else plan_service_factory
    )
    with startup_timer.phase("startup.build_initial_restore_plan"):
        restore_plan = factory(
            repository=runtime_services.session_snapshot_repository,
            normalizer=SnapshotNormalizationService(),
            restore_projection_repository=(
                runtime_services.restore_projection_cache_repository
            ),
            restore_projection_target_key=restore_projection_target_key_for_context(
                installation_context
            ),
        ).build()
    startup_timer.mark("restore_plan_built")
    trace_mark(
        "startup.restore_plan.built",
        workspace_present=restore_plan.workspace is not None,
        shell_placement_present=restore_plan.shell_placement is not None,
        workflow_count=restored_workspace_workflow_count(restore_plan.workspace),
        provisional_restore_projection_present=(
            restore_plan.provisional_restore_projection is not None
        ),
    )
    restore_asset_preload = _start_restore_asset_preload(
        workspace=restore_plan.workspace,
        execution_runtime=runtime_services.execution_runtime,
        startup_resources=startup_resources,
        preload_handle_factory=preload_handle_factory,
    )
    return StartupRestorePlanPreparation(
        restore_plan=restore_plan,
        restore_asset_preload=restore_asset_preload,
    )


def _start_restore_asset_preload(
    *,
    workspace: WorkspaceSnapshot | None,
    execution_runtime: Any,
    startup_resources: StartupRestoreResourceRegistry,
    preload_handle_factory: Callable[
        [WorkspaceSnapshot], StartupRestoreAssetPreloadHandle
    ]
    | None,
) -> StartupRestoreAssetPreloadHandle | None:
    """Create, register, and start restore asset preloading when a workspace exists."""

    if workspace is None:
        return None
    restore_asset_preload: StartupRestoreAssetPreloadHandle
    if preload_handle_factory is None:
        submitter = execution_runtime.submitter(
            "disk_io_low_priority",
            owner_id="workspace_restore_asset_preload",
            dispatcher=_RestoreAssetPreloadExecutionDispatcher(),
        )
        restore_asset_preload = WorkspaceRestoreAssetPreloadHandle(
            workspace,
            submitter=submitter,
            close_submitter=submitter.close,
        )
    else:
        restore_asset_preload = preload_handle_factory(workspace)
    startup_resources.register_workspace_restore_asset_preload(restore_asset_preload)
    restore_asset_preload.start()
    return restore_asset_preload


__all__ = [
    "StartupRestorePlanPreparation",
    "prepare_startup_restore_plan",
]
