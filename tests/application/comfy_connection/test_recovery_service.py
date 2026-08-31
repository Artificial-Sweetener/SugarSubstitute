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

"""Cover authoritative Comfy connection and recovery transitions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from substitute.application.comfy_connection import ComfyConnectionRecoveryService
from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionStateChange,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)


class _RestartRequester:
    """Record asynchronous managed restart requests for deterministic tests."""

    def __init__(self) -> None:
        """Initialize an empty request log."""

        self.failure_callbacks: list[Callable[[], None]] = []

    def request_restart(self, *, on_failure: Callable[[], None]) -> None:
        """Capture the supplied failure callback."""

        self.failure_callbacks.append(on_failure)


def _target(mode: ComfyTargetMode) -> ComfyTargetConfiguration:
    """Build one target with ownership matching its configured mode."""

    managed = mode is ComfyTargetMode.MANAGED_LOCAL
    return ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint("127.0.0.1", 8188),
        workspace_path=Path("ComfyUI") if mode is not ComfyTargetMode.REMOTE else None,
        install_owned=managed,
        launch_owned=managed,
    )


def _service(
    mode: ComfyTargetMode = ComfyTargetMode.MANAGED_LOCAL,
) -> tuple[
    ComfyConnectionRecoveryService,
    list[Callable[[], None]],
    list[str],
    list[bool],
    _RestartRequester,
]:
    """Build a deterministic service and expose its observable collaborators."""

    scheduled: list[Callable[[], None]] = []
    backend_states: list[str] = []
    dispatch_states: list[bool] = []
    restart_requester = _RestartRequester()
    service = ComfyConnectionRecoveryService(
        target=_target(mode),
        set_backend_state=backend_states.append,
        set_dispatch_available=dispatch_states.append,
        schedule_delay=lambda _delay_ms, callback: scheduled.append(callback),
        restart_requester=restart_requester,
    )
    return service, scheduled, backend_states, dispatch_states, restart_requester


def _current_phase(
    service: ComfyConnectionRecoveryService,
) -> ComfyConnectionPhase:
    """Read mutable recovery state without retaining mypy's prior narrowing."""

    return service.state.phase


def test_transient_disconnect_recovers_without_visible_outage() -> None:
    """Reconnect during the grace should cancel the sustained outage transition."""

    service, scheduled, backend_states, dispatch_states, _restart = _service()
    changes: list[ComfyConnectionStateChange] = []
    service.add_observer(changes.append)

    service.report_disconnected()
    service.report_connected()
    scheduled[0]()

    assert [change.current.phase for change in changes] == [
        ComfyConnectionPhase.RECONNECTING,
        ComfyConnectionPhase.READY,
    ]
    assert backend_states == ["starting", "ready"]
    assert dispatch_states == [False, True]


def test_sustained_disconnect_disables_generation_and_exposes_restart() -> None:
    """A managed outage should become visible after grace with restart available."""

    service, scheduled, backend_states, dispatch_states, _restart = _service()

    service.report_disconnected()
    scheduled[0]()

    assert _current_phase(service) is ComfyConnectionPhase.DISCONNECTED
    assert service.state.can_restart is True
    assert backend_states == ["starting", "unavailable"]
    assert dispatch_states == [False]


@pytest.mark.parametrize(
    "mode",
    [ComfyTargetMode.ATTACHED_LOCAL, ComfyTargetMode.REMOTE],
)
def test_non_owned_targets_fail_closed_for_restart(mode: ComfyTargetMode) -> None:
    """Attached and remote targets should never receive a local restart request."""

    service, scheduled, _backend, _dispatch, restart = _service(mode)
    service.report_disconnected()
    scheduled[0]()

    assert service.request_restart() is False
    assert service.state.can_restart is False
    assert restart.failure_callbacks == []


def test_restart_is_single_flight_and_success_waits_for_connection() -> None:
    """Restart should deduplicate requests and remain pending until websocket readiness."""

    service, scheduled, backend_states, dispatch_states, restart = _service()
    service.report_disconnected()
    scheduled[0]()

    assert service.request_restart() is True
    assert service.request_restart() is False
    assert len(restart.failure_callbacks) == 1
    assert _current_phase(service) is ComfyConnectionPhase.RESTARTING

    service.report_connected()

    assert _current_phase(service) is ComfyConnectionPhase.READY
    assert backend_states[-1] == "ready"
    assert dispatch_states[-1] is True


def test_restart_failure_remains_gated_and_deduplicates_late_failure() -> None:
    """A failed restart should retain pending work and ignore duplicate callbacks."""

    service, scheduled, backend_states, dispatch_states, restart = _service()
    changes: list[ComfyConnectionStateChange] = []
    service.add_observer(changes.append)
    service.report_disconnected()
    scheduled[0]()
    service.request_restart()

    restart.failure_callbacks[0]()
    restart.failure_callbacks[0]()

    assert _current_phase(service) is ComfyConnectionPhase.RESTART_FAILED
    assert backend_states[-1] == "unavailable"
    assert dispatch_states[-1] is False
    assert [change.current.phase for change in changes].count(
        ComfyConnectionPhase.RESTART_FAILED
    ) == 1


def test_restart_times_out_when_persistent_connection_never_returns() -> None:
    """A launched process that never reconnects should become a visible failure."""

    service, scheduled, backend_states, dispatch_states, _restart = _service()
    service.report_disconnected()
    scheduled.pop(0)()
    service.request_restart()

    scheduled.pop(0)()

    assert _current_phase(service) is ComfyConnectionPhase.RESTART_FAILED
    assert backend_states[-1] == "unavailable"
    assert dispatch_states[-1] is False
