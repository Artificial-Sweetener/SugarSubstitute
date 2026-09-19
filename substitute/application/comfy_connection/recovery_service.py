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

"""Coordinate Comfy connection state, queue gating, and restart requests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.domain.comfy_connection import (
    ComfyConnectionPhase,
    ComfyConnectionState,
    ComfyConnectionStateChange,
)
from substitute.domain.onboarding import ComfyTargetConfiguration, ComfyTargetMode
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("application.comfy_connection.recovery_service")

ComfyConnectionStateObserver = Callable[[ComfyConnectionStateChange], None]
DelayScheduler = Callable[[int, Callable[[], None]], None]


class ManagedComfyRestartRequester(Protocol):
    """Request one asynchronous restart of a Substitute-owned Comfy process."""

    def request_restart(self, *, on_failure: Callable[[], None]) -> None:
        """Begin restart work and report failures through the supplied callback."""


class ComfyConnectionRecoveryService:
    """Own connection transitions and coordinate non-destructive recovery policy."""

    def __init__(
        self,
        *,
        target: ComfyTargetConfiguration,
        set_backend_state: Callable[[str], None],
        set_dispatch_available: Callable[[bool], None],
        schedule_delay: DelayScheduler,
        restart_requester: ManagedComfyRestartRequester | None = None,
        disconnect_grace_ms: int = 1500,
        restart_timeout_ms: int = 120_000,
    ) -> None:
        """Store policy collaborators and initialize the connected state."""

        if disconnect_grace_ms < 0:
            raise ValueError("disconnect_grace_ms must be non-negative")
        if restart_timeout_ms <= 0:
            raise ValueError("restart_timeout_ms must be positive")
        self._target = target
        self._set_backend_state = set_backend_state
        self._set_dispatch_available = set_dispatch_available
        self._schedule_delay = schedule_delay
        self._restart_requester = restart_requester
        self._disconnect_grace_ms = disconnect_grace_ms
        self._restart_timeout_ms = restart_timeout_ms
        self._observers: list[ComfyConnectionStateObserver] = []
        self._disconnect_generation = 0
        self._restart_generation = 0
        self._state = ComfyConnectionState(
            phase=ComfyConnectionPhase.READY,
            target_mode=target.mode,
            can_restart=self._restart_is_safe,
        )

    @property
    def state(self) -> ComfyConnectionState:
        """Return the current immutable connection state."""

        return self._state

    def add_observer(self, observer: ComfyConnectionStateObserver) -> None:
        """Register an observer without synthesizing a state transition."""

        self._observers.append(observer)

    def remove_observer(self, observer: ComfyConnectionStateObserver) -> None:
        """Remove a previously registered observer when present."""

        if observer in self._observers:
            self._observers.remove(observer)

    def report_disconnected(self) -> None:
        """Gate generation immediately and confirm sustained outages after a grace."""

        if self._state.phase in {
            ComfyConnectionPhase.RESTARTING,
            ComfyConnectionPhase.RESTART_FAILED,
        }:
            return
        self._disconnect_generation += 1
        disconnect_generation = self._disconnect_generation
        self._set_dispatch_available(False)
        self._set_backend_state("starting")
        self._transition_to(ComfyConnectionPhase.RECONNECTING)
        self._schedule_delay(
            self._disconnect_grace_ms,
            lambda: self._confirm_disconnected(disconnect_generation),
        )

    def report_connected(self) -> None:
        """Restore generation only after the persistent Comfy channel reconnects."""

        self._disconnect_generation += 1
        self._restart_generation += 1
        previous_phase = self._state.phase
        self._set_backend_state("ready")
        self._set_dispatch_available(True)
        self._transition_to(ComfyConnectionPhase.READY)
        if previous_phase is not ComfyConnectionPhase.READY:
            log_info(
                _LOGGER,
                "Comfy connection recovered",
                previous_phase=previous_phase.value,
                target_mode=self._target.mode.value,
            )

    def request_restart(self) -> bool:
        """Start one safe managed-local restart without relaunching Substitute."""

        if not self._restart_is_safe or self._restart_requester is None:
            log_info(
                _LOGGER,
                "Ignored unsafe Comfy restart request",
                target_mode=self._target.mode.value,
                launch_owned=self._target.launch_owned,
            )
            return False
        if self._state.phase is ComfyConnectionPhase.RESTARTING:
            return False
        self._disconnect_generation += 1
        self._restart_generation += 1
        restart_generation = self._restart_generation
        self._set_dispatch_available(False)
        self._set_backend_state("starting")
        self._transition_to(ComfyConnectionPhase.RESTARTING)
        try:
            self._restart_requester.request_restart(
                on_failure=self.report_restart_failed
            )
        except Exception:
            log_exception(
                _LOGGER,
                "Managed Comfy restart request failed",
                target_mode=self._target.mode.value,
            )
            self.report_restart_failed()
        self._schedule_delay(
            self._restart_timeout_ms,
            lambda: self._expire_restart(restart_generation),
        )
        return True

    def report_restart_failed(self) -> None:
        """Expose restart failure while keeping generation and pending dispatch gated."""

        if self._state.phase is not ComfyConnectionPhase.RESTARTING:
            return
        self._restart_generation += 1
        self._set_backend_state("unavailable")
        self._set_dispatch_available(False)
        self._transition_to(ComfyConnectionPhase.RESTART_FAILED)

    def _expire_restart(self, restart_generation: int) -> None:
        """Fail a restart that never produces a connected persistent channel."""

        if restart_generation != self._restart_generation:
            return
        self.report_restart_failed()

    @property
    def _restart_is_safe(self) -> bool:
        """Return whether Substitute owns the selected local process lifecycle."""

        return (
            self._target.mode is ComfyTargetMode.MANAGED_LOCAL
            and self._target.launch_owned
        )

    def _confirm_disconnected(self, disconnect_generation: int) -> None:
        """Publish an outage only when its grace generation remains current."""

        if disconnect_generation != self._disconnect_generation:
            return
        if self._state.phase is not ComfyConnectionPhase.RECONNECTING:
            return
        self._set_backend_state("unavailable")
        self._transition_to(ComfyConnectionPhase.DISCONNECTED)

    def _transition_to(self, phase: ComfyConnectionPhase) -> None:
        """Publish one deduplicated immutable state transition."""

        if self._state.phase is phase:
            return
        previous = self._state
        current = ComfyConnectionState(
            phase=phase,
            target_mode=self._target.mode,
            can_restart=self._restart_is_safe,
            revision=previous.revision + 1,
        )
        self._state = current
        log_info(
            _LOGGER,
            "Comfy connection state changed",
            previous_phase=previous.phase.value,
            current_phase=current.phase.value,
            target_mode=current.target_mode.value,
            revision=current.revision,
        )
        change = ComfyConnectionStateChange(previous=previous, current=current)
        for observer in tuple(self._observers):
            observer(change)


__all__ = [
    "ComfyConnectionRecoveryService",
    "ComfyConnectionStateObserver",
    "ManagedComfyRestartRequester",
]
