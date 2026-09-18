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

"""Launch managed-local Comfy workspaces in foreground or background."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
import os
from pathlib import Path
from typing import IO, Callable

from substitute.application.comfy_startup_diagnostics.startup_failure_report_service import (
    build_startup_launch_exception_incident,
)
from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
)
from substitute.domain.onboarding import ManagedRuntimeLaunchStatus
from substitute.domain.comfy_manager import ComfyManagerKind
from substitute.infrastructure.comfy.managed_install import (
    emit_log,
    emit_status,
)
from substitute.infrastructure.comfy.managed_launch_command import (
    build_managed_launch_command,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
    build_launch_request,
    launch_managed_process,
)
from substitute.infrastructure.comfy.manager_runtime_probe import (
    detect_workspace_manager_runtime,
)
from substitute.infrastructure.comfy.manager_environment import (
    manager_runtime_environment,
)
from substitute.infrastructure.comfy.managed_runtime_selection_policy import (
    HardwareAwareManagedRuntimeSelectionPolicy,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
    ProgressCallback,
    wait_for_managed_startup_ready,
)
from substitute.infrastructure.comfy.managed_termination_result import (
    ManagedProcessTerminationStatus,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    kill_managed_comfy_metadata,
)
from substitute.infrastructure.comfy.managed_validation import (
    workspace_main_path,
    workspace_python_path,
)
from substitute.shared.startup_trace import trace_mark, trace_span
from substitute.infrastructure.onboarding.file_managed_runtime_repository import (
    FileManagedRuntimeConfigurationRepository,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
)
from sugarsubstitute_shared.windows_long_paths import operational_path

from substitute.infrastructure.comfy.managed_process_state import (
    ManagedComfyState,
    ManagedTaskFactory,
)
from substitute.infrastructure.comfy.managed_output_pump import start_output_pump_task

from substitute.infrastructure.comfy.managed_listener_adoption import (
    resolve_managed_listener,
)

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.managed_launcher")
_MANAGED_LAUNCH_REQUEST_IDS = count(1)


def start_managed_comfy_subprocess(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    runtime_state_dir: Path,
    python_executable: Path | None = None,
) -> ManagedProcessHandle:
    """Launch a foreground Comfy subprocess from an installed workspace."""

    workspace = operational_path(workspace)
    runtime_state_dir = operational_path(runtime_state_dir)
    if python_executable is not None:
        python_executable = operational_path(python_executable)
    registry = ManagedProcessRegistry(runtime_state_dir)
    runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(runtime_state_dir),
        selection_policy=HardwareAwareManagedRuntimeSelectionPolicy(),
    )
    resolve_managed_listener(
        endpoint=endpoint,
        workspace=workspace,
        registry=registry,
        runtime_service=runtime_service,
    )
    venv_python = _resolve_launch_python(
        workspace=workspace,
        python_executable=python_executable,
    )
    manager_runtime = detect_workspace_manager_runtime(
        workspace,
        python_executable=venv_python,
    )
    env = os.environ.copy()
    if manager_runtime.kind is ComfyManagerKind.INTEGRATED:
        env = manager_runtime_environment(
            workspace,
            env,
            use_pygit2=manager_runtime.uses_pygit2,
        )
    env["PATH"] = str(venv_python.parent) + os.pathsep + env.get("PATH", "")
    env["SUGARSUBSTITUTE_SKIP_TTS_INSTALLER"] = "1"
    launch_result = launch_managed_process(
        endpoint=endpoint,
        workspace=workspace,
        request=build_launch_request(
            command=build_managed_launch_command(
                venv_python=venv_python,
                endpoint=endpoint,
                workspace=workspace,
                manager_runtime=manager_runtime,
                force_cpu_mode=_managed_force_cpu_mode(runtime_service),
            ),
            cwd=workspace,
            env=env,
            capture_output=False,
        ),
    )
    return launch_result.process


def _resolve_launch_python(
    *,
    workspace: Path,
    python_executable: Path | None,
) -> Path:
    """Return installed launch artifacts without reconciling or mutating them."""

    entrypoint = workspace_main_path(workspace)
    resolved_python = python_executable or workspace_python_path(workspace)
    for required_path in (entrypoint, resolved_python):
        if not required_path.is_file():
            raise FileNotFoundError(required_path)
    return resolved_python


def start_managed_comfy_background(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    runtime_state_dir: Path,
    on_log: LogCallback | None = None,
    on_status: StatusCallback | None = None,
    on_progress: ProgressCallback | None = None,
    diagnostics: ComfyStartupDiagnosticsCollector | None = None,
    launch_task_factory: ManagedTaskFactory,
    process_pump_task_factory: ManagedTaskFactory,
    python_executable: Path | None = None,
) -> ManagedComfyState:
    """Launch ComfyUI through the managed execution layer."""

    workspace = operational_path(workspace)
    runtime_state_dir = operational_path(runtime_state_dir)
    if python_executable is not None:
        python_executable = operational_path(python_executable)
    registry = ManagedProcessRegistry(runtime_state_dir)
    runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(runtime_state_dir),
        selection_policy=HardwareAwareManagedRuntimeSelectionPolicy(),
    )
    state = ManagedComfyState(registry=registry)
    request_id = next(_MANAGED_LAUNCH_REQUEST_IDS)

    def run_startup(cancellation: CancellationSource) -> None:
        """Run managed startup work on the supplied execution task."""

        trace_mark("managed_comfy.startup_task.start", request_id=request_id)
        try:
            if cancellation.is_cancelled or state.stop_requested:
                return
            with trace_span("managed_comfy.resolve_listener"):
                existing_metadata = resolve_managed_listener(
                    endpoint=endpoint,
                    workspace=workspace,
                    registry=registry,
                    runtime_service=runtime_service,
                )
            if existing_metadata is not None:
                state.record_reused_metadata(existing_metadata)
                state.record_startup_result(ManagedStartupReadinessResult(ready=True))
                runtime_service.record_launch(
                    status=ManagedRuntimeLaunchStatus.REUSED_OWNED,
                    detail="Reused the existing healthy owned managed ComfyUI listener.",
                )
                emit_status(on_status, "Reusing the existing managed ComfyUI instance.")
                trace_mark(
                    "managed_comfy.reused_existing_listener",
                    request_id=request_id,
                    pid=existing_metadata.pid,
                )
                return

            with trace_span("managed_comfy.resolve_launch_workspace"):
                venv_python = _resolve_launch_python(
                    workspace=workspace,
                    python_executable=python_executable,
                )
            manager_runtime = detect_workspace_manager_runtime(
                workspace,
                python_executable=venv_python,
            )
            if cancellation.is_cancelled or state.stop_requested:
                emit_log(on_log, "[INFO] ComfyUI launch canceled before start.")
                trace_mark(
                    "managed_comfy.launch.skip",
                    reason="cancelled_before_start",
                    request_id=request_id,
                )
                return

            env = os.environ.copy()
            if manager_runtime.kind is ComfyManagerKind.INTEGRATED:
                env = manager_runtime_environment(
                    workspace,
                    env,
                    use_pygit2=manager_runtime.uses_pygit2,
                )
            env["PATH"] = str(venv_python.parent) + os.pathsep + env.get("PATH", "")
            env["PYTHONIOENCODING"] = "utf-8"
            env["SUGARSUBSTITUTE_SKIP_TTS_INSTALLER"] = "1"
            emit_status(on_status, "Launching ComfyUI.")
            stdout_stream: IO[bytes] | None = None
            with trace_span("managed_comfy.launch_process"):
                launch_result = launch_managed_process(
                    endpoint=endpoint,
                    workspace=workspace,
                    request=build_launch_request(
                        command=build_managed_launch_command(
                            venv_python=venv_python,
                            endpoint=endpoint,
                            workspace=workspace,
                            manager_runtime=manager_runtime,
                            force_cpu_mode=_managed_force_cpu_mode(runtime_service),
                        ),
                        cwd=workspace,
                        env=env,
                        capture_output=True,
                    ),
                )
            trace_mark(
                "managed_comfy.process_launched",
                request_id=request_id,
                pid=launch_result.metadata.pid,
            )
            if not state.record_launch_result_if_running(
                launch_result,
                registry=registry,
            ):
                _terminate_launch_result(launch_result, registry=registry)
                trace_mark(
                    "managed_comfy.launch.discarded",
                    reason="stop_requested",
                    request_id=request_id,
                )
                return
            stdout_stream = launch_result.stdout_stream

            if on_log is not None and stdout_stream is not None:
                state.add_process_pump(
                    start_output_pump_task(
                        request_id=next(_MANAGED_LAUNCH_REQUEST_IDS),
                        task_factory=process_pump_task_factory,
                        stdout_stream=stdout_stream,
                        on_log=on_log,
                    )
                )

            if cancellation.is_cancelled or state.stop_requested:
                termination = kill_managed_comfy_metadata(
                    state.metadata,
                    containment_handle=state.containment_handle,
                )
                if (
                    termination.status
                    is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
                    and state.metadata is not None
                ):
                    registry.clear_if_pid_matches(state.metadata.pid)
                trace_mark(
                    "managed_comfy.launch.cancelled_after_spawn",
                    request_id=request_id,
                )
                return
            with trace_span("managed_comfy.wait_ready"):
                startup_result = wait_for_managed_startup_ready(
                    host=endpoint.host,
                    port=endpoint.port,
                    process=launch_result.process,
                    workspace=workspace,
                    on_progress=on_progress,
                    cancellation=cancellation,
                    diagnostics=diagnostics,
                )
            state.record_startup_result(startup_result)
            trace_mark(
                "managed_comfy.wait_ready.result",
                request_id=request_id,
                ready=startup_result.ready,
                fatal_incident=startup_result.fatal_incident is not None,
            )
            if startup_result.ready:
                state.record_validated_metadata(
                    registry.update_validation_timestamp(_timestamp_now())
                )
                runtime_service.record_launch(
                    status=ManagedRuntimeLaunchStatus.READY,
                    detail="Managed ComfyUI launched and passed readiness checks.",
                )
            elif startup_result.fatal_incident is not None:
                runtime_service.record_launch(
                    status=ManagedRuntimeLaunchStatus.FAILED,
                    detail=startup_result.fatal_incident.message,
                )
                emit_log(on_log, f"[ERROR] {startup_result.fatal_incident.message}")
        except Exception as error:
            state.record_startup_result(
                ManagedStartupReadinessResult(ready=False, canceled=True)
                if cancellation.is_cancelled or state.stop_requested
                else ManagedStartupReadinessResult(
                    ready=False,
                    fatal_incident=build_startup_launch_exception_incident(
                        workspace=str(workspace), error=error
                    ),
                )
            )
            runtime_service.record_launch(
                status=ManagedRuntimeLaunchStatus.FAILED,
                detail=str(error).strip() or type(error).__name__,
            )
            emit_log(on_log, f"[ERROR] {error}")
            log_exception(
                _LOGGER,
                "Managed ComfyUI startup failed",
                error_type=type(error).__name__,
            )

        finally:
            if state.startup_result is None and (
                cancellation.is_cancelled or state.stop_requested
            ):
                state.record_startup_result(
                    ManagedStartupReadinessResult(ready=False, canceled=True)
                )

    state.set_launch_task(
        launch_task_factory(
            TaskIdentity(
                request_id=request_id,
                domain="managed_comfy_startup",
            ),
            ExecutionContext(
                operation="managed_comfy_startup",
                reason="managed_target_activation",
                lane="process_pump",
            ),
            run_startup,
            "substitute-managed-comfy-startup",
        )
    )
    return state


def _terminate_launch_result(
    launch_result: object,
    *,
    registry: ManagedProcessRegistry,
) -> None:
    """Terminate a process that was launched after cancellation was requested."""

    metadata = getattr(launch_result, "metadata")
    termination = kill_managed_comfy_metadata(
        metadata,
        containment_handle=getattr(launch_result, "containment_handle"),
    )
    if termination.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED:
        registry.clear_if_pid_matches(metadata.pid)


def _timestamp_now() -> str:
    """Return one UTC ISO timestamp for managed runtime metadata."""

    return datetime.now(UTC).isoformat()


def _managed_force_cpu_mode(runtime_service: ManagedRuntimeService) -> bool:
    """Return whether the active managed runtime requires ComfyUI CPU mode."""

    configuration = runtime_service.load_persisted()
    return configuration.force_cpu_mode if configuration is not None else False
