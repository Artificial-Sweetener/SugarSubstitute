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

"""Cover managed-recovery controller construction and lifecycle behavior."""

from __future__ import annotations


from collections.abc import Callable


from pathlib import Path
from sugarsubstitute_shared.localization import render_source_application_text


from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
    ManagedCompatibilityRecoveryControllerState,
    ManagedCompatibilityRecoveryOutcome,
    create_connected_managed_compatibility_recovery_controller,
    create_managed_compatibility_recovery_controller,
    request_managed_recovery_stop,
)


from substitute.application.execution import (
    TaskSubmitter,
)


from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.launch_activity import LocalizedSplashActivity


from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
)


from substitute.domain.comfy_nodepacks import CoreNodepackId


from .support import (
    _CleanupResult,
    _ComfyReadyState,
    _ControllerAdapters,
    _ManagedStartupState,
    _Phase,
    _QueuedSubmitter,
    _ReadinessState,
    _StartupAdapters,
    _compatibility,
    _recovery_controller_for_finish,
    _target,
)


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
    splash_activities: list[LocalizedSplashActivity] = []
    clear_activity_calls = 0
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

    def clear_recovery_activity() -> None:
        """Record one activity clear request."""

        nonlocal clear_activity_calls
        clear_activity_calls += 1

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
        start_recovery_activity=splash_activities.append,
        clear_recovery_activity=clear_recovery_activity,
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
    assert len(splash_activities) == 1
    assert render_source_application_text(splash_activities[0].initial_text) == (
        "Updating SugarCubes"
    )
    assert clear_activity_calls == 0
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
        start_recovery_activity=lambda _activity: None,
        clear_recovery_activity=lambda: None,
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
    clear_activity_calls = 0

    def restart_readiness_timer() -> None:
        """Record readiness timer restarts."""

        nonlocal restart_calls
        restart_calls += 1

    def clear_recovery_activity() -> None:
        """Record successful recovery activity cleanup."""

        nonlocal clear_activity_calls
        clear_activity_calls += 1

    controller = _recovery_controller_for_finish(
        tmp_path=tmp_path,
        state=controller_state,
        readiness_state=readiness_state,
        set_comfy_state=comfy_states.append,
        clear_recovery_activity=clear_recovery_activity,
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
    assert clear_activity_calls == 1


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
    clear_activity_calls = 0

    def restart_readiness_timer() -> None:
        """Record unexpected readiness timer restarts."""

        nonlocal restart_calls
        restart_calls += 1

    def clear_recovery_activity() -> None:
        """Record failed recovery activity cleanup."""

        nonlocal clear_activity_calls
        clear_activity_calls += 1

    controller = _recovery_controller_for_finish(
        tmp_path=tmp_path,
        state=controller_state,
        handle_recovery_failure=lambda failure_compatibility, failure_error: (
            failures.append((failure_compatibility, failure_error))
        ),
        clear_recovery_activity=clear_recovery_activity,
        restart_readiness_timer=restart_readiness_timer,
    )

    controller.finish(ManagedCompatibilityRecoveryOutcome(compatibility, error=error))

    assert controller_state.recovery_running is False
    assert failures == [(compatibility, error)]
    assert restart_calls == 0
    assert clear_activity_calls == 1


def test_managed_recovery_stop_requests_state_stop() -> None:
    """Recovery start should request managed startup execution to stop."""

    state = _ManagedStartupState()

    request_managed_recovery_stop(state)

    assert state.stop_reasons == ["managed_compatibility_recovery"]
