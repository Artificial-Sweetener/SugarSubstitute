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

"""Concrete startup adapters for managed compatibility recovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityCleanupResultProtocol,
    RecoveryLogCallback,
)
from substitute.application.execution import TaskSubmitter
from substitute.app.bootstrap.managed_target_activation import activate_target
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.comfy_startup_diagnostics.startup_failure_report_service import (
    build_startup_runtime_compatibility_incident,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import InstallationContext
from substitute.domain.onboarding.models import (
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.infrastructure.comfy import process_manager
from substitute.infrastructure.comfy.managed_launcher import ManagedTaskFactory
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationStatus,
)
from substitute.infrastructure.comfy.nodepack_reconciliation import (
    ensure_core_comfy_nodepacks,
    run_sugarcubes_baseline_maintenance,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("app.bootstrap.managed_recovery_adapters")


class ManagedRecoveryOutputStreamProtocol(Protocol):
    """Append managed recovery output to the shell transcript stream."""

    def append_line(self, line: str) -> None:
        """Append one output line."""


class ManagedRecoveryStartupAdapters:
    """Adapt live startup collaborators into managed recovery controller ports."""

    def __init__(
        self,
        *,
        installation_context: InstallationContext,
        splash: Callable[[], LaunchSplashClient | None],
        comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
        startup_diagnostics: ComfyStartupDiagnosticsCollector,
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        launch_task_factory: ManagedTaskFactory,
        process_pump_task_factory: ManagedTaskFactory,
    ) -> None:
        """Store live startup collaborators needed by recovery controller ports."""

        self._installation_context = installation_context
        self._splash = splash
        self._comfy_output_stream = comfy_output_stream
        self._startup_diagnostics = startup_diagnostics
        self._handle_managed_startup_failure = handle_managed_startup_failure
        self._launch_task_factory = launch_task_factory
        self._process_pump_task_factory = process_pump_task_factory

    def append_recovery_message(self, message: str) -> None:
        """Append one managed recovery message to the current splash."""

        splash = self._splash()
        if splash is not None:
            splash.append_log(message)

    def emit_recovery_log(self, line: str) -> None:
        """Forward one managed recovery output line to startup sinks."""

        splash = self._splash()
        if splash is not None:
            try:
                splash.append_log(line)
            except RuntimeError:
                log_warning(_LOGGER, "Dropped recovery splash log after disposal")
        self._comfy_output_stream.append_line(line)

    def handle_recovery_failure(
        self,
        compatibility: BackendCompatibilityResult,
        error: Exception,
    ) -> None:
        """Build and present one managed recovery startup failure incident."""

        self._handle_managed_startup_failure(
            build_startup_runtime_compatibility_incident(
                installation_context=self._installation_context,
                compatibility=compatibility,
                transcript=self._startup_diagnostics.transcript(),
                recovery_attempted=True,
                error=error,
            )
        )

    def relaunch_managed_comfy(self) -> object | None:
        """Relaunch the managed Comfy target after recovery."""

        splash = self._splash()
        assert splash is not None
        return activate_target(
            installation_context=self._installation_context,
            splash=splash,
            comfy_output_stream=self._comfy_output_stream,
            startup_diagnostics=self._startup_diagnostics,
            launch_task_factory=self._launch_task_factory,
            process_pump_task_factory=self._process_pump_task_factory,
        )


@dataclass(frozen=True, slots=True)
class ManagedRecoveryControllerAdapters:
    """Group concrete managed recovery ports consumed by the controller."""

    submitter_factory: Callable[[], TaskSubmitter]
    register_submitter: Callable[[TaskSubmitter], None]
    cleanup_state: Callable[
        [object | None],
        ManagedCompatibilityCleanupResultProtocol,
    ]
    reconcile_owned_comfy_dependencies: Callable[
        [ComfyTargetConfiguration, frozenset[CoreNodepackId], RecoveryLogCallback],
        None,
    ]
    confirmed_termination_status: object


class ManagedRecoverySubmitterResource:
    """Close a managed recovery submitter during startup cleanup."""

    def __init__(self, submitter: TaskSubmitter) -> None:
        """Store the runtime submitter whose dispatcher route is retained."""

        self._submitter = submitter

    def shutdown(self) -> None:
        """Close the runtime submitter when it exposes a close hook."""

        close = getattr(self._submitter, "close", None)
        if callable(close):
            close()


def create_managed_recovery_startup_adapters(
    *,
    installation_context: InstallationContext,
    splash: Callable[[], LaunchSplashClient | None],
    comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
    startup_diagnostics: ComfyStartupDiagnosticsCollector,
    handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
    launch_task_factory: ManagedTaskFactory,
    process_pump_task_factory: ManagedTaskFactory,
) -> ManagedRecoveryStartupAdapters:
    """Create startup-facing managed recovery controller adapters."""

    return ManagedRecoveryStartupAdapters(
        installation_context=installation_context,
        splash=splash,
        comfy_output_stream=comfy_output_stream,
        startup_diagnostics=startup_diagnostics,
        handle_managed_startup_failure=handle_managed_startup_failure,
        launch_task_factory=launch_task_factory,
        process_pump_task_factory=process_pump_task_factory,
    )


def create_managed_recovery_controller_adapters(
    *,
    startup_resources: StartupResourceRegistry,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
) -> ManagedRecoveryControllerAdapters:
    """Create concrete managed recovery controller adapters."""

    return ManagedRecoveryControllerAdapters(
        submitter_factory=lambda: create_managed_recovery_submitter(
            execution_runtime=execution_runtime,
            execution_dispatcher_factory=execution_dispatcher_factory,
        ),
        register_submitter=lambda submitter: register_managed_recovery_submitter(
            startup_resources,
            submitter,
        ),
        cleanup_state=cleanup_managed_recovery_state,
        reconcile_owned_comfy_dependencies=reconcile_owned_comfy_dependencies,
        confirmed_termination_status=confirmed_managed_recovery_termination_status(),
    )


def create_managed_recovery_submitter(
    *,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
) -> TaskSubmitter:
    """Create the startup-lane submitter for managed compatibility recovery."""

    return cast(
        TaskSubmitter,
        cast(Any, execution_runtime).submitter(
            "startup",
            owner_id="managed_compatibility_recovery",
            dispatcher=execution_dispatcher_factory(),
        ),
    )


def register_managed_recovery_submitter(
    startup_resources: StartupResourceRegistry,
    submitter: TaskSubmitter,
) -> None:
    """Register one managed recovery submitter for startup cleanup."""

    startup_resources.register_startup_diagnostics_task(
        ManagedRecoverySubmitterResource(submitter)
    )


def reconcile_owned_comfy_dependencies(
    target: ComfyTargetConfiguration,
    nodepacks: frozenset[CoreNodepackId],
    emit_log: RecoveryLogCallback,
) -> None:
    """Reconcile Substitute-owned Comfy dependencies for one owned local target."""

    workspace = target.workspace_path
    if (
        target.mode is ComfyTargetMode.REMOTE
        or not target.launch_owned
        or workspace is None
    ):
        raise RuntimeError(
            "Owned Comfy dependency reconciliation requires a launch-owned "
            "local workspace."
        )

    if target.mode is ComfyTargetMode.MANAGED_LOCAL:
        reconcile_managed_local_owned_dependencies(workspace, nodepacks, emit_log)
        return

    reconcile_attached_local_owned_dependencies(workspace, nodepacks, emit_log)


def reconcile_managed_local_owned_dependencies(
    workspace: Path,
    nodepacks: frozenset[CoreNodepackId],
    emit_log: RecoveryLogCallback,
) -> None:
    """Run full managed setup when Substitute owns the Comfy installation."""

    ensure_managed_comfy_setup(
        workspace=workspace,
        refresh_core_nodepacks=nodepacks,
        on_status=emit_log,
        on_log=emit_log,
    )


def reconcile_attached_local_owned_dependencies(
    workspace: Path,
    nodepacks: frozenset[CoreNodepackId],
    emit_log: RecoveryLogCallback,
) -> None:
    """Refresh only Substitute-owned nodepacks in an attached local workspace."""

    emit_log("Updating Substitute Comfy nodepacks.")
    ensure_core_comfy_nodepacks(
        workspace,
        refresh_nodepacks=nodepacks,
        on_log=emit_log,
    )
    emit_log("Preparing Base-Cubes dependencies.")
    run_sugarcubes_baseline_maintenance(
        workspace,
        on_log=emit_log,
    )


def cleanup_managed_recovery_state(
    state: object | None,
) -> ManagedCompatibilityCleanupResultProtocol:
    """Clean one managed Comfy state through the infrastructure adapter."""

    managed_state = cast(process_manager.ManagedComfyState | None, state)
    if managed_state is None:
        return process_manager.kill_comfyui_state(None)
    return managed_state.with_spawn_lock(
        lambda: process_manager.kill_comfyui_state(managed_state)
    )


def confirmed_managed_recovery_termination_status() -> object:
    """Return the infrastructure status that proves managed cleanup completed."""

    return ManagedProcessTerminationStatus.TERMINATED_CONFIRMED


__all__ = [
    "ManagedRecoveryControllerAdapters",
    "ManagedRecoveryOutputStreamProtocol",
    "ManagedRecoverySubmitterResource",
    "ManagedRecoveryStartupAdapters",
    "cleanup_managed_recovery_state",
    "confirmed_managed_recovery_termination_status",
    "create_managed_recovery_controller_adapters",
    "create_managed_recovery_startup_adapters",
    "create_managed_recovery_submitter",
    "reconcile_attached_local_owned_dependencies",
    "reconcile_managed_local_owned_dependencies",
    "reconcile_owned_comfy_dependencies",
    "register_managed_recovery_submitter",
]
