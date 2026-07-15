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

"""Own managed startup compatibility recovery policy."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.domain.comfy_nodepacks import CoreNodepackId
from substitute.domain.onboarding import ComfyTargetConfiguration, ComfyTargetMode
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("app.bootstrap.managed_compatibility_recovery")
RecoveryLogCallback = Callable[[str], None]


class ManagedCompatibilityCleanupResultProtocol(Protocol):
    """Describe managed cleanup facts needed during compatibility recovery."""

    @property
    def managed_resource_present(self) -> bool:
        """Return whether a managed resource existed during cleanup."""

    @property
    def termination_status(self) -> object | None:
        """Return the normalized termination status."""

    @property
    def user_safe_detail(self) -> str:
        """Return a user-safe cleanup detail line."""


ManagedCompatibilityCleanup = Callable[
    [object | None], ManagedCompatibilityCleanupResultProtocol
]
OwnedComfyDependencyReconciliation = Callable[
    [ComfyTargetConfiguration, frozenset[CoreNodepackId], RecoveryLogCallback], None
]


@dataclass(frozen=True)
class ManagedCompatibilityRecoveryOutcome:
    """Carry managed startup compatibility recovery results to the GUI thread."""

    compatibility: BackendCompatibilityResult
    error: Exception | None = None


@dataclass
class ManagedCompatibilityRecoveryControllerState:
    """Track GUI-thread managed compatibility recovery lifecycle state."""

    recovery_attempted: bool = False
    recovery_running: bool = False


class ManagedRecoveryComfyReadyStateProtocol(Protocol):
    """Record whether Comfy HTTP readiness is currently available."""

    comfy_http_ready: bool


class ManagedRecoveryReadinessStateProtocol(Protocol):
    """Record readiness probe retry state during managed recovery."""

    readiness_attempts: int


class ManagedRecoveryControllerAdaptersProtocol(Protocol):
    """Group concrete managed recovery ports consumed by the controller."""

    @property
    def submitter_factory(self) -> Callable[[], TaskSubmitter]:
        """Return the submitter factory used for recovery work."""

    @property
    def register_submitter(self) -> Callable[[TaskSubmitter], None]:
        """Return the startup resource registration port."""

    @property
    def cleanup_state(self) -> ManagedCompatibilityCleanup:
        """Return the managed state cleanup port."""

    @property
    def reconcile_owned_comfy_dependencies(
        self,
    ) -> OwnedComfyDependencyReconciliation:
        """Return the owned Comfy dependency reconciliation port."""

    @property
    def confirmed_termination_status(self) -> object:
        """Return the cleanup status proving managed termination."""


class ManagedRecoveryStartupAdaptersProtocol(Protocol):
    """Group startup-facing managed recovery ports consumed by the controller."""

    def append_recovery_message(self, message: str) -> None:
        """Append a recovery message to the current startup surface."""

    def emit_recovery_log(self, line: str) -> None:
        """Forward one recovery log line to startup output sinks."""

    def handle_recovery_failure(
        self,
        compatibility: BackendCompatibilityResult,
        error: Exception,
    ) -> None:
        """Handle a managed recovery failure incident."""

    def relaunch_managed_comfy(self) -> object | None:
        """Relaunch the managed Comfy target after recovery."""


OWNED_NODEPACK_RECOVERY_COMPATIBILITY_STATUSES: frozenset[
    RuntimeCompatibilityStatus
] = frozenset(
    {
        RuntimeCompatibilityStatus.BACKEND_UNREACHABLE,
        RuntimeCompatibilityStatus.BACKEND_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
        RuntimeCompatibilityStatus.BACKEND_API_MISMATCH,
        RuntimeCompatibilityStatus.BACKEND_FEATURE_MISSING,
        RuntimeCompatibilityStatus.SUGARCUBES_MISSING,
        RuntimeCompatibilityStatus.SUGARCUBES_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD,
        RuntimeCompatibilityStatus.SUGARCUBES_DEV_VERSION_RELEASE_BLOCKED,
    }
)


def core_nodepacks_for_compatibility_recovery(
    status: RuntimeCompatibilityStatus,
) -> frozenset[CoreNodepackId]:
    """Return the exact core nodepacks needed to repair one compatibility status."""

    if status in {
        RuntimeCompatibilityStatus.BACKEND_UNREACHABLE,
        RuntimeCompatibilityStatus.BACKEND_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
        RuntimeCompatibilityStatus.BACKEND_API_MISMATCH,
        RuntimeCompatibilityStatus.BACKEND_FEATURE_MISSING,
    }:
        return frozenset({CoreNodepackId.SUBSTITUTE_BACKEND})
    if status in {
        RuntimeCompatibilityStatus.SUGARCUBES_MISSING,
        RuntimeCompatibilityStatus.SUGARCUBES_VERSION_UNKNOWN,
        RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD,
        RuntimeCompatibilityStatus.SUGARCUBES_DEV_VERSION_RELEASE_BLOCKED,
    }:
        return frozenset({CoreNodepackId.SUGARCUBES})
    return frozenset()


def owned_nodepack_recovery_message(
    nodepacks: frozenset[CoreNodepackId],
) -> str:
    """Return a concise startup message for targeted owned-nodepack recovery."""

    if nodepacks == frozenset({CoreNodepackId.SUBSTITUTE_BACKEND}):
        return "Updating Substitute BackEnd before opening."
    if nodepacks == frozenset({CoreNodepackId.SUGARCUBES}):
        return "Updating SugarCubes before opening."
    return "Updating Substitute Comfy nodepacks before opening."


def should_attempt_owned_nodepack_recovery(
    *,
    target: ComfyTargetConfiguration,
    compatibility: BackendCompatibilityResult,
    recovery_attempted: bool,
    recovery_running: bool,
) -> bool:
    """Return whether startup may repair owned local nodepacks and restart Comfy."""

    if recovery_attempted or recovery_running:
        return False
    if (
        target.mode is ComfyTargetMode.REMOTE
        or not target.launch_owned
        or target.workspace_path is None
    ):
        return False
    if not compatibility.repairable:
        return False
    return compatibility.status in OWNED_NODEPACK_RECOVERY_COMPATIBILITY_STATUSES


class ManagedCompatibilityRecoveryController:
    """Coordinate managed compatibility recovery start, finish, and relaunch."""

    def __init__(
        self,
        *,
        state: ManagedCompatibilityRecoveryControllerState,
        comfy_ready_state: ManagedRecoveryComfyReadyStateProtocol,
        readiness_state: ManagedRecoveryReadinessStateProtocol,
        target: ComfyTargetConfiguration,
        submitter_factory: Callable[[], TaskSubmitter],
        register_submitter: Callable[[TaskSubmitter], None],
        current_comfy_state: Callable[[], object | None],
        set_comfy_state: Callable[[object | None], None],
        set_backend_state: Callable[[str], None],
        append_recovery_message: Callable[[str], None],
        emit_recovery_log: RecoveryLogCallback,
        cleanup_state: ManagedCompatibilityCleanup,
        reconcile_owned_comfy_dependencies: OwnedComfyDependencyReconciliation,
        confirmed_termination_status: object,
        publish_outcome: Callable[[ManagedCompatibilityRecoveryOutcome], None],
        is_startup_cancelled: Callable[[], bool],
        handle_recovery_failure: Callable[
            [BackendCompatibilityResult, Exception], None
        ],
        relaunch_managed_comfy: Callable[[], object | None],
        restart_readiness_timer: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        relaunch_phase: Callable[[], AbstractContextManager[object]] = nullcontext,
    ) -> None:
        """Store explicit ports for managed recovery orchestration."""

        self._state = state
        self._comfy_ready_state = comfy_ready_state
        self._readiness_state = readiness_state
        self._target = target
        self._submitter_factory = submitter_factory
        self._register_submitter = register_submitter
        self._current_comfy_state = current_comfy_state
        self._set_comfy_state = set_comfy_state
        self._set_backend_state = set_backend_state
        self._append_recovery_message = append_recovery_message
        self._emit_recovery_log = emit_recovery_log
        self._cleanup_state = cleanup_state
        self._reconcile_owned_comfy_dependencies = reconcile_owned_comfy_dependencies
        self._confirmed_termination_status = confirmed_termination_status
        self._publish_outcome = publish_outcome
        self._is_startup_cancelled = is_startup_cancelled
        self._handle_recovery_failure = handle_recovery_failure
        self._relaunch_managed_comfy = relaunch_managed_comfy
        self._relaunch_phase = relaunch_phase
        self._restart_readiness_timer = restart_readiness_timer
        self._trace_fields = trace_fields

    def start(self, compatibility: BackendCompatibilityResult) -> None:
        """Start targeted managed recovery work on the startup execution lane."""

        workspace = self._target.workspace_path
        if workspace is None:
            raise RuntimeError("Managed compatibility recovery requires a workspace.")
        trace_mark(
            "startup.runtime_compatibility.recovery.start",
            compatibility_status=compatibility.status.value,
            compatibility_summary=compatibility.summary,
            **self._trace_fields(),
        )
        refresh_nodepacks = core_nodepacks_for_compatibility_recovery(
            compatibility.status
        )
        if not refresh_nodepacks:
            raise RuntimeError(
                "Managed compatibility recovery has no targeted nodepack "
                f"for status {compatibility.status.value}."
            )
        self._state.recovery_attempted = True
        self._state.recovery_running = True
        self._comfy_ready_state.comfy_http_ready = False
        self._set_backend_state("starting")
        state_to_recover = self._current_comfy_state()
        request_managed_recovery_stop(state_to_recover)
        self._set_comfy_state(None)
        self._append_recovery_message(
            owned_nodepack_recovery_message(refresh_nodepacks)
        )
        submitter = self._submitter_factory()
        self._register_submitter(submitter)
        log_info(
            _LOGGER,
            "Managed compatibility recovery started",
            target_mode=self._target.mode.value,
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
            compatibility_status=compatibility.status.value,
            recovery_attempted=self._state.recovery_attempted,
            recovery_running=self._state.recovery_running,
        )
        submit_managed_compatibility_recovery(
            submitter=submitter,
            compatibility=compatibility,
            target=self._target,
            state_to_recover=state_to_recover,
            confirmed_termination_status=self._confirmed_termination_status,
            cleanup_state=self._cleanup_state,
            reconcile_owned_comfy_dependencies=(
                self._reconcile_owned_comfy_dependencies
            ),
            emit_recovery_log=self._emit_recovery_log,
            publish_outcome=self._publish_outcome,
        )

    def finish(self, outcome: object) -> None:
        """Finish managed recovery by failing startup or relaunching Comfy."""

        self._state.recovery_running = False
        recovery_outcome = cast(ManagedCompatibilityRecoveryOutcome, outcome)
        trace_mark(
            "startup.runtime_compatibility.recovery.finished",
            compatibility_status=recovery_outcome.compatibility.status.value,
            error=repr(recovery_outcome.error)
            if recovery_outcome.error is not None
            else "",
            **self._trace_fields(),
        )
        if self._is_startup_cancelled():
            return
        if recovery_outcome.error is not None:
            log_warning(
                _LOGGER,
                "Managed compatibility recovery failed before relaunch",
                target_mode=self._target.mode.value,
                host=self._target.endpoint.host,
                port=self._target.endpoint.port,
                compatibility_status=recovery_outcome.compatibility.status.value,
                recovery_attempted=self._state.recovery_attempted,
                recovery_running=self._state.recovery_running,
                error_type=type(recovery_outcome.error).__name__,
            )
            self._handle_recovery_failure(
                recovery_outcome.compatibility,
                recovery_outcome.error,
            )
            return
        self._readiness_state.readiness_attempts = 0
        with self._relaunch_phase():
            self._set_comfy_state(self._relaunch_managed_comfy())
        log_info(
            _LOGGER,
            "Managed compatibility recovery relaunched Comfy",
            target_mode=self._target.mode.value,
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
            compatibility_status=recovery_outcome.compatibility.status.value,
            recovery_attempted=self._state.recovery_attempted,
            recovery_running=self._state.recovery_running,
        )
        self._restart_readiness_timer()


def create_managed_compatibility_recovery_controller(
    *,
    state: ManagedCompatibilityRecoveryControllerState,
    comfy_ready_state: ManagedRecoveryComfyReadyStateProtocol,
    readiness_state: ManagedRecoveryReadinessStateProtocol,
    target: ComfyTargetConfiguration,
    submitter_factory: Callable[[], TaskSubmitter],
    register_submitter: Callable[[TaskSubmitter], None],
    current_comfy_state: Callable[[], object | None],
    set_comfy_state: Callable[[object | None], None],
    set_backend_state: Callable[[str], None],
    append_recovery_message: Callable[[str], None],
    emit_recovery_log: RecoveryLogCallback,
    cleanup_state: ManagedCompatibilityCleanup,
    reconcile_owned_comfy_dependencies: OwnedComfyDependencyReconciliation,
    confirmed_termination_status: object,
    publish_outcome: Callable[[ManagedCompatibilityRecoveryOutcome], None],
    is_startup_cancelled: Callable[[], bool],
    handle_recovery_failure: Callable[[BackendCompatibilityResult, Exception], None],
    relaunch_managed_comfy: Callable[[], object | None],
    restart_readiness_timer: Callable[[], None],
    trace_fields: Callable[[], dict[str, object]],
    relaunch_phase: Callable[[], AbstractContextManager[object]] = nullcontext,
) -> ManagedCompatibilityRecoveryController:
    """Create the controller that coordinates managed compatibility recovery."""

    return ManagedCompatibilityRecoveryController(
        state=state,
        comfy_ready_state=comfy_ready_state,
        readiness_state=readiness_state,
        target=target,
        submitter_factory=submitter_factory,
        register_submitter=register_submitter,
        current_comfy_state=current_comfy_state,
        set_comfy_state=set_comfy_state,
        set_backend_state=set_backend_state,
        append_recovery_message=append_recovery_message,
        emit_recovery_log=emit_recovery_log,
        cleanup_state=cleanup_state,
        reconcile_owned_comfy_dependencies=reconcile_owned_comfy_dependencies,
        confirmed_termination_status=confirmed_termination_status,
        publish_outcome=publish_outcome,
        is_startup_cancelled=is_startup_cancelled,
        handle_recovery_failure=handle_recovery_failure,
        relaunch_managed_comfy=relaunch_managed_comfy,
        restart_readiness_timer=restart_readiness_timer,
        trace_fields=trace_fields,
        relaunch_phase=relaunch_phase,
    )


def create_connected_managed_compatibility_recovery_controller(
    *,
    state: ManagedCompatibilityRecoveryControllerState,
    comfy_ready_state: ManagedRecoveryComfyReadyStateProtocol,
    readiness_state: ManagedRecoveryReadinessStateProtocol,
    target: ComfyTargetConfiguration,
    controller_adapters: ManagedRecoveryControllerAdaptersProtocol,
    startup_adapters: ManagedRecoveryStartupAdaptersProtocol,
    current_comfy_state: Callable[[], object | None],
    set_comfy_state: Callable[[object | None], None],
    set_backend_state: Callable[[str], None],
    publish_outcome: Callable[[ManagedCompatibilityRecoveryOutcome], None],
    connect_finished: Callable[[Callable[[object], None]], object],
    is_startup_cancelled: Callable[[], bool],
    restart_readiness_timer: Callable[[], None],
    trace_fields: Callable[[], dict[str, object]],
    relaunch_phase: Callable[[], AbstractContextManager[object]] = nullcontext,
) -> ManagedCompatibilityRecoveryController:
    """Create the live recovery controller and connect its completion bridge."""

    controller = create_managed_compatibility_recovery_controller(
        state=state,
        comfy_ready_state=comfy_ready_state,
        readiness_state=readiness_state,
        target=target,
        submitter_factory=controller_adapters.submitter_factory,
        register_submitter=controller_adapters.register_submitter,
        current_comfy_state=current_comfy_state,
        set_comfy_state=set_comfy_state,
        set_backend_state=set_backend_state,
        append_recovery_message=startup_adapters.append_recovery_message,
        emit_recovery_log=startup_adapters.emit_recovery_log,
        cleanup_state=controller_adapters.cleanup_state,
        reconcile_owned_comfy_dependencies=(
            controller_adapters.reconcile_owned_comfy_dependencies
        ),
        confirmed_termination_status=(controller_adapters.confirmed_termination_status),
        publish_outcome=publish_outcome,
        is_startup_cancelled=is_startup_cancelled,
        handle_recovery_failure=startup_adapters.handle_recovery_failure,
        relaunch_managed_comfy=startup_adapters.relaunch_managed_comfy,
        restart_readiness_timer=restart_readiness_timer,
        trace_fields=trace_fields,
        relaunch_phase=relaunch_phase,
    )
    connect_finished(controller.finish)
    return controller


def submit_managed_compatibility_recovery(
    *,
    submitter: TaskSubmitter,
    compatibility: BackendCompatibilityResult,
    target: ComfyTargetConfiguration,
    state_to_recover: object | None,
    confirmed_termination_status: object,
    cleanup_state: ManagedCompatibilityCleanup,
    reconcile_owned_comfy_dependencies: OwnedComfyDependencyReconciliation,
    emit_recovery_log: RecoveryLogCallback,
    publish_outcome: Callable[[ManagedCompatibilityRecoveryOutcome], None],
) -> TaskHandle[ManagedCompatibilityRecoveryOutcome]:
    """Submit managed recovery work and publish a normalized outcome."""

    request: TaskRequest[ManagedCompatibilityRecoveryOutcome] = TaskRequest(
        identity=TaskIdentity(
            request_id=1,
            domain="managed_compatibility_recovery",
            parts=(("status", compatibility.status.value),),
        ),
        context=ExecutionContext(
            operation="managed_compatibility_recovery",
            reason="startup_recovery",
            lane="startup",
        ),
        work=lambda _token: run_managed_compatibility_recovery(
            compatibility=compatibility,
            target=target,
            state_to_recover=state_to_recover,
            confirmed_termination_status=confirmed_termination_status,
            cleanup_state=cleanup_state,
            reconcile_owned_comfy_dependencies=reconcile_owned_comfy_dependencies,
            emit_recovery_log=emit_recovery_log,
        ),
    )
    scope = TaskScope(
        submitter=submitter,
        scope_id="managed_compatibility_recovery",
    )
    handle = scope.submit(request)
    handle.add_done_callback(
        lambda outcome: _publish_scoped_managed_compatibility_recovery_outcome(
            outcome=outcome,
            compatibility=compatibility,
            publish_outcome=publish_outcome,
            close_scope=scope.close,
        ),
        reason="managed_compatibility_recovery_finished",
    )
    return handle


def _publish_scoped_managed_compatibility_recovery_outcome(
    *,
    outcome: TaskOutcome[ManagedCompatibilityRecoveryOutcome],
    compatibility: BackendCompatibilityResult,
    publish_outcome: Callable[[ManagedCompatibilityRecoveryOutcome], None],
    close_scope: Callable[..., None],
) -> None:
    """Publish a managed recovery outcome and close its execution scope."""

    close_scope(reason="managed_compatibility_recovery_finished")
    publish_outcome(
        managed_compatibility_recovery_outcome_from_task(
            outcome,
            compatibility=compatibility,
        )
    )


def run_managed_compatibility_recovery(
    *,
    compatibility: BackendCompatibilityResult,
    target: ComfyTargetConfiguration,
    state_to_recover: object | None,
    confirmed_termination_status: object,
    cleanup_state: ManagedCompatibilityCleanup,
    reconcile_owned_comfy_dependencies: OwnedComfyDependencyReconciliation,
    emit_recovery_log: RecoveryLogCallback,
) -> ManagedCompatibilityRecoveryOutcome:
    """Stop the current owned local Comfy instance and refresh targeted nodepacks."""

    refresh_nodepacks = core_nodepacks_for_compatibility_recovery(compatibility.status)
    workspace = target.workspace_path
    if workspace is None:
        return ManagedCompatibilityRecoveryOutcome(
            compatibility=compatibility,
            error=RuntimeError(
                "Owned Comfy dependency recovery requires a local workspace."
            ),
        )
    if not refresh_nodepacks:
        return ManagedCompatibilityRecoveryOutcome(
            compatibility=compatibility,
            error=RuntimeError(
                "Managed compatibility recovery has no targeted nodepack "
                f"for status {compatibility.status.value}."
            ),
        )
    try:
        log_info(
            _LOGGER,
            "Managed compatibility recovery task started",
            compatibility_status=compatibility.status.value,
            workspace_name=workspace.name,
            nodepacks=",".join(
                sorted(nodepack.value for nodepack in refresh_nodepacks)
            ),
        )
        if state_to_recover is not None:
            cleanup_result = cleanup_state(state_to_recover)
            emit_recovery_log(cleanup_result.user_safe_detail)
            _wait_for_state_stop(state_to_recover)
            if (
                cleanup_result.managed_resource_present
                and cleanup_result.termination_status != confirmed_termination_status
            ):
                raise RuntimeError(cleanup_result.user_safe_detail)
        reconcile_owned_comfy_dependencies(target, refresh_nodepacks, emit_recovery_log)
        log_info(
            _LOGGER,
            "Managed compatibility recovery task finished",
            compatibility_status=compatibility.status.value,
            workspace_name=workspace.name,
            recovery_failed=False,
        )
        return ManagedCompatibilityRecoveryOutcome(compatibility)
    except Exception as error:
        log_warning(
            _LOGGER,
            "Managed compatibility recovery task failed",
            compatibility_status=compatibility.status.value,
            workspace_name=workspace.name,
            recovery_failed=True,
            error_type=type(error).__name__,
        )
        return ManagedCompatibilityRecoveryOutcome(
            compatibility=compatibility,
            error=error,
        )


def managed_compatibility_recovery_outcome_from_task(
    outcome: TaskOutcome[ManagedCompatibilityRecoveryOutcome],
    *,
    compatibility: BackendCompatibilityResult,
) -> ManagedCompatibilityRecoveryOutcome:
    """Return a recovery outcome from a completed task."""

    if outcome.status == "succeeded" and outcome.result is not None:
        return outcome.result
    if outcome.error is not None:
        return ManagedCompatibilityRecoveryOutcome(
            compatibility=compatibility,
            error=outcome.error
            if isinstance(outcome.error, Exception)
            else RuntimeError(repr(outcome.error)),
        )
    return ManagedCompatibilityRecoveryOutcome(
        compatibility=compatibility,
        error=RuntimeError(outcome.cancellation_reason or outcome.status),
    )


def request_managed_recovery_stop(state_to_recover: object | None) -> None:
    """Request the current managed startup state to stop when possible."""

    if state_to_recover is None:
        return
    stop = getattr(state_to_recover, "request_stop", None)
    if callable(stop):
        stop(reason="managed_compatibility_recovery")


def _wait_for_state_stop(state_to_recover: object) -> None:
    """Wait briefly for managed startup execution after cleanup."""

    wait = getattr(state_to_recover, "wait_until_finished", None)
    if callable(wait):
        wait(timeout=5.0)


__all__ = [
    "ManagedCompatibilityCleanup",
    "ManagedCompatibilityCleanupResultProtocol",
    "ManagedCompatibilityRecoveryController",
    "ManagedCompatibilityRecoveryControllerState",
    "ManagedCompatibilityRecoveryOutcome",
    "ManagedRecoveryControllerAdaptersProtocol",
    "ManagedRecoveryComfyReadyStateProtocol",
    "ManagedRecoveryReadinessStateProtocol",
    "ManagedRecoveryStartupAdaptersProtocol",
    "OWNED_NODEPACK_RECOVERY_COMPATIBILITY_STATUSES",
    "OwnedComfyDependencyReconciliation",
    "RecoveryLogCallback",
    "core_nodepacks_for_compatibility_recovery",
    "create_connected_managed_compatibility_recovery_controller",
    "create_managed_compatibility_recovery_controller",
    "managed_compatibility_recovery_outcome_from_task",
    "owned_nodepack_recovery_message",
    "request_managed_recovery_stop",
    "run_managed_compatibility_recovery",
    "should_attempt_owned_nodepack_recovery",
    "submit_managed_compatibility_recovery",
]
