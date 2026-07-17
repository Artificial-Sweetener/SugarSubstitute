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

"""Tests for managed ComfyUI process ownership, probing, and shutdown behavior."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import signal
import subprocess
import threading
from typing import IO, Any, cast

import pytest

from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.application.ports.managed_runtime_selection_policy import (
    ManagedRuntimeSelectionPolicy,
)
from substitute.app.bootstrap import lifecycle
from substitute.app.bootstrap.lifecycle import ManagedComfyCleanupOutcome
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ManagedRuntimeConfiguration,
    SetupTransactionStatus,
)
from substitute.domain.comfy_manager import ComfyManagerKind, ComfyManagerRuntime
from substitute.infrastructure.comfy import (
    posix_guardian_containment,
    managed_launcher,
    managed_shutdown,
    process_manager,
    windows_job_containment,
)
from substitute.infrastructure.comfy.posix_guardian_containment import (
    PosixGuardianContainmentHandle,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)
from substitute.infrastructure.comfy.managed_process_registry import (
    ManagedProcessRegistry,
)
from substitute.infrastructure.comfy.managed_startup_monitor import (
    ManagedStartupReadinessResult,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentLaunchRequest,
    ManagedContainmentLaunchResult,
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationResult,
    ManagedProcessTerminationStatus,
    kill_managed_comfy,
    kill_managed_comfy_pid,
)
from substitute.infrastructure.comfy.windows_job_containment import (
    WindowsJobContainmentHandle,
)
from substitute.infrastructure.onboarding.file_managed_runtime_repository import (
    FileManagedRuntimeConfigurationRepository,
)
from substitute.infrastructure.onboarding.file_setup_transaction_repository import (
    FileSetupTransactionRepository,
)


@pytest.fixture(autouse=True)
def _use_integrated_manager_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep lifecycle tests focused on launch behavior after setup validation."""

    def detect(
        workspace: Path,
        *,
        python_executable: Path,
        **_kwargs: object,
    ) -> ComfyManagerRuntime:
        """Return the verified integrated runtime supplied by setup."""

        return ComfyManagerRuntime(
            kind=ComfyManagerKind.INTEGRATED,
            workspace=workspace,
            python_executable=python_executable,
            version="test",
        )

    monkeypatch.setattr(managed_launcher, "detect_workspace_manager_runtime", detect)


class _StaticSelectionPolicy(ManagedRuntimeSelectionPolicy):
    """Return a deterministic managed runtime configuration."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return a stable managed runtime selection."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel
        return ManagedRuntimeConfiguration(install_target="windows_nvidia")


class _FakeProcess:
    """Provide the minimal Popen surface used by lifecycle tests."""

    def __init__(self, pid: int, returncode: int | None = None) -> None:
        self.pid = pid
        self._returncode = returncode

    def poll(self) -> int | None:
        """Return the configured process exit status."""

        return self._returncode


class _ControlledOutputStream:
    """Release one output chunk only after the test permits reading."""

    def __init__(self, chunk: bytes) -> None:
        """Store one chunk and initialize read coordination."""

        self._chunk = chunk
        self._released = threading.Event()
        self._emitted = False
        self.close_count = 0

    def release(self) -> None:
        """Allow the blocked pump read to continue."""

        self._released.set()

    def read(self, _size: int = -1) -> bytes:
        """Return the chunk once, then EOF."""

        assert self._released.wait(timeout=2)
        if self._emitted:
            return b""
        self._emitted = True
        return self._chunk

    def close(self) -> None:
        """Record close calls without invalidating the test stream."""

        self.close_count += 1


class _ThreadedManagedTaskHandle:
    """Run managed launcher work in a test-owned thread."""

    def __init__(
        self,
        work: managed_launcher.LongLivedWork[None],
        *,
        thread_name: str,
    ) -> None:
        """Start the supplied long-lived work immediately."""

        self._cancellation = CancellationSource(generation=1)
        self._thread = threading.Thread(target=lambda: work(self._cancellation))
        self._thread.name = thread_name
        self._thread.start()

    @property
    def is_finished(self) -> bool:
        """Return whether the work thread has exited."""

        return not self._thread.is_alive()

    def stop(self, *, reason: str) -> None:
        """Cancel and briefly join the work thread."""

        self._cancellation.cancel(reason=reason)
        self._thread.join(timeout=1.0)

    def join(self, *, timeout: float) -> None:
        """Join the work thread for tests that wait on startup."""

        self._thread.join(timeout=timeout)


def _managed_task_factory(
    identity: TaskIdentity,
    context: ExecutionContext,
    work: managed_launcher.LongLivedWork[None],
    thread_name: str,
) -> managed_launcher.ManagedLongLivedTaskHandle:
    """Create one test managed task handle."""

    _ = identity, context
    return _ThreadedManagedTaskHandle(work, thread_name=thread_name)


def _managed_state(
    tmp_path: Path,
    *,
    process: ManagedProcessHandle | None,
    metadata: ManagedProcessMetadata | None,
) -> managed_launcher.ManagedComfyState:
    """Build one concrete managed state for lifecycle tests."""

    state = managed_launcher.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    state.proc = process
    state.metadata = metadata
    state.containment_handle = None
    state.containment_mode = None if metadata is None else metadata.containment_mode
    return state


def test_cleanup_handler_requests_stop_and_kills_owned_process_once(
    tmp_path: Path,
) -> None:
    """Cleanup should be idempotent and terminate the owned process only once."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    killed_states: list[managed_launcher.ManagedComfyState | None] = []
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state(killed_states, current_state),
    )

    first_result = cleanup()
    second_result = cleanup()

    assert state.stop_requested is True
    assert killed_states == [state]
    assert first_result.cleanup_ran is True
    assert first_result.outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS
    assert second_result == first_result


def test_cleanup_handler_retries_after_uncertain_result(tmp_path: Path) -> None:
    """Retry should re-run cleanup after an uncertain result instead of caching it."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    outcomes = [
        ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED,
        ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
    ]
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state(
            [],
            current_state,
            termination_status=outcomes.pop(0),
        ),
    )

    first_result = cleanup()
    second_result = cleanup()

    assert first_result.outcome is ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS
    assert second_result.outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS


def test_cleanup_handler_skip_future_cleanup_returns_bypass_result(
    tmp_path: Path,
) -> None:
    """Force-close should bypass any later cleanup hook execution."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state([], current_state),
    )

    cleanup.skip_future_cleanup()
    result = cleanup()

    assert result.cleanup_ran is False
    assert result.outcome is ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED


def test_cleanup_handler_without_managed_state_maps_to_no_action_required() -> None:
    """Missing managed state should map to the lifecycle no-action outcome."""

    cleanup = lifecycle.create_cleanup_handler(
        lambda: None,
        lambda current_state: _record_cleanup_state([], current_state),
    )

    result = cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED


def test_startup_revalidation_transaction_created_for_missing_workspace(
    tmp_path: Path,
) -> None:
    """Launcher setup work should leave pending state if startup is interrupted."""

    state_dir = tmp_path / "state"
    runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(state_dir),
        selection_policy=_StaticSelectionPolicy(),
    )

    transaction = managed_launcher._begin_startup_revalidation_transaction_if_needed(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=state_dir,
        runtime_service=runtime_service,
    )

    assert transaction is not None
    saved = FileSetupTransactionRepository(state_dir).load()
    assert saved is not None
    assert saved.status is SetupTransactionStatus.MANAGED_WORKSPACE_PROVISIONING


def test_startup_revalidation_transaction_cleared_after_success(
    tmp_path: Path,
) -> None:
    """Successful startup revalidation should remove pending setup state."""

    state_dir = tmp_path / "state"
    runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(state_dir),
        selection_policy=_StaticSelectionPolicy(),
    )
    transaction = managed_launcher._begin_startup_revalidation_transaction_if_needed(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=state_dir,
        runtime_service=runtime_service,
    )

    managed_launcher._finish_startup_revalidation_transaction(transaction)

    assert FileSetupTransactionRepository(state_dir).exists() is False


def test_startup_revalidation_transaction_records_failure(
    tmp_path: Path,
) -> None:
    """Failed startup revalidation should persist recoverable failure detail."""

    state_dir = tmp_path / "state"
    runtime_service = ManagedRuntimeService(
        FileManagedRuntimeConfigurationRepository(state_dir),
        selection_policy=_StaticSelectionPolicy(),
    )
    transaction = managed_launcher._begin_startup_revalidation_transaction_if_needed(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=state_dir,
        runtime_service=runtime_service,
    )

    managed_launcher._fail_startup_revalidation_transaction(
        transaction,
        RuntimeError("interrupted"),
    )

    saved = FileSetupTransactionRepository(state_dir).load()
    assert saved is not None
    assert saved.status is SetupTransactionStatus.FAILED
    assert saved.failure is not None
    assert saved.failure.message == "interrupted"


def test_cleanup_handler_maps_termination_timeout_to_failure(tmp_path: Path) -> None:
    """Termination command failure should map to the lifecycle failure outcome."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )
    cleanup = lifecycle.create_cleanup_handler(
        lambda: state,
        lambda current_state: _record_cleanup_state(
            [],
            current_state,
            termination_status=ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED,
        ),
    )

    result = cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.FAILURE


def test_cleanup_handler_maps_unexpected_exception_to_failure(tmp_path: Path) -> None:
    """Unexpected cleanup exceptions should map to the lifecycle failure outcome."""

    state = _managed_state(
        tmp_path,
        process=cast(ManagedProcessHandle, _FakeProcess(200)),
        metadata=ManagedProcessMetadata(
            pid=200,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        ),
    )

    def _raise_failure(
        current_state: managed_launcher.ManagedComfyState | None,
    ) -> process_manager.ManagedComfyStateCleanupResult:
        _ = current_state
        raise RuntimeError("boom")

    cleanup = lifecycle.create_cleanup_handler(lambda: state, _raise_failure)

    result = cleanup()

    assert result.outcome is ManagedComfyCleanupOutcome.FAILURE


def test_kill_comfyui_state_clears_registry_when_process_dies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """State-based cleanup should clear ownership metadata after a successful kill."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = registry.save(
        ManagedProcessMetadata(
            pid=321,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    state = managed_launcher.ManagedComfyState(registry=registry)
    state.metadata = metadata
    state.containment_mode = metadata.containment_mode
    monkeypatch.setattr(
        process_manager,
        "kill_managed_comfy_metadata",
        lambda metadata, **kwargs: ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
            pid=None if metadata is None else metadata.pid,
            attempted=True,
            user_safe_detail="Shutdown finished cleanly.",
            diagnostic_detail="terminated",
        ),
    )

    result = process_manager.kill_comfyui_state(state)

    assert registry.load() is None
    assert result.registry_cleared is True
    assert (
        result.termination_status
        is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    )


def test_kill_comfyui_state_keeps_registry_when_termination_is_not_verified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """State cleanup should preserve ownership metadata when verification fails."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = registry.save(
        ManagedProcessMetadata(
            pid=654,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    state = managed_launcher.ManagedComfyState(registry=registry)
    state.metadata = metadata
    state.containment_mode = metadata.containment_mode
    monkeypatch.setattr(
        process_manager,
        "kill_managed_comfy_metadata",
        lambda metadata, **kwargs: ManagedProcessTerminationResult(
            status=ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED,
            pid=None if metadata is None else metadata.pid,
            attempted=True,
            user_safe_detail=(
                "Shutdown could not be confirmed before the verification timeout."
            ),
            diagnostic_detail="SUCCESS: sent termination",
            verification_timed_out=True,
        ),
    )

    result = process_manager.kill_comfyui_state(state)

    assert registry.load() == metadata
    assert result.registry_cleared is False
    assert (
        result.termination_status
        is ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED
    )
    assert result.termination is not None
    assert result.termination.verification_timed_out is True


def test_background_start_reuses_healthy_owned_listener_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup should reuse a healthy owned listener instead of spawning again."""

    registry = ManagedProcessRegistry(tmp_path)
    metadata = registry.save(
        ManagedProcessMetadata(
            pid=999,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    status_lines: list[str] = []
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.OWNED_HEALTHY,
            reason="healthy",
            listener_pid=999,
            metadata=metadata,
        ),
    )
    popen_calls: list[list[str]] = []

    def _fake_popen(command: list[str], **kwargs: Any) -> Any:
        popen_calls.append(command)
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        on_status=status_lines.append,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert state.proc is None
    assert state.metadata == metadata
    assert status_lines == ["Reusing the existing managed ComfyUI instance."]
    assert popen_calls == []


def test_background_start_returns_before_listener_probe_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed background startup should not run listener probing before returning."""

    probe_entered = threading.Event()
    release_probe = threading.Event()

    def probe_managed_listener(**_kwargs: object) -> ManagedListenerProbeResult:
        """Block inside the fake probe until the test confirms startup returned."""

        probe_entered.set()
        assert release_probe.wait(timeout=2)
        return ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        )

    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        probe_managed_listener,
    )
    monkeypatch.setattr(
        managed_launcher,
        "ensure_managed_comfy_setup",
        lambda **kwargs: tmp_path / ".venv" / "Scripts" / "python.exe",
    )
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 789
        stdout = None

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _SpawnedProcess(),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )

    assert probe_entered.wait(timeout=2)
    assert state.is_finished is False
    release_probe.set()
    state.wait_until_finished(timeout=2)


def test_background_start_reaps_stale_owned_listener_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup should terminate a stale owned listener before spawning again."""

    registry = ManagedProcessRegistry(tmp_path)
    stale_metadata = registry.save(
        ManagedProcessMetadata(
            pid=456,
            host="127.0.0.1",
            port=8188,
            workspace_path=tmp_path / "comfyui",
        )
    )
    probe_results = [
        ManagedListenerProbeResult(
            status=ManagedListenerStatus.OWNED_STALE,
            reason="stale",
            metadata=stale_metadata,
        ),
        ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    ]
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: probe_results.pop(0),
    )
    killed_pids: list[int | None] = []
    monkeypatch.setattr(
        managed_launcher,
        "kill_managed_comfy_metadata",
        lambda metadata, **kwargs: _record_termination(
            killed_pids,
            None if metadata is None else metadata.pid,
        ),
    )
    monkeypatch.setattr(
        managed_launcher,
        "ensure_managed_comfy_setup",
        lambda **kwargs: tmp_path / ".venv" / "Scripts" / "python.exe",
    )
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 789
        stdout = None

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _SpawnedProcess(),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert killed_pids == [456]


def test_background_start_uses_utf8_for_managed_output_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed background launch should preserve raw Comfy stdout control codes."""

    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    )
    monkeypatch.setattr(
        managed_launcher,
        "ensure_managed_comfy_setup",
        lambda **kwargs: tmp_path / ".venv" / "Scripts" / "python.exe",
    )
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=False),
    )
    observed_request: dict[str, object] = {}

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 790
        stdout = None

        def poll(self) -> int | None:
            """Behave like a still-running process handle for lifecycle tests."""

            return None

    monkeypatch.setattr(
        managed_launcher,
        "launch_managed_process",
        lambda **kwargs: _record_launch_request(
            observed_request,
            kwargs["request"],
            _SpawnedProcess(),
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert observed_request["capture_output"] is True
    command = cast(tuple[str, ...], observed_request["command"])
    assert command[-1] == "--enable-manager"
    assert isinstance(observed_request["env"], dict)
    env = cast(dict[str, str], observed_request["env"])
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["SUGARSUBSTITUTE_SKIP_TTS_INSTALLER"] == "1"
    assert env["CM_USE_PYGIT2"] == "1"


def test_background_start_traces_managed_startup_phases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed background launch should trace the work hidden behind activation."""

    events: list[str] = []

    class _TraceSpan:
        """Record deterministic span entry and exit events."""

        def __init__(self, name: str) -> None:
            self._name = name

        def __enter__(self) -> None:
            events.append(f"span:start:{self._name}")

        def __exit__(self, *_exc: object) -> None:
            events.append(f"span:end:{self._name}")

    def trace_mark(event: str, **_fields: object) -> None:
        """Record one trace mark."""

        events.append(event)

    def trace_span(event: str, **_fields: object) -> _TraceSpan:
        """Record one trace span."""

        return _TraceSpan(event)

    monkeypatch.setattr(managed_launcher, "trace_mark", trace_mark)
    monkeypatch.setattr(managed_launcher, "trace_span", trace_span)
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT,
            reason="absent",
        ),
    )
    monkeypatch.setattr(
        managed_launcher,
        "ensure_managed_comfy_setup",
        lambda **kwargs: tmp_path / ".venv" / "Scripts" / "python.exe",
    )
    monkeypatch.setattr(
        managed_launcher,
        "wait_for_managed_startup_ready",
        lambda **kwargs: ManagedStartupReadinessResult(ready=True),
    )

    class _SpawnedProcess:
        """Provide the minimal subprocess handle used by managed startup."""

        pid = 790
        stdout = None

        def poll(self) -> int | None:
            """Behave like a still-running process handle for lifecycle tests."""

            return None

    monkeypatch.setattr(
        managed_launcher,
        "launch_managed_process",
        lambda **kwargs: _record_launch_request(
            {},
            kwargs["request"],
            _SpawnedProcess(),
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert events == [
        "managed_comfy.startup_task.start",
        "span:start:managed_comfy.resolve_listener",
        "span:end:managed_comfy.resolve_listener",
        "span:start:managed_comfy.startup_revalidation.begin",
        "span:end:managed_comfy.startup_revalidation.begin",
        "span:start:managed_comfy.ensure_setup",
        "span:end:managed_comfy.ensure_setup",
        "span:start:managed_comfy.startup_revalidation.finish",
        "span:end:managed_comfy.startup_revalidation.finish",
        "span:start:managed_comfy.launch_process",
        "span:end:managed_comfy.launch_process",
        "managed_comfy.process_launched",
        "span:start:managed_comfy.wait_ready",
        "span:end:managed_comfy.wait_ready",
        "managed_comfy.wait_ready.result",
    ]


def test_iter_output_records_preserves_carriage_return_progress_updates() -> None:
    """Managed output parsing should preserve in-place redraw records."""

    records = tuple(
        managed_launcher._iter_output_records(
            BytesIO(
                (
                    b"FETCH ComfyRegistry Data: 5/133\r"
                    b"FETCH ComfyRegistry Data: 10/133\r"
                    b"Prompt executed in 12.61 seconds\n"
                )
            ),
            chunk_size=7,
        )
    )

    assert records == (
        "FETCH ComfyRegistry Data: 5/133\r",
        "FETCH ComfyRegistry Data: 10/133\r",
        "Prompt executed in 12.61 seconds\n",
    )


def test_iter_output_records_preserves_interleaved_carriage_return_and_newline_records() -> (
    None
):
    """Managed output parsing should preserve mixed redraw and stable records."""

    records = tuple(
        managed_launcher._iter_output_records(
            BytesIO(
                (
                    b"  0%|          | 0/28 [00:00<?, ?it/s]\r"
                    b"FETCH ComfyRegistry Data: 25/134\n"
                    b" 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r"
                )
            ),
            chunk_size=11,
        )
    )

    assert records == (
        "  0%|          | 0/28 [00:00<?, ?it/s]\r",
        "FETCH ComfyRegistry Data: 25/134\n",
        " 21%|       | 6/28 [00:00<00:04,  5.38it/s]\r",
    )


def test_managed_output_pump_emits_harness_timing_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness runs should expose output-pump fanout timing."""

    monkeypatch.setenv("SUGAR_SUBSTITUTE_STARTUP_HARNESS", "1")
    records: list[str] = []
    state = managed_launcher.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )

    task = managed_launcher._start_output_pump_task(
        state=state,
        request_id=1,
        task_factory=_managed_task_factory,
        stdout_stream=BytesIO(b"Starting server\nTo see the GUI go to: http://x\n"),
        on_log=records.append,
    )
    join = getattr(task, "join")
    join(timeout=2)

    assert records[:2] == [
        "Starting server\n",
        "To see the GUI go to: http://x\n",
    ]
    assert any(
        record.startswith(
            "Substitute startup diagnostic event=managed_output_pump_timing "
        )
        and "record_count=2" in record
        and "total_on_log_ms=" in record
        and "max_on_log_ms=" in record
        for record in records
    )


def test_managed_request_stop_preserves_live_output_stream(
    tmp_path: Path,
) -> None:
    """Startup cancellation must not close Comfy's process-owned output pipe."""

    records: list[str] = []
    state = managed_launcher.ManagedComfyState(
        registry=ManagedProcessRegistry(tmp_path)
    )
    stdout_stream = _ControlledOutputStream(b"  0%|          | 0/28\r")

    task = managed_launcher._start_output_pump_task(
        state=state,
        request_id=1,
        task_factory=_managed_task_factory,
        stdout_stream=cast(IO[bytes], stdout_stream),
        on_log=records.append,
    )

    state.add_process_pump(task)
    state.request_stop(reason="startup_cancelled")
    stdout_stream.release()
    join = getattr(task, "join")
    join(timeout=2)

    assert records == ["  0%|          | 0/28\r"]
    assert stdout_stream.close_count == 1


def test_managed_output_pump_survives_log_consumer_failure(
    tmp_path: Path,
) -> None:
    """Output consumer failures must not close Comfy's process-owned pipe."""

    records: list[str] = []
    failures_remaining = 1

    def _flaky_consumer(record: str) -> None:
        """Fail once, then collect subsequent output records."""

        nonlocal failures_remaining
        if failures_remaining:
            failures_remaining -= 1
            raise RuntimeError("consumer disposed")
        records.append(record)

    task = managed_launcher._start_output_pump_task(
        state=managed_launcher.ManagedComfyState(
            registry=ManagedProcessRegistry(tmp_path)
        ),
        request_id=1,
        task_factory=_managed_task_factory,
        stdout_stream=BytesIO(b"first\rsecond\n"),
        on_log=_flaky_consumer,
    )
    join = getattr(task, "join")
    join(timeout=2)

    assert records == ["second\n"]


def test_background_start_refuses_foreign_listener(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed startup should fail closed when a foreign process owns the endpoint."""

    log_lines: list[str] = []
    monkeypatch.setattr(
        managed_launcher,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.FOREIGN,
            reason="foreign",
            listener_pid=777,
        ),
    )

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path / "comfyui",
        runtime_state_dir=tmp_path,
        on_log=log_lines.append,
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    state.wait_until_finished(timeout=2)

    assert state.proc is None
    assert any("foreign listener" in line for line in log_lines)


def test_kill_managed_comfy_reports_success_when_process_already_gone() -> None:
    """Termination should report success when no live process remains."""

    result = kill_managed_comfy(
        cast(subprocess.Popen[Any], _FakeProcess(123, returncode=0))
    )

    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert result.attempted is False


def test_kill_managed_comfy_pid_reports_windows_taskkill_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows termination should report taskkill timeouts explicitly."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _raise_taskkill_timeout(*args, **kwargs),
    )

    result = kill_managed_comfy_pid(123)

    assert result.attempted is True
    assert result.status is ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED
    assert result.termination_command_timed_out is True
    assert result.verification_timed_out is False


def test_kill_managed_comfy_pid_reports_windows_verification_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful Windows taskkill should still count as confirmed shutdown."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="terminated",
            stderr="",
        ),
    )
    monkeypatch.setattr(managed_shutdown, "is_process_running", lambda _pid: True)

    result = kill_managed_comfy_pid(124)

    assert result.attempted is True
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert result.termination_command_timed_out is False
    assert result.verification_timed_out is True
    assert "SUCCESS:" not in result.user_safe_detail


def test_kill_managed_comfy_pid_captures_windows_stdout_only_in_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw taskkill stdout should remain diagnostic-only."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="SUCCESS: Sent termination signal.",
            stderr="",
        ),
    )
    monkeypatch.setattr(managed_shutdown, "is_process_running", lambda _pid: True)

    result = kill_managed_comfy_pid(126)

    assert "SUCCESS:" not in result.user_safe_detail
    assert "SUCCESS:" in result.diagnostic_detail
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED


def test_kill_managed_comfy_pid_reports_windows_invocation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows termination should surface invocation failures as command failures."""

    monkeypatch.setattr(os, "name", "nt", raising=False)

    def _raise_os_error(*args: object, **kwargs: object) -> object:
        raise OSError("taskkill unavailable")

    monkeypatch.setattr(subprocess, "run", _raise_os_error)

    result = kill_managed_comfy_pid(127)

    assert result.status is ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED
    assert "taskkill unavailable" in result.diagnostic_detail


def test_kill_managed_comfy_pid_reports_windows_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows termination should report success when exit verification passes."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="terminated",
            stderr="",
        ),
    )
    monkeypatch.setattr(managed_shutdown, "is_process_running", lambda _pid: False)

    result = kill_managed_comfy_pid(125)

    assert result.attempted is True
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert result.termination_command_timed_out is False
    assert result.verification_timed_out is False
    assert result.user_safe_detail == "Shutdown finished cleanly."
    assert "terminated" in result.diagnostic_detail


def test_windows_job_owned_shutdown_closes_only_containment_handles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows contained shutdown should close the job handle before exit verification."""

    close_calls: list[str] = []
    verification_calls: list[int] = []
    handle = WindowsJobContainmentHandle(
        job_handle=11,
        process_handle=22,
        job_name="job-1",
    )
    metadata = ManagedProcessMetadata(
        pid=321,
        host="127.0.0.1",
        port=8188,
        workspace_path=tmp_path / "comfyui",
        containment_mode="windows_job_object",
        owner_pid=654,
        job_name="job-1",
    )
    monkeypatch.setattr(
        windows_job_containment,
        "close_job_containment_handle",
        lambda raw_handle: close_calls.append(raw_handle.job_name),
    )
    monkeypatch.setattr(
        managed_shutdown,
        "_verify_process_exit",
        lambda pid, **kwargs: _record_verification(verification_calls, pid),
    )

    result = managed_shutdown.kill_managed_comfy_metadata(
        metadata,
        containment_handle=handle,
    )

    assert close_calls == ["job-1"]
    assert verification_calls == [321]
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED


def test_posix_guardian_handle_close_preserves_log_stream() -> None:
    """POSIX cleanup should preserve the stderr stream owned by the log pump."""

    closed_streams: list[str] = []
    guardian_process = _FakeGuardianProcess(closed_streams)
    handle = PosixGuardianContainmentHandle(
        guardian_process=cast(subprocess.Popen[bytes], guardian_process),
        keepalive_write_fd=_create_pipe_write_fd(),
        guardian_pipe_token="guardian-1",
        process_group_id=321,
    )

    handle.close()

    assert "stdin" in closed_streams
    assert "stdout" in closed_streams
    assert "stderr" not in closed_streams


def test_terminate_process_group_yields_between_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POSIX process-group termination should sleep between liveness probes."""

    running_states = iter([True, True, False])
    sent_signals: list[int] = []
    sleep_calls: list[float] = []
    monotonic_values = iter([0.0, 0.01, 0.02])

    monkeypatch.setattr(
        posix_guardian_containment,
        "is_process_group_running",
        lambda _pgid: next(running_states),
    )
    monkeypatch.setattr(
        posix_guardian_containment,
        "_kill_process_group",
        lambda _pgid, signum: sent_signals.append(signum),
    )
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("time.sleep", lambda seconds: sleep_calls.append(seconds))

    posix_guardian_containment.terminate_process_group(123, timeout_seconds=1.0)

    assert sent_signals == [signal.SIGTERM]
    assert sleep_calls == [0.1]


def _record_termination(
    calls: list[int | None],
    pid: int | None,
) -> ManagedProcessTerminationResult:
    """Record one termination request and return a successful result."""

    calls.append(pid)
    return ManagedProcessTerminationResult(
        status=ManagedProcessTerminationStatus.TERMINATED_CONFIRMED,
        pid=pid,
        attempted=True,
        user_safe_detail="Shutdown finished cleanly.",
        diagnostic_detail="terminated",
    )


def _record_cleanup_state(
    calls: list[managed_launcher.ManagedComfyState | None],
    current_state: managed_launcher.ManagedComfyState | None,
    *,
    termination_status: ManagedProcessTerminationStatus = (
        ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    ),
) -> process_manager.ManagedComfyStateCleanupResult:
    """Record one cleanup request and return a successful typed result."""

    calls.append(current_state)
    metadata = None if current_state is None else current_state.metadata
    process = None if current_state is None else current_state.proc
    pid = (
        process.pid
        if process is not None
        else (metadata.pid if metadata is not None else None)
    )
    host = metadata.host if metadata is not None else None
    port = metadata.port if metadata is not None else None
    workspace = metadata.workspace_path if metadata is not None else None
    return process_manager.ManagedComfyStateCleanupResult(
        pid=pid,
        host=host,
        port=port,
        workspace=workspace,
        managed_resource_present=current_state is not None,
        live_process_present=process is not None,
        metadata_present=metadata is not None,
        used_persisted_metadata=False,
        termination_attempted=True,
        registry_cleared=False,
        termination=ManagedProcessTerminationResult(
            status=termination_status,
            pid=pid,
            attempted=True,
            verification_timed_out=(
                termination_status
                is ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED
            ),
            user_safe_detail=(
                "Shutdown finished cleanly."
                if termination_status
                is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
                else "Shutdown could not be confirmed before the verification timeout."
            ),
            diagnostic_detail="terminated",
        ),
        termination_status=termination_status,
        user_safe_detail=(
            "Shutdown finished cleanly."
            if termination_status
            is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
            else "Shutdown could not be confirmed before the verification timeout."
        ),
        diagnostic_detail="terminated",
    )


def _raise_taskkill_timeout(*args: object, **kwargs: object) -> object:
    """Raise one deterministic taskkill timeout for unit tests."""

    timeout = kwargs.get("timeout")
    command = cast(list[str], args[0])
    raise subprocess.TimeoutExpired(
        cmd=command,
        timeout=timeout if isinstance(timeout, int | float) else 5.0,
    )


def _record_launch_request(
    observed_request: dict[str, object],
    request: ManagedContainmentLaunchRequest,
    process: object,
) -> ManagedContainmentLaunchResult:
    """Capture one managed launch request and return a fake containment result."""

    observed_request["command"] = request.command
    observed_request["cwd"] = request.cwd
    observed_request["env"] = dict(request.env)
    observed_request["capture_output"] = request.capture_output
    return ManagedContainmentLaunchResult(
        process=cast(Any, process),
        metadata=ManagedProcessMetadata(
            pid=790,
            host="127.0.0.1",
            port=8188,
            workspace_path=request.cwd,
            containment_mode="legacy_uncontained",
        ),
        stdout_stream=None,
        containment_handle=None,
    )


def _record_verification(
    calls: list[int],
    pid: int,
) -> tuple[bool, bool]:
    """Record one verification request and report a confirmed exit."""

    calls.append(pid)
    return True, False


class _FakeGuardianProcess:
    """Provide close-traceable guardian stdio for containment-handle tests."""

    def __init__(self, closed_streams: list[str]) -> None:
        self.stdin = _NamedCloser("stdin", closed_streams)
        self.stdout = _NamedCloser("stdout", closed_streams)
        self.stderr = _NamedCloser("stderr", closed_streams)


class _NamedCloser:
    """Record when one guardian stream is explicitly closed."""

    def __init__(self, name: str, closed_streams: list[str]) -> None:
        self._name = name
        self._closed_streams = closed_streams

    def close(self) -> None:
        """Record one close call."""

        self._closed_streams.append(self._name)


def _create_pipe_write_fd() -> int:
    """Return one write file descriptor for containment-handle close tests."""

    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    return write_fd
