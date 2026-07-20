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

"""Define process-lifetime application runtime service bundles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import count

from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.appearance_runtime import AppearanceRuntimeController
from substitute.app.bootstrap.localization_composition import (
    ComfyNodeLocalizationRuntime,
    build_comfy_node_localization_runtime,
)
from substitute.application.appearance import ActiveAppearanceBaseline
from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.ports import SessionSnapshotRepository
from substitute.application.workspace_state import (
    RestoreProjectionCacheRepository,
    SessionAutosaveService,
    SnapshotCaptureService,
)
from substitute.domain.onboarding import InstallationContext
from substitute.infrastructure.persistence import (
    FileRestoreProjectionCacheRepository,
    FileSessionSnapshotRepository,
)
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher, QtUiScheduler
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.localization import TranslationManager


@dataclass(frozen=True, slots=True)
class ApplicationRuntimeServices:
    """Store long-lived services shared by disposable shell instances."""

    context: InstallationContext
    comfy_output_stream: TerminalOutputStream
    localization_manager: TranslationManager
    comfy_node_localization: ComfyNodeLocalizationRuntime
    appearance_runtime: AppearanceRuntimeController
    active_appearance_baseline: ActiveAppearanceBaseline
    session_snapshot_repository: SessionSnapshotRepository
    restore_projection_cache_repository: RestoreProjectionCacheRepository
    session_autosave_service: SessionAutosaveService
    execution_runtime: ExecutionRuntime


def build_application_runtime_services(
    *,
    context: InstallationContext,
    comfy_output_stream: TerminalOutputStream,
    localization_manager: TranslationManager,
    appearance_runtime: AppearanceRuntimeController,
) -> ApplicationRuntimeServices:
    """Compose process-lifetime services available to shell construction."""

    session_snapshot_repository = FileSessionSnapshotRepository(context.session_dir)
    restore_projection_cache_repository = FileRestoreProjectionCacheRepository(
        context.cache_dir
    )
    execution_runtime = ExecutionRuntime()
    qt_owner = _application_qt_owner()
    comfy_catalog_submitter = execution_runtime.submitter(
        "node_definition",
        owner_id="comfy_node_localization",
        dispatcher=QtOwnerThreadDispatcher(qt_owner),
    )
    comfy_catalog_scheduler = _ComfyNodeLocalizationRefreshScheduler(
        comfy_catalog_submitter
    )
    comfy_node_localization = build_comfy_node_localization_runtime(
        qt_owner,
        manager=localization_manager,
        endpoint=context.comfy_target.endpoint,
        cache_root=context.cache_dir,
        background_scheduler=comfy_catalog_scheduler.schedule,
    )
    autosave_scheduler = QtUiScheduler(qt_owner)
    session_autosave_submitter = execution_runtime.submitter(
        "disk_io_low_priority",
        owner_id="session_autosave",
        dispatcher=QtOwnerThreadDispatcher(qt_owner),
    )
    session_autosave_persistence = _SessionAutosavePersistenceScheduler(
        session_autosave_submitter
    )
    return ApplicationRuntimeServices(
        context=context,
        comfy_output_stream=comfy_output_stream,
        localization_manager=localization_manager,
        comfy_node_localization=comfy_node_localization,
        appearance_runtime=appearance_runtime,
        active_appearance_baseline=ActiveAppearanceBaseline(
            appearance_runtime.load_preferences()
        ),
        session_snapshot_repository=session_snapshot_repository,
        restore_projection_cache_repository=restore_projection_cache_repository,
        session_autosave_service=SessionAutosaveService(
            capture_service=SnapshotCaptureService(),
            repository=session_snapshot_repository,
            schedule_debounced=lambda callback: autosave_scheduler.schedule(
                500,
                callback,
                reason="session_autosave_debounce",
            ),
            schedule_persistence=session_autosave_persistence.schedule,
        ),
        execution_runtime=execution_runtime,
    )


def _application_qt_owner() -> QApplication:
    """Return the process QApplication used for runtime Qt execution adapters."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("QApplication is required before runtime services.")
    return app


class _SessionAutosavePersistenceScheduler:
    """Schedule captured session snapshots on the low-priority disk lane."""

    def __init__(self, submitter: TaskSubmitter) -> None:
        """Store autosave execution dependencies."""

        self._scope = TaskScope(
            submitter=submitter,
            scope_id="session_autosave_persistence",
        )
        self._request_ids = count(1)

    def schedule(self, callback: Callable[[], None]) -> None:
        """Submit one captured autosave persistence callback."""

        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._request_ids),
                domain="session_autosave_persistence",
            ),
            context=ExecutionContext(
                operation="session_autosave_persistence",
                reason="session_autosave",
                lane="disk_io_low_priority",
            ),
            work=lambda _token: callback(),
        )
        self._scope.submit(request)


class _ComfyNodeLocalizationRefreshScheduler:
    """Schedule process-lifetime Comfy localization refreshes on its owned lane."""

    def __init__(self, submitter: TaskSubmitter) -> None:
        """Store the execution scope and deterministic request sequence."""

        self._scope = TaskScope(
            submitter=submitter,
            scope_id="comfy_node_localization_refresh",
        )
        self._request_ids = count(1)

    def schedule(self, callback: Callable[[], None]) -> object:
        """Submit one bounded custom-node catalog refresh."""

        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._request_ids),
                domain="comfy_node_localization_refresh",
            ),
            context=ExecutionContext(
                operation="refresh_comfy_node_localization",
                reason="localization_generation_changed",
                lane="node_definition",
            ),
            work=lambda _token: callback(),
        )
        return self._scope.submit(request)


__all__ = [
    "ApplicationRuntimeServices",
    "build_application_runtime_services",
]
