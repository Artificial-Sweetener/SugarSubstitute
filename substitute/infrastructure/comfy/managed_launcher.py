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

from collections.abc import Iterator
from codecs import getincrementaldecoder
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
import os
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4
from typing import IO, Callable, Protocol, TypeVar

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
from substitute.application.onboarding.managed_runtime_state_recorder import (
    ActiveSafeManagedRuntimeStateRecorder,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
)
from substitute.domain.onboarding import ManagedRuntimeLaunchStatus
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)
from substitute.infrastructure.comfy.managed_install import (
    emit_log,
    emit_status,
    ensure_managed_comfy_setup,
)
from substitute.infrastructure.comfy.attached_install import (
    prepare_attached_comfy_setup,
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
from substitute.infrastructure.comfy.managed_process_metadata import (
    ContainmentMode,
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerStatus,
    probe_managed_listener,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
    ProgressCallback,
    wait_for_managed_startup_ready,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationStatus,
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
from substitute.infrastructure.onboarding.file_setup_transaction_repository import (
    FileSetupTransactionRepository,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_error,
    log_info,
    log_warning_exception,
)
from sugarsubstitute_shared.windows_long_paths import (
    exceeds_windows_legacy_path_limit,
    operational_path,
    subprocess_path,
)

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]
TResult = TypeVar("TResult")
LongLivedWork = Callable[[CancellationSource], TResult]

_LOGGER = get_logger("infrastructure.comfy.managed_launcher")
_MANAGED_LAUNCH_REQUEST_IDS = count(1)
_STARTUP_HARNESS_ENV = "SUGAR_SUBSTITUTE_STARTUP_HARNESS"
_LONG_WORKSPACE_BOOTSTRAP = (
    "import os, runpy, sys; "
    "root = sys.argv.pop(1); script = sys.argv.pop(1); "
    "os.chdir(root); sys.argv[0] = script; "
    "runpy.run_path(script, run_name='__main__')"
)


class ManagedLongLivedTaskHandle(Protocol):
    """Describe the task lifecycle handle used by managed process startup."""

    @property
    def is_finished(self) -> bool:
        """Return whether the task has reached a terminal state."""

    def stop(self, *, reason: str) -> None:
        """Request task cancellation."""


ManagedTaskFactory = Callable[
    [TaskIdentity, ExecutionContext, LongLivedWork[None], str],
    ManagedLongLivedTaskHandle,
]


class ManagedComfyState:
    """Track managed background ComfyUI process startup state."""

    def __init__(self, *, registry: ManagedProcessRegistry) -> None:
        """Initialize mutable managed process state."""

        self.proc: ManagedProcessHandle | None = None
        self.registry = registry
        self.metadata: ManagedProcessMetadata | None = None
        self.containment_handle: object | None = None
        self.containment_mode: ContainmentMode | None = None
        self.startup_result: ManagedStartupReadinessResult | None = None
        self.launch_task: ManagedLongLivedTaskHandle | None = None
        self._process_pumps: list[ManagedLongLivedTaskHandle] = []
        self._stop_requested = False
        self._spawn_lock = Lock()
        self._state_lock = Lock()

    @property
    def stop_requested(self) -> bool:
        """Return whether lifecycle shutdown has been requested."""

        with self._state_lock:
            return self._stop_requested

    @property
    def is_finished(self) -> bool:
        """Return whether the startup task has finished."""

        task = self.launch_task
        return task is not None and task.is_finished

    def request_stop(self, *, reason: str) -> None:
        """Request startup cancellation without closing process-owned output."""

        with self._state_lock:
            self._stop_requested = True
            launch_task = self.launch_task
        if launch_task is not None:
            launch_task.stop(reason=reason)

    def wait_until_finished(self, *, timeout: float) -> None:
        """Wait briefly for the startup task when the handle exposes waiting."""

        task = self.launch_task
        if task is None:
            return
        join = getattr(task, "join", None)
        if callable(join):
            join(timeout=timeout)
            return
        wait = getattr(task, "wait", None)
        if callable(wait):
            wait(timeout=timeout)
            return

    def set_launch_task(self, task: ManagedLongLivedTaskHandle) -> None:
        """Store the task that owns managed startup execution."""

        with self._state_lock:
            self.launch_task = task

    def add_process_pump(self, task: ManagedLongLivedTaskHandle) -> None:
        """Store one task that pumps managed process output."""

        with self._state_lock:
            self._process_pumps.append(task)

    def record_reused_metadata(self, metadata: ManagedProcessMetadata) -> None:
        """Record metadata for a reused owned listener."""

        with self._state_lock:
            self.metadata = metadata
            self.containment_mode = metadata.containment_mode

    def record_startup_result(self, result: ManagedStartupReadinessResult) -> None:
        """Record managed startup readiness output."""

        with self._state_lock:
            self.startup_result = result

    def record_validated_metadata(
        self,
        metadata: ManagedProcessMetadata | None,
    ) -> None:
        """Record refreshed metadata after readiness validation."""

        with self._state_lock:
            self.metadata = metadata

    def with_spawn_lock(self, action: Callable[[], TResult]) -> TResult:
        """Run an action after any in-flight process spawn has quiesced."""

        with self._spawn_lock:
            return action()

    def record_launch_result_if_running(
        self,
        launch_result: object,
        *,
        registry: ManagedProcessRegistry,
    ) -> bool:
        """Record one newly launched process unless shutdown was requested."""

        with self._spawn_lock:
            if self.stop_requested:
                return False
            process = getattr(launch_result, "process")
            metadata = getattr(launch_result, "metadata")
            self.proc = process
            self.containment_handle = getattr(launch_result, "containment_handle")
            self.metadata = registry.save(metadata)
            self.containment_mode = metadata.containment_mode
            return True


def start_managed_comfy_subprocess(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    runtime_state_dir: Path,
    python_executable: Path | None = None,
) -> ManagedProcessHandle:
    """Ensure setup and launch a foreground managed Comfy subprocess."""

    workspace = operational_path(workspace)
    runtime_state_dir = operational_path(runtime_state_dir)
    if python_executable is not None:
        python_executable = operational_path(python_executable)
    registry = ManagedProcessRegistry(runtime_state_dir)
    runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(runtime_state_dir),
        selection_policy=HardwareAwareManagedRuntimeSelectionPolicy(),
    )
    _resolve_listener_state(
        endpoint=endpoint,
        workspace=workspace,
        registry=registry,
        runtime_service=runtime_service,
    )
    startup_transaction = (
        None
        if python_executable is not None
        else _begin_startup_revalidation_transaction_if_needed(
            endpoint=endpoint,
            workspace=workspace,
            runtime_state_dir=runtime_state_dir,
            runtime_service=runtime_service,
        )
    )
    try:
        venv_python = _ensure_launch_workspace(
            workspace=workspace,
            python_executable=python_executable,
            runtime_state_dir=runtime_state_dir,
            transaction_key=f"foreground-{uuid4().hex}",
            runtime_service=runtime_service,
        )
    except Exception as error:
        _fail_startup_revalidation_transaction(startup_transaction, error)
        raise
    _finish_startup_revalidation_transaction(startup_transaction)
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
            command=_build_managed_launch_command(
                venv_python=venv_python,
                endpoint=endpoint,
                workspace=workspace,
                manager_runtime=manager_runtime,
            ),
            cwd=workspace,
            env=env,
            capture_output=False,
        ),
    )
    return launch_result.process


def _ensure_launch_workspace(
    *,
    workspace: Path,
    python_executable: Path | None,
    runtime_state_dir: Path,
    transaction_key: str,
    runtime_service: ManagedRuntimeService,
    on_status: StatusCallback | None = None,
    on_log: LogCallback | None = None,
) -> Path:
    """Prepare managed or attached workspace through its authoritative owner."""

    if python_executable is not None:
        return prepare_attached_comfy_setup(
            workspace=workspace,
            python_executable=python_executable,
            on_status=on_status,
            on_log=on_log,
        ).executable
    return ensure_managed_comfy_setup(
        workspace=workspace,
        installer_temp_root=(
            runtime_state_dir / "installer-temp" / "managed-comfy" / transaction_key
        ),
        on_status=on_status,
        on_log=on_log,
        state_recorder=ActiveSafeManagedRuntimeStateRecorder(runtime_service),
    )


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

        startup_transaction: _StartupRevalidationTransaction | None = None
        trace_mark("managed_comfy.startup_task.start", request_id=request_id)
        try:
            with trace_span("managed_comfy.resolve_listener"):
                existing_metadata = _resolve_listener_state(
                    endpoint=endpoint,
                    workspace=workspace,
                    registry=registry,
                    runtime_service=runtime_service,
                )
            if existing_metadata is not None:
                state.record_reused_metadata(existing_metadata)
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

            with trace_span("managed_comfy.startup_revalidation.begin"):
                if python_executable is None:
                    startup_transaction = (
                        _begin_startup_revalidation_transaction_if_needed(
                            endpoint=endpoint,
                            workspace=workspace,
                            runtime_state_dir=runtime_state_dir,
                            runtime_service=runtime_service,
                        )
                    )
            with trace_span("managed_comfy.ensure_setup"):
                venv_python = _ensure_launch_workspace(
                    workspace=workspace,
                    python_executable=python_executable,
                    runtime_state_dir=runtime_state_dir,
                    transaction_key=f"background-{uuid4().hex}",
                    runtime_service=runtime_service,
                    on_status=on_status,
                    on_log=on_log,
                )
            with trace_span("managed_comfy.startup_revalidation.finish"):
                _finish_startup_revalidation_transaction(startup_transaction)
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
                        command=_build_managed_launch_command(
                            venv_python=venv_python,
                            endpoint=endpoint,
                            workspace=workspace,
                            manager_runtime=manager_runtime,
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
                    _start_output_pump_task(
                        state=state,
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
            _fail_startup_revalidation_transaction(startup_transaction, error)
            runtime_service.record_launch(
                status=ManagedRuntimeLaunchStatus.FAILED,
                detail=str(error).strip() or type(error).__name__,
            )
            emit_log(on_log, f"[ERROR] {error}")
            log_error(_LOGGER, "Managed ComfyUI startup failed", error=error)

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


def _start_output_pump_task(
    *,
    state: ManagedComfyState,
    request_id: int,
    task_factory: ManagedTaskFactory,
    stdout_stream: IO[bytes],
    on_log: LogCallback,
) -> ManagedLongLivedTaskHandle:
    """Start one process-pump task for managed Comfy output."""

    def pump_output(cancellation: CancellationSource) -> None:
        """Forward ComfyUI output records into the provided log callback."""

        record_count = 0
        max_on_log_ms = 0.0
        total_on_log_ms = 0.0
        started_at = perf_counter()
        try:
            for record in _iter_output_records(stdout_stream):
                if cancellation.is_cancelled:
                    return
                record_count += 1
                on_log_started_at = perf_counter()
                _emit_process_output_record(
                    on_log=on_log,
                    record=record,
                    request_id=request_id,
                    record_count=record_count,
                    diagnostic=False,
                )
                on_log_ms = (perf_counter() - on_log_started_at) * 1000.0
                total_on_log_ms += on_log_ms
                max_on_log_ms = max(max_on_log_ms, on_log_ms)
        finally:
            try:
                if _managed_output_pump_diagnostics_enabled() and record_count:
                    _emit_process_output_record(
                        on_log=on_log,
                        record=(
                            "Substitute startup diagnostic "
                            "event=managed_output_pump_timing "
                            f"total_duration_ms="
                            f"{round((perf_counter() - started_at) * 1000.0, 3)} "
                            f"record_count={record_count} "
                            f"total_on_log_ms={round(total_on_log_ms, 3)} "
                            f"max_on_log_ms={round(max_on_log_ms, 3)}"
                        ),
                        request_id=request_id,
                        record_count=record_count,
                        diagnostic=True,
                    )
            finally:
                stdout_stream.close()

    return task_factory(
        TaskIdentity(
            request_id=request_id,
            domain="managed_comfy_output_pump",
        ),
        ExecutionContext(
            operation="managed_comfy_output_pump",
            reason="managed_process_output",
            lane="process_pump",
        ),
        pump_output,
        "substitute-managed-comfy-output-pump",
    )


def _emit_process_output_record(
    *,
    on_log: LogCallback,
    record: str,
    request_id: int,
    record_count: int,
    diagnostic: bool,
) -> None:
    """Forward one process-output record without letting consumers stop pipe drain."""

    try:
        on_log(record)
    except Exception as error:
        log_warning_exception(
            _LOGGER,
            "Managed Comfy output consumer failed; continuing pipe drain",
            error=error,
            request_id=request_id,
            record_count=record_count,
            diagnostic=diagnostic,
        )


def _managed_output_pump_diagnostics_enabled() -> bool:
    """Return whether harness output-pump diagnostics should be emitted."""

    return os.environ.get(_STARTUP_HARNESS_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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


def _managed_runtime_claims_workspace(
    configuration: ManagedRuntimeConfiguration,
    workspace: Path,
) -> bool:
    """Return whether active managed state claims the configured workspace."""

    if configuration.workspace_path is None:
        return configuration.validation_status is ManagedRuntimeValidationStatus.VALID
    try:
        claimed_workspace = Path(configuration.workspace_path).resolve()
        configured_workspace = workspace.resolve()
    except OSError:
        claimed_workspace = Path(configuration.workspace_path)
        configured_workspace = workspace
    return claimed_workspace == configured_workspace


@dataclass(frozen=True)
class _StartupRevalidationTransaction:
    """Track one pending startup revalidation file created by the launcher."""

    repository: FileSetupTransactionRepository
    transaction_id: str


def _begin_startup_revalidation_transaction_if_needed(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    runtime_state_dir: Path,
    runtime_service: ManagedRuntimeService,
) -> _StartupRevalidationTransaction | None:
    """Create pending startup revalidation state when setup work is required."""

    managed_runtime = runtime_service.load_persisted()
    if (
        workspace.exists()
        and workspace_main_path(workspace).exists()
        and workspace_python_path(workspace).exists()
        and managed_runtime is not None
        and _managed_runtime_claims_workspace(managed_runtime, workspace)
    ):
        return None
    repository = FileSetupTransactionRepository(runtime_state_dir)
    now = datetime.now(UTC)
    transaction = SetupTransaction(
        schema_version=1,
        transaction_id=str(uuid4()),
        mode=SetupTransactionMode.STARTUP_REVALIDATION,
        status=SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING,
        created_at=now,
        updated_at=now,
        target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=endpoint,
            workspace_path=workspace,
            install_owned=True,
            launch_owned=True,
        ),
        managed_runtime=managed_runtime,
        workspace_path=workspace,
        endpoint_host=endpoint.host,
        endpoint_port=endpoint.port,
    )
    repository.save(transaction)
    log_info(
        _LOGGER,
        "Startup revalidation transaction created.",
        transaction_id=transaction.transaction_id,
        workspace=workspace,
    )
    return _StartupRevalidationTransaction(
        repository=repository,
        transaction_id=transaction.transaction_id,
    )


def _finish_startup_revalidation_transaction(
    transaction: _StartupRevalidationTransaction | None,
) -> None:
    """Clear startup revalidation state after setup succeeds."""

    if transaction is None:
        return
    transaction.repository.delete()
    log_info(
        _LOGGER,
        "Startup revalidation transaction cleared.",
        transaction_id=transaction.transaction_id,
    )


def _fail_startup_revalidation_transaction(
    transaction: _StartupRevalidationTransaction | None,
    error: Exception,
) -> None:
    """Mark startup revalidation as failed without hiding launch errors."""

    if transaction is None:
        return
    try:
        current = transaction.repository.load()
        if current is None:
            return
        transaction.repository.save(
            SetupTransaction(
                schema_version=current.schema_version,
                transaction_id=current.transaction_id,
                mode=current.mode,
                status=SetupTransactionStatus.FAILED,
                created_at=current.created_at,
                updated_at=datetime.now(UTC),
                installation=current.installation,
                runtime=current.runtime,
                target=current.target,
                managed_runtime=current.managed_runtime,
                workspace_path=current.workspace_path,
                endpoint_host=current.endpoint_host,
                endpoint_port=current.endpoint_port,
                force_cpu_mode=current.force_cpu_mode,
                prefer_edge_torch=current.prefer_edge_torch,
                prefer_edge_comfy_channel=current.prefer_edge_comfy_channel,
                failure=SetupTransactionFailure(
                    code=type(error).__name__,
                    message=str(error).strip() or type(error).__name__,
                    recoverable=True,
                    diagnostic_detail=str(error).strip() or type(error).__name__,
                ),
            )
        )
        log_info(
            _LOGGER,
            "Startup revalidation transaction failed.",
            transaction_id=transaction.transaction_id,
            error=error,
        )
    except Exception as transaction_error:
        log_error(
            _LOGGER,
            "Failed to update startup revalidation transaction.",
            error=transaction_error,
        )


def _resolve_listener_state(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    registry: ManagedProcessRegistry,
    runtime_service: ManagedRuntimeService,
) -> ManagedProcessMetadata | None:
    """Resolve the endpoint ownership state before launching a managed process."""

    metadata = registry.load()
    probe = probe_managed_listener(
        host=endpoint.host,
        port=endpoint.port,
        workspace=workspace,
        metadata=metadata,
    )
    if probe.status is ManagedListenerStatus.ABSENT:
        if metadata is not None:
            registry.clear()
        return None
    if probe.status is ManagedListenerStatus.OWNED_HEALTHY:
        log_info(
            _LOGGER,
            "Reusing healthy owned managed ComfyUI listener",
            pid=probe.metadata.pid if probe.metadata is not None else None,
            host=endpoint.host,
            port=endpoint.port,
        )
        return probe.metadata
    if probe.status is ManagedListenerStatus.OWNED_STALE:
        stale_pid = probe.metadata.pid if probe.metadata is not None else None
        assert probe.metadata is not None
        termination = kill_managed_comfy_metadata(probe.metadata)
        runtime_service.record_launch(
            status=ManagedRuntimeLaunchStatus.STALE_REAPED,
            detail=probe.reason,
        )
        if (
            termination.status
            is not ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
        ):
            raise RuntimeError(
                "Substitute found a stale managed ComfyUI process but could not "
                "terminate it. Close any leftover ComfyUI windows or kill the "
                "process manually, then try again."
            )
        registry.clear_if_pid_matches(stale_pid)
        return None
    runtime_service.record_launch(
        status=ManagedRuntimeLaunchStatus.FOREIGN_LISTENER_BLOCKED,
        detail=probe.reason,
    )
    raise RuntimeError(
        "Another process is already using the managed ComfyUI address "
        f"{endpoint.host}:{endpoint.port}. Substitute will not start over a "
        "foreign listener."
    )


def _timestamp_now() -> str:
    """Return one UTC ISO timestamp for managed runtime metadata."""

    return datetime.now(UTC).isoformat()


def _build_managed_launch_command(
    *,
    venv_python: Path,
    endpoint: ComfyEndpoint,
    workspace: Path,
    manager_runtime: ComfyManagerRuntime,
) -> tuple[str, ...]:
    """Build the authoritative managed ComfyUI launch command."""

    arguments = (
        "--listen",
        str(endpoint.host),
        "--port",
        str(endpoint.port),
        *manager_runtime.launch_arguments,
    )
    if exceeds_windows_legacy_path_limit(workspace):
        return (
            subprocess_path(venv_python),
            "-c",
            _LONG_WORKSPACE_BOOTSTRAP,
            subprocess_path(workspace),
            subprocess_path(workspace / "main.py"),
            *arguments,
        )
    return (
        subprocess_path(venv_python),
        subprocess_path(workspace / "main.py"),
        *arguments,
    )


def _iter_output_records(
    stdout_stream: IO[bytes], *, chunk_size: int = 4096
) -> Iterator[str]:
    """Decode one byte stream into newline- and carriage-return-delimited records."""

    decoder = getincrementaldecoder("utf-8")("replace")
    pending_text = ""
    while True:
        chunk = stdout_stream.read(chunk_size)
        if not chunk:
            break
        pending_text += decoder.decode(chunk)
        extracted_records, pending_text = _split_complete_output_records(pending_text)
        yield from extracted_records

    pending_text += decoder.decode(b"", final=True)
    extracted_records, pending_text = _split_complete_output_records(pending_text)
    yield from extracted_records
    if pending_text:
        yield pending_text


def _split_complete_output_records(text: str) -> tuple[tuple[str, ...], str]:
    """Split decoded terminal text into complete records plus one trailing partial."""

    record_start = 0
    cursor = 0
    records: list[str] = []
    text_length = len(text)
    while cursor < text_length:
        character = text[cursor]
        if character == "\r":
            if cursor + 1 < text_length and text[cursor + 1] == "\n":
                records.append(text[record_start : cursor + 2])
                cursor += 2
                record_start = cursor
                continue
            records.append(text[record_start : cursor + 1])
            cursor += 1
            record_start = cursor
            continue
        if character == "\n":
            records.append(text[record_start : cursor + 1])
            cursor += 1
            record_start = cursor
            continue
        cursor += 1
    return tuple(records), text[record_start:]
