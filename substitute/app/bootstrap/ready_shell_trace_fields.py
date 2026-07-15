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

"""Build prompt-safe ready-shell startup trace fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class ReadyShellGateStateProtocol(Protocol):
    """Expose ready-shell gate flags used in startup trace records."""

    minimum_shell_ready: bool
    comfy_http_ready: bool
    main_window_shown: bool
    prehydration_attempted: bool
    prehydration_succeeded: bool
    hydration_started: bool


class StartupReadinessTraceStateProtocol(Protocol):
    """Expose readiness-controller fields used in startup trace records."""

    readiness_attempts: int
    nonessential_startup_warmups_pending_backend: bool


class ManagedCompatibilityRecoveryTraceStateProtocol(Protocol):
    """Expose managed recovery fields used in startup trace records."""

    recovery_attempted: bool
    recovery_running: bool


class PreShowRestoreProjectionTraceStateProtocol(Protocol):
    """Expose pre-show restore projection fields used in startup trace records."""

    pending: bool


@dataclass(frozen=True, slots=True)
class ReadyShellTraceFieldsProvider:
    """Provide a current prompt-safe ready-shell trace field snapshot."""

    startup_cancelled: Callable[[], bool]
    shell_frame_present: Callable[[], bool]
    ready_state: ReadyShellGateStateProtocol
    readiness_state: StartupReadinessTraceStateProtocol
    recovery_state: ManagedCompatibilityRecoveryTraceStateProtocol
    pre_show_restore_projection_state: PreShowRestoreProjectionTraceStateProtocol
    provisional_restore_projection_present: Callable[[], bool]

    def __call__(self) -> dict[str, object]:
        """Return current ready-shell gate and recovery state fields."""

        return {
            "startup_cancelled": self.startup_cancelled(),
            "shell_frame_present": self.shell_frame_present(),
            "minimum_shell_ready": self.ready_state.minimum_shell_ready,
            "comfy_http_ready": self.ready_state.comfy_http_ready,
            "main_window_shown": self.ready_state.main_window_shown,
            "prehydration_attempted": self.ready_state.prehydration_attempted,
            "prehydration_succeeded": self.ready_state.prehydration_succeeded,
            "hydration_started": self.ready_state.hydration_started,
            "readiness_attempts": self.readiness_state.readiness_attempts,
            "managed_compatibility_recovery_attempted": (
                self.recovery_state.recovery_attempted
            ),
            "managed_compatibility_recovery_running": (
                self.recovery_state.recovery_running
            ),
            "pre_show_restore_projection_pending": (
                self.pre_show_restore_projection_state.pending
            ),
            "nonessential_startup_warmups_pending_backend": (
                self.readiness_state.nonessential_startup_warmups_pending_backend
            ),
            "provisional_restore_projection_present": (
                self.provisional_restore_projection_present()
            ),
        }


def create_ready_shell_trace_fields_provider(
    *,
    startup_cancelled: Callable[[], bool],
    shell_frame_present: Callable[[], bool],
    ready_state: ReadyShellGateStateProtocol,
    readiness_state: StartupReadinessTraceStateProtocol,
    recovery_state: ManagedCompatibilityRecoveryTraceStateProtocol,
    pre_show_restore_projection_state: PreShowRestoreProjectionTraceStateProtocol,
    provisional_restore_projection_present: Callable[[], bool],
) -> ReadyShellTraceFieldsProvider:
    """Create the prompt-safe trace-field provider for ready-shell startup."""

    return ReadyShellTraceFieldsProvider(
        startup_cancelled=startup_cancelled,
        shell_frame_present=shell_frame_present,
        ready_state=ready_state,
        readiness_state=readiness_state,
        recovery_state=recovery_state,
        pre_show_restore_projection_state=pre_show_restore_projection_state,
        provisional_restore_projection_present=provisional_restore_projection_present,
    )


__all__ = [
    "ManagedCompatibilityRecoveryTraceStateProtocol",
    "PreShowRestoreProjectionTraceStateProtocol",
    "ReadyShellGateStateProtocol",
    "ReadyShellTraceFieldsProvider",
    "StartupReadinessTraceStateProtocol",
    "create_ready_shell_trace_fields_provider",
]
