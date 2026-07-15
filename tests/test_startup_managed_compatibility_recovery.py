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

"""Tests for managed startup runtime compatibility recovery policy."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
    ManagedCompatibilityRecoveryControllerState,
    ManagedCompatibilityRecoveryOutcome,
    core_nodepacks_for_compatibility_recovery,
    create_connected_managed_compatibility_recovery_controller,
    create_managed_compatibility_recovery_controller,
    managed_compatibility_recovery_outcome_from_task,
    owned_nodepack_recovery_message,
    request_managed_recovery_stop,
    run_managed_compatibility_recovery,
    should_attempt_owned_nodepack_recovery,
    submit_managed_compatibility_recovery,
)
from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskSubmitter,
)
from tests.execution_testing import ManualTaskHandle
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId

TResult = TypeVar("TResult")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
RECOVERY_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "managed_compatibility_recovery.py"
)
FORBIDDEN_RECOVERY_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_managed_core_refresh_allowed_for_updateable_core_mismatch(
    tmp_path: Path,
) -> None:
    """Managed startup should auto-refresh old core nodepacks once."""

    target = _target(tmp_path, launch_owned=True)
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is True
    )


def test_managed_core_refresh_blocks_too_new_core_mismatch(tmp_path: Path) -> None:
    """Startup recovery should not try to fix too-new nodepacks by updating."""

    target = _target(tmp_path, launch_owned=True)
    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_NEW)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is False
    )


def test_managed_core_refresh_requires_owned_launch(tmp_path: Path) -> None:
    """Targets not launched by Substitute must not be mutated by startup recovery."""

    target = _target(tmp_path, launch_owned=False)
    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is False
    )


def test_owned_nodepack_recovery_allows_attached_local_owned_launch(
    tmp_path: Path,
) -> None:
    """Attached local launch-owned workspaces should use owned-nodepack recovery."""

    target = _target(
        tmp_path,
        launch_owned=True,
        mode=ComfyTargetMode.ATTACHED_LOCAL,
    )
    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is True
    )


def test_owned_nodepack_recovery_rejects_remote_targets(tmp_path: Path) -> None:
    """Remote targets should stay read-only because there is no local workspace."""

    target = _target(
        tmp_path,
        launch_owned=False,
        mode=ComfyTargetMode.REMOTE,
    )
    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)

    assert (
        should_attempt_owned_nodepack_recovery(
            target=target,
            compatibility=compatibility,
            recovery_attempted=False,
            recovery_running=False,
        )
        is False
    )


def test_backend_mismatch_recovery_targets_only_backend() -> None:
    """BackEnd compatibility failures should not refresh SugarCubes."""

    for status in (
        RuntimeCompatibilityStatus.BACKEND_UNREACHABLE,
        RuntimeCompatibilityStatus.BACKEND_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
        RuntimeCompatibilityStatus.BACKEND_API_MISMATCH,
        RuntimeCompatibilityStatus.BACKEND_FEATURE_MISSING,
    ):
        assert core_nodepacks_for_compatibility_recovery(status) == frozenset(
            {CoreNodepackId.SUBSTITUTE_BACKEND}
        )


def test_sugarcubes_mismatch_recovery_targets_only_sugarcubes() -> None:
    """SugarCubes compatibility failures should not refresh BackEnd."""

    for status in (
        RuntimeCompatibilityStatus.SUGARCUBES_MISSING,
        RuntimeCompatibilityStatus.SUGARCUBES_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD,
        RuntimeCompatibilityStatus.SUGARCUBES_DEV_VERSION_RELEASE_BLOCKED,
    ):
        assert core_nodepacks_for_compatibility_recovery(status) == frozenset(
            {CoreNodepackId.SUGARCUBES}
        )


def test_compatible_runtime_recovery_targets_no_nodepacks() -> None:
    """Compatible runtimes should not request a managed nodepack refresh."""

    assert (
        core_nodepacks_for_compatibility_recovery(RuntimeCompatibilityStatus.COMPATIBLE)
        == frozenset()
    )


def test_managed_recovery_message_describes_targeted_nodepack() -> None:
    """Startup splash text should describe the exact targeted recovery."""

    assert (
        owned_nodepack_recovery_message(frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}))
        == "Updating Substitute BackEnd before opening."
    )
    assert (
        owned_nodepack_recovery_message(frozenset({CoreNodepackId.SUGARCUBES}))
        == "Updating SugarCubes before opening."
    )


def test_managed_recovery_outcome_carries_compatibility_and_error() -> None:
    """Managed recovery outcomes should carry task success or failure state."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)
    error = RuntimeError("failed")

    success = ManagedCompatibilityRecoveryOutcome(compatibility)
    failure = ManagedCompatibilityRecoveryOutcome(compatibility, error=error)

    assert success.compatibility is compatibility
    assert success.error is None
    assert failure.compatibility is compatibility
    assert failure.error is error


def test_managed_recovery_task_stops_state_and_refreshes_nodepack(
    tmp_path: Path,
) -> None:
    """Managed recovery task should clean the old state before refreshing setup."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)
    confirmed_status = object()
    cleanup_calls: list[object | None] = []
    setup_calls: list[tuple[ComfyTargetConfiguration, frozenset[CoreNodepackId]]] = []
    logs: list[str] = []
    state = _ManagedStartupState()

    def cleanup_state(cleanup_state: object | None) -> _CleanupResult:
        """Record cleanup and return a confirmed result."""

        cleanup_calls.append(cleanup_state)
        return _CleanupResult(
            managed_resource_present=True,
            termination_status=confirmed_status,
            user_safe_detail="Shutdown finished cleanly.",
        )

    def reconcile_owned_comfy_dependencies(
        target: ComfyTargetConfiguration,
        nodepacks: frozenset[CoreNodepackId],
        emit_log: Callable[[str], None],
    ) -> None:
        """Record setup and emit one fake setup log line."""

        setup_calls.append((target, nodepacks))
        emit_log("setup complete")

    target = _target(tmp_path, launch_owned=True)
    outcome = run_managed_compatibility_recovery(
        compatibility=compatibility,
        target=target,
        state_to_recover=state,
        confirmed_termination_status=confirmed_status,
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=reconcile_owned_comfy_dependencies,
        emit_recovery_log=logs.append,
    )

    assert outcome == ManagedCompatibilityRecoveryOutcome(compatibility)
    assert cleanup_calls == [state]
    assert state.wait_calls == [5.0]
    assert setup_calls == [(target, frozenset({CoreNodepackId.SUGARCUBES}))]
    assert logs == ["Shutdown finished cleanly.", "setup complete"]


def test_managed_recovery_task_fails_unconfirmed_cleanup(tmp_path: Path) -> None:
    """Managed recovery task should fail when a managed process remains uncertain."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)

    def cleanup_state(_state: object | None) -> _CleanupResult:
        """Return an unconfirmed cleanup result."""

        return _CleanupResult(
            managed_resource_present=True,
            termination_status=object(),
            user_safe_detail="Shutdown uncertain.",
        )

    outcome = run_managed_compatibility_recovery(
        compatibility=compatibility,
        target=_target(tmp_path, launch_owned=True),
        state_to_recover=object(),
        confirmed_termination_status=object(),
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=(
            lambda _target, _nodepacks, _emit_log: None
        ),
        emit_recovery_log=lambda _line: None,
    )

    assert outcome.compatibility is compatibility
    assert isinstance(outcome.error, RuntimeError)
    assert str(outcome.error) == "Shutdown uncertain."


def test_managed_recovery_submit_publishes_handle_outcome(tmp_path: Path) -> None:
    """Recovery submission should normalize and publish task outcomes."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)
    submitter = _QueuedSubmitter()
    published: list[ManagedCompatibilityRecoveryOutcome] = []

    def cleanup_state(_state: object | None) -> _CleanupResult:
        """Return a no-op cleanup result."""

        return _CleanupResult(
            managed_resource_present=False,
            termination_status=None,
            user_safe_detail="No cleanup.",
        )

    handle = submit_managed_compatibility_recovery(
        submitter=submitter,
        compatibility=compatibility,
        target=_target(tmp_path, launch_owned=True),
        state_to_recover=None,
        confirmed_termination_status=object(),
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=(
            lambda _target, _nodepacks, _emit_log: None
        ),
        emit_recovery_log=lambda _line: None,
        publish_outcome=published.append,
    )

    submitter.run_next()

    assert handle.is_finished
    assert published == [ManagedCompatibilityRecoveryOutcome(compatibility)]


def test_managed_recovery_controller_starts_targeted_recovery(
    tmp_path: Path,
) -> None:
    """Recovery controller should close readiness and submit targeted task work."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD)
    controller_state = ManagedCompatibilityRecoveryControllerState()
    comfy_ready_state = _ComfyReadyState(comfy_http_ready=True)
    queued_submitter = _QueuedSubmitter()
    registered_submitters: list[TaskSubmitter] = []
    backend_states: list[str] = []
    splash_messages: list[str] = []
    recovery_logs: list[str] = []
    setup_calls: list[tuple[ComfyTargetConfiguration, frozenset[CoreNodepackId]]] = []
    published: list[ManagedCompatibilityRecoveryOutcome] = []
    comfy_state: object | None = _ManagedStartupState()

    def set_comfy_state(state: object | None) -> None:
        """Record managed Comfy state replacement."""

        nonlocal comfy_state
        comfy_state = state

    def reconcile_owned_comfy_dependencies(
        target: ComfyTargetConfiguration,
        nodepacks: frozenset[CoreNodepackId],
        emit_log: Callable[[str], None],
    ) -> None:
        """Record targeted managed setup requests."""

        setup_calls.append((target, nodepacks))
        emit_log("setup complete")

    target = _target(tmp_path, launch_owned=True)
    controller = ManagedCompatibilityRecoveryController(
        state=controller_state,
        comfy_ready_state=comfy_ready_state,
        readiness_state=_ReadinessState(),
        target=target,
        submitter_factory=lambda: queued_submitter,
        register_submitter=registered_submitters.append,
        current_comfy_state=lambda: comfy_state,
        set_comfy_state=set_comfy_state,
        set_backend_state=backend_states.append,
        append_recovery_message=splash_messages.append,
        emit_recovery_log=recovery_logs.append,
        cleanup_state=lambda _state: _CleanupResult(
            managed_resource_present=False,
            termination_status=None,
            user_safe_detail="No cleanup.",
        ),
        reconcile_owned_comfy_dependencies=reconcile_owned_comfy_dependencies,
        confirmed_termination_status=object(),
        publish_outcome=published.append,
        is_startup_cancelled=lambda: False,
        handle_recovery_failure=lambda _compatibility, _error: None,
        relaunch_managed_comfy=lambda: None,
        restart_readiness_timer=lambda: None,
        trace_fields=dict,
    )

    controller.start(compatibility)
    queued_submitter.run_next()

    assert controller_state.recovery_attempted is True
    assert controller_state.recovery_running is True
    assert comfy_ready_state.comfy_http_ready is False
    assert backend_states == ["starting"]
    assert comfy_state is None
    assert registered_submitters == [queued_submitter]
    assert splash_messages == ["Updating SugarCubes before opening."]
    assert setup_calls == [(target, frozenset({CoreNodepackId.SUGARCUBES}))]
    assert recovery_logs == ["No cleanup.", "setup complete"]
    assert published == [ManagedCompatibilityRecoveryOutcome(compatibility)]


def test_create_managed_compatibility_recovery_controller_returns_controller(
    tmp_path: Path,
) -> None:
    """Managed recovery controller construction should live in its owner."""

    controller = create_managed_compatibility_recovery_controller(
        state=ManagedCompatibilityRecoveryControllerState(),
        comfy_ready_state=_ComfyReadyState(),
        readiness_state=_ReadinessState(),
        target=_target(tmp_path, launch_owned=True),
        submitter_factory=_QueuedSubmitter,
        register_submitter=lambda _submitter: None,
        current_comfy_state=lambda: None,
        set_comfy_state=lambda _state: None,
        set_backend_state=lambda _state: None,
        append_recovery_message=lambda _message: None,
        emit_recovery_log=lambda _line: None,
        cleanup_state=lambda _state: _CleanupResult(
            managed_resource_present=False,
            termination_status=None,
            user_safe_detail="No cleanup.",
        ),
        reconcile_owned_comfy_dependencies=(
            lambda _target, _nodepacks, _emit_log: None
        ),
        confirmed_termination_status=object(),
        publish_outcome=lambda _outcome: None,
        is_startup_cancelled=lambda: False,
        handle_recovery_failure=lambda _compatibility, _error: None,
        relaunch_managed_comfy=lambda: None,
        restart_readiness_timer=lambda: None,
        trace_fields=dict,
    )

    assert isinstance(controller, ManagedCompatibilityRecoveryController)


def test_create_connected_managed_compatibility_recovery_controller_wires_finish(
    tmp_path: Path,
) -> None:
    """Connected recovery controller factory should wire completion callback."""

    connected_callbacks: list[Callable[[object], None]] = []
    controller = create_connected_managed_compatibility_recovery_controller(
        state=ManagedCompatibilityRecoveryControllerState(),
        comfy_ready_state=_ComfyReadyState(),
        readiness_state=_ReadinessState(),
        target=_target(tmp_path, launch_owned=True),
        controller_adapters=_ControllerAdapters(),
        startup_adapters=_StartupAdapters(),
        current_comfy_state=lambda: None,
        set_comfy_state=lambda _state: None,
        set_backend_state=lambda _state: None,
        publish_outcome=lambda _outcome: None,
        connect_finished=connected_callbacks.append,
        is_startup_cancelled=lambda: False,
        restart_readiness_timer=lambda: None,
        trace_fields=dict,
    )

    assert isinstance(controller, ManagedCompatibilityRecoveryController)
    assert connected_callbacks == [controller.finish]


def test_managed_recovery_controller_finish_relaunches_after_success(
    tmp_path: Path,
) -> None:
    """Successful managed recovery should reset readiness and relaunch Comfy."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)
    controller_state = ManagedCompatibilityRecoveryControllerState(
        recovery_attempted=True,
        recovery_running=True,
    )
    phase = _Phase()
    comfy_states: list[object | None] = []
    relaunch_state = object()
    readiness_state = _ReadinessState(readiness_attempts=7)
    restart_calls = 0

    def restart_readiness_timer() -> None:
        """Record readiness timer restarts."""

        nonlocal restart_calls
        restart_calls += 1

    controller = _recovery_controller_for_finish(
        tmp_path=tmp_path,
        state=controller_state,
        readiness_state=readiness_state,
        set_comfy_state=comfy_states.append,
        relaunch_managed_comfy=lambda: relaunch_state,
        restart_readiness_timer=restart_readiness_timer,
        relaunch_phase=lambda: phase,
    )

    controller.finish(ManagedCompatibilityRecoveryOutcome(compatibility))

    assert controller_state.recovery_running is False
    assert readiness_state.readiness_attempts == 0
    assert phase.entered == 1
    assert phase.exited == 1
    assert comfy_states == [relaunch_state]
    assert restart_calls == 1


def test_managed_recovery_controller_finish_reports_failure(
    tmp_path: Path,
) -> None:
    """Failed managed recovery should report the incident without relaunching."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)
    error = RuntimeError("refresh failed")
    controller_state = ManagedCompatibilityRecoveryControllerState(
        recovery_attempted=True,
        recovery_running=True,
    )
    failures: list[tuple[BackendCompatibilityResult, Exception]] = []
    restart_calls = 0

    def restart_readiness_timer() -> None:
        """Record unexpected readiness timer restarts."""

        nonlocal restart_calls
        restart_calls += 1

    controller = _recovery_controller_for_finish(
        tmp_path=tmp_path,
        state=controller_state,
        handle_recovery_failure=lambda failure_compatibility, failure_error: (
            failures.append((failure_compatibility, failure_error))
        ),
        restart_readiness_timer=restart_readiness_timer,
    )

    controller.finish(ManagedCompatibilityRecoveryOutcome(compatibility, error=error))

    assert controller_state.recovery_running is False
    assert failures == [(compatibility, error)]
    assert restart_calls == 0


def test_managed_recovery_handle_failure_normalizes_outcome() -> None:
    """Unexpected handle failures should still publish compatibility context."""

    compatibility = _compatibility(RuntimeCompatibilityStatus.BACKEND_TOO_OLD)
    request: TaskRequest[ManagedCompatibilityRecoveryOutcome] = TaskRequest(
        identity=TaskIdentity(
            request_id=1,
            domain="managed_compatibility_recovery",
        ),
        context=ExecutionContext(
            operation="managed_compatibility_recovery",
            reason="test",
            lane="startup",
        ),
        work=lambda _token: ManagedCompatibilityRecoveryOutcome(compatibility),
    )
    handle: ManualTaskHandle[ManagedCompatibilityRecoveryOutcome] = ManualTaskHandle(
        request
    )
    error = RuntimeError("task crashed")
    handle.complete_failed(error)
    task_outcome = handle.outcome
    assert task_outcome is not None

    outcome = managed_compatibility_recovery_outcome_from_task(
        task_outcome,
        compatibility=compatibility,
    )

    assert outcome.compatibility is compatibility
    assert outcome.error is error


def test_managed_recovery_stop_requests_state_stop() -> None:
    """Recovery start should request managed startup execution to stop."""

    state = _ManagedStartupState()

    request_managed_recovery_stop(state)

    assert state.stop_reasons == ["managed_compatibility_recovery"]


def test_managed_recovery_policy_imports_no_forbidden_boundaries() -> None:
    """Managed recovery policy should stay free of Qt, presentation, and infrastructure."""

    imported_modules = _imported_module_names(RECOVERY_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_RECOVERY_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_managed_recovery_policy() -> None:
    """The startup facade should delegate managed recovery policy decisions."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "def _core_nodepacks_for_compatibility_recovery" not in source
    assert "def _managed_compatibility_recovery_message" not in source
    assert "def _should_attempt_managed_core_refresh" not in source
    assert "class _ManagedCompatibilityRecoveryOutcome" not in source
    assert "_MANAGED_CORE_REFRESH_COMPATIBILITY_STATUSES" not in source
    assert "def start_managed_compatibility_recovery" not in source
    assert "def finish_managed_compatibility_recovery" not in source
    assert "def setup_managed_recovery_comfy" not in source
    assert "def cleanup_managed_recovery_state" not in source
    assert "setup_managed_recovery_comfy" not in source
    assert "cleanup_managed_recovery_state" not in source
    assert "create_managed_recovery_submitter" not in source
    assert "register_managed_recovery_submitter" not in source
    assert "confirmed_managed_recovery_termination_status()" not in source
    assert "ensure_managed_comfy_setup" not in source
    assert 'thread_name_prefix="managed-compatibility-recovery"' not in source
    assert "def mark_managed_recovery_comfy_not_ready" not in source
    assert "mark_comfy_not_ready=" not in source
    assert "def reset_managed_recovery_readiness_attempts" not in source
    assert "reset_readiness_attempts=" not in source
    assert "create_connected_managed_compatibility_recovery_controller(" not in source
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in source
    )
    assert (
        "from substitute.app.bootstrap.managed_compatibility_recovery import"
        not in source
    )
    assert "ManagedCompatibilityRecoveryController(" not in source


def _compatibility(
    status: RuntimeCompatibilityStatus,
) -> BackendCompatibilityResult:
    """Build one incompatible runtime compatibility result."""

    return BackendCompatibilityResult(
        status=status,
        summary="SugarCubes version is incompatible.",
        installed_backend_version="1.6.2",
        required_backend_version=">=1.6.2,<2.0.0",
        installed_sugarcubes_version="0.8.0",
        required_sugarcubes_version=">=0.10.0,<2.0.0",
        repairable=True,
    )


def _target(
    tmp_path: Path,
    *,
    launch_owned: bool,
    mode: ComfyTargetMode = ComfyTargetMode.MANAGED_LOCAL,
) -> ComfyTargetConfiguration:
    """Build one target with configurable mode and launch ownership."""

    return ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None if mode is ComfyTargetMode.REMOTE else tmp_path / "ComfyUI",
        install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        launch_owned=launch_owned,
    )


@dataclass(frozen=True)
class _CleanupResult:
    """Represent fake cleanup facts for recovery task tests."""

    managed_resource_present: bool
    termination_status: object | None
    user_safe_detail: str


class _ManagedStartupState:
    """Record managed startup lifecycle requests."""

    def __init__(self) -> None:
        self.stop_reasons: list[str] = []
        self.wait_calls: list[float] = []

    def request_stop(self, *, reason: str) -> None:
        """Record one stop request."""

        self.stop_reasons.append(reason)

    def wait_until_finished(self, *, timeout: float) -> None:
        """Record one wait timeout."""

        self.wait_calls.append(timeout)


class _QueuedSubmitter(TaskSubmitter):
    """Queue recovery work until the test explicitly runs it."""

    def __init__(self) -> None:
        self._jobs: list[
            tuple[
                ManualTaskHandle[object],
                TaskRequest[object],
                CancellationToken,
            ]
        ] = []

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Queue one request and return its handle."""

        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        self._jobs.append(
            (
                _as_object_handle(handle),
                _as_object_request(request),
                cancellation,
            )
        )
        return handle

    def run_next(self) -> None:
        """Run the next queued job."""

        handle, request, cancellation = self._jobs.pop(0)
        try:
            if cancellation.is_cancelled:
                handle.complete_cancelled(reason=cancellation.reason or "cancelled")
            else:
                handle.complete_success(request.work(cancellation))
        except BaseException as error:
            handle.complete_failed(error)


def _as_object_handle(handle: ManualTaskHandle[TResult]) -> ManualTaskHandle[object]:
    """Widen one manual handle for queued-submit bookkeeping."""

    return handle  # type: ignore[return-value]


def _as_object_request(request: TaskRequest[TResult]) -> TaskRequest[object]:
    """Widen one task request for queued-submit bookkeeping."""

    return request  # type: ignore[return-value]


class _ControllerAdapters:
    """Expose fake concrete recovery controller adapter ports."""

    @property
    def submitter_factory(self) -> Callable[[], TaskSubmitter]:
        """Return a queued TaskSubmitter factory."""

        return _QueuedSubmitter

    @property
    def register_submitter(self) -> Callable[[TaskSubmitter], None]:
        """Return an inert TaskSubmitter registration port."""

        return lambda _submitter: None

    @property
    def cleanup_state(self) -> Callable[[object | None], _CleanupResult]:
        """Return an inert cleanup port."""

        return lambda _state: _CleanupResult(
            managed_resource_present=False,
            termination_status=None,
            user_safe_detail="No cleanup.",
        )

    @property
    def reconcile_owned_comfy_dependencies(
        self,
    ) -> Callable[
        [ComfyTargetConfiguration, frozenset[CoreNodepackId], Callable[[str], None]],
        None,
    ]:
        """Return an inert owned Comfy dependency reconciliation port."""

        return lambda _target, _nodepacks, _emit_log: None

    @property
    def confirmed_termination_status(self) -> object:
        """Return the fake confirmed termination status."""

        return object()


class _StartupAdapters:
    """Expose fake startup-facing recovery adapter ports."""

    def append_recovery_message(self, _message: str) -> None:
        """Ignore recovery messages."""

    def emit_recovery_log(self, _line: str) -> None:
        """Ignore recovery log lines."""

    def handle_recovery_failure(
        self,
        _compatibility: BackendCompatibilityResult,
        _error: Exception,
    ) -> None:
        """Ignore recovery failures."""

    def relaunch_managed_comfy(self) -> object | None:
        """Return no relaunched state."""

        return None


class _Phase:
    """Record context manager entry and exit for startup phases."""

    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    def __enter__(self) -> "_Phase":
        """Record phase entry."""

        self.entered += 1
        return self

    def __exit__(
        self,
        _error_type: object,
        _error: object,
        _traceback: object,
    ) -> None:
        """Record phase exit."""

        self.exited += 1


@dataclass
class _ComfyReadyState:
    """Expose the managed recovery Comfy readiness state field."""

    comfy_http_ready: bool = False


@dataclass
class _ReadinessState:
    """Expose the managed recovery readiness-attempt state field."""

    readiness_attempts: int = 0


def _recovery_controller_for_finish(
    *,
    tmp_path: Path,
    state: ManagedCompatibilityRecoveryControllerState,
    readiness_state: _ReadinessState | None = None,
    set_comfy_state: Callable[[object | None], None] = lambda _state: None,
    handle_recovery_failure: Callable[
        [BackendCompatibilityResult, Exception], None
    ] = lambda _compatibility, _error: None,
    relaunch_managed_comfy: Callable[[], object | None] = lambda: None,
    restart_readiness_timer: Callable[[], None] = lambda: None,
    relaunch_phase: Callable[[], _Phase] = _Phase,
) -> ManagedCompatibilityRecoveryController:
    """Build a controller with inert ports for finish-path tests."""

    return ManagedCompatibilityRecoveryController(
        state=state,
        comfy_ready_state=_ComfyReadyState(),
        readiness_state=readiness_state or _ReadinessState(),
        target=_target(tmp_path, launch_owned=True),
        submitter_factory=_QueuedSubmitter,
        register_submitter=lambda _submitter: None,
        current_comfy_state=lambda: None,
        set_comfy_state=set_comfy_state,
        set_backend_state=lambda _state: None,
        append_recovery_message=lambda _message: None,
        emit_recovery_log=lambda _line: None,
        cleanup_state=lambda _state: _CleanupResult(
            managed_resource_present=False,
            termination_status=None,
            user_safe_detail="No cleanup.",
        ),
        reconcile_owned_comfy_dependencies=(
            lambda _target, _nodepacks, _emit_log: None
        ),
        confirmed_termination_status=object(),
        publish_outcome=lambda _outcome: None,
        is_startup_cancelled=lambda: False,
        handle_recovery_failure=handle_recovery_failure,
        relaunch_managed_comfy=relaunch_managed_comfy,
        restart_readiness_timer=restart_readiness_timer,
        trace_fields=dict,
        relaunch_phase=relaunch_phase,
    )
