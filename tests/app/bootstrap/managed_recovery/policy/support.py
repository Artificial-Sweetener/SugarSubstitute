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

"""Provide deterministic managed-recovery policy collaborators."""

from __future__ import annotations


import ast
from dataclasses import dataclass
from collections.abc import Callable


from pathlib import Path


from typing import TypeVar


from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
    ManagedCompatibilityRecoveryControllerState,
)


from substitute.application.execution import (
    CancellationToken,
    TaskHandle,
    TaskRequest,
    TaskSubmitter,
)


from tests.support.execution import ManualTaskHandle


from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.launch_activity import LocalizedSplashActivity


from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)


from substitute.domain.comfy_nodepacks import CoreNodepackId


TResult = TypeVar("TResult")


PROJECT_ROOT = Path(__file__).resolve().parents[5]


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
        required_sugarcubes_version="0.11.0",
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

    def start_recovery_activity(self, _activity: LocalizedSplashActivity) -> None:
        """Ignore recovery activities."""

    def clear_recovery_activity(self) -> None:
        """Ignore recovery activity clear requests."""

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
    clear_recovery_activity: Callable[[], None] = lambda: None,
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
        start_recovery_activity=lambda _activity: None,
        clear_recovery_activity=clear_recovery_activity,
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
