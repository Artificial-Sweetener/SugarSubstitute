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

"""Provide typed ports and clocks for launch-assembly tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellBuildTask,
    ReadyShellInitialWorkspacePrehydrationTask,
    ReadyShellMetadataBridgeTask,
    ReadyShellMinimumReadyTask,
    ReadyShellPromptEditorWarmupTask,
    ReadyShellTargetActivationTask,
)
from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTaskQueueProtocol,
)
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedCompatibilityRecoveryBridgeProtocol,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupRuntimeCompatibilityCheckerProtocol,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)


def _ports() -> StartupManagedReadyFactoryPorts:
    """Create inert managed-ready ports for launch assembly tests."""

    failure_incident = cast(ComfyStartupIncident, object())
    compatibility_checker = cast(
        StartupRuntimeCompatibilityCheckerProtocol,
        _CompatibilityChecker(),
    )

    return StartupManagedReadyFactoryPorts(
        create_startup_diagnostics_collector=ComfyStartupDiagnosticsCollector,
        create_startup_diagnostics_ignore_repository=lambda _context: cast(
            StartupDiagnosticsIgnoreRepository,
            object(),
        ),
        create_runtime_compatibility_checker=lambda: compatibility_checker,
        create_managed_compatibility_recovery_bridge=lambda: cast(
            StartupManagedCompatibilityRecoveryBridgeProtocol,
            _RecoveryBridge(),
        ),
        create_model_metadata_update_bridge=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            object(),
        ),
        request_startup_diagnostics_titlebar_update=lambda **_kwargs: True,
        activate_target=lambda **_kwargs: object(),
        managed_startup_fatal_incident=lambda _state: failure_incident,
        present_startup_failure_report=lambda _report: None,
        build_startup_failure_report=lambda **_kwargs: object(),
        build_startup_readiness_timeout_incident=lambda **_kwargs: failure_incident,
        build_startup_runtime_compatibility_incident=lambda **_kwargs: failure_incident,
    )


def _context(tmp_path: Path) -> InstallationContext:
    """Build one managed-ready installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=True,
        ),
    )


class _CompatibilityChecker:
    """Accept compatibility checks requested by runtime resources."""

    def assess_target(self, _target: object) -> object:
        """Return an inert compatibility result."""

        return object()


class _Signal:
    """Expose the Qt-compatible signal methods used by startup bridges."""

    def connect(self, _callback: object) -> object:
        """Return one inert connection token."""

        return object()

    def emit(self, *_args: object) -> None:
        """Accept emitted bridge payloads."""


class _RecoveryBridge:
    """Expose a recovery completion signal."""

    def __init__(self) -> None:
        """Create the finished signal."""

        self.finished = _Signal()


class _StartupTaskScheduleRuntime:
    """Record the readiness timer callback passed to the lower-level scheduler."""

    def __init__(self) -> None:
        """Initialize the recorded callback slot."""

        self.start_readiness_timer: Callable[[], None] | None = None

    def schedule_startup_tasks(
        self,
        *,
        queue: ReadyShellStartupTaskQueueProtocol,
        target_activation_task: ReadyShellTargetActivationTask,
        start_readiness_timer: Callable[[], None],
        shell_build_task: ReadyShellBuildTask,
        metadata_bridge_task: ReadyShellMetadataBridgeTask,
        prompt_editor_warmup_task: ReadyShellPromptEditorWarmupTask,
        initial_workspace_prehydration_task: ReadyShellInitialWorkspacePrehydrationTask,
        minimum_shell_ready_task: ReadyShellMinimumReadyTask,
    ) -> None:
        """Store the callback delegated by the launch runtime."""

        self.start_readiness_timer = start_readiness_timer


class _Clock:
    """Return monotonically increasing timestamps for deterministic timing."""

    def __init__(self) -> None:
        """Initialize the fake clock."""

        self._now = 0.0

    def __call__(self) -> float:
        """Return the next fake timestamp."""

        self._now += 0.1
        return self._now
