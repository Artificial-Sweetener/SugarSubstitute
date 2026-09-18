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

"""Compose startup failure cleanup and its cancellable GUI task queue."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from substitute.app.bootstrap.gui_startup_queue import GuiStartupTaskQueue
from substitute.app.bootstrap.startup_splash_progress import (
    StartupProgressSplash,
    StartupSplashProgress,
)
from substitute.app.bootstrap.startup_failure_controller import (
    RuntimeCompatibilityProbeProtocol,
    StartupFailClosedCleanupPortFactory,
    StartupFailureController,
    StartupTimerProtocol,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident


class ReadyShellFailureQueue:
    """Adapt ready-shell failure handling and GUI task queue construction."""

    def __init__(
        self,
        *,
        is_startup_cancelled: Callable[[], bool],
        mark_startup_cancelled: Callable[[], None],
        readiness_timers: Callable[[], Sequence[StartupTimerProtocol]],
        runtime_compatibility_probes: Callable[
            [], Sequence[RuntimeCompatibilityProbeProtocol]
        ],
        managed_comfy_state: Callable[[], object | None],
        splash: Callable[[], StartupProgressSplash | None],
        cleanup: Callable[[], object],
        quit_app: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        managed_failure_report_factory: Callable[[ComfyStartupIncident], Any],
        present_startup_failure_report: Callable[[Any], None],
        scheduler: Callable[[int, Callable[[], None]], None],
        startup_timer: StartupTimer,
    ) -> None:
        """Create failure handling with a GUI queue that can be cancelled."""

        self._gui_queue: GuiStartupTaskQueue | None = None
        self._failure_controller = StartupFailureController(
            is_startup_cancelled=is_startup_cancelled,
            mark_startup_cancelled=mark_startup_cancelled,
            cleanup_ports=StartupFailClosedCleanupPortFactory(
                readiness_timers=readiness_timers,
                runtime_compatibility_probes=runtime_compatibility_probes,
                managed_comfy_state=managed_comfy_state,
                splash=splash,
                cleanup=cleanup,
                quit_app=quit_app,
                cancel_gui_queue=self.cancel_queue,
            ),
            trace_fields=trace_fields,
            managed_failure_report_factory=managed_failure_report_factory,
            present_startup_failure_report=present_startup_failure_report,
            quit_app=quit_app,
        )
        self._gui_queue = GuiStartupTaskQueue(
            scheduler=scheduler,
            startup_timer=startup_timer,
            failed=self._failure_controller.handle_gui_startup_failure,
            progress_observer=StartupSplashProgress(splash).queue_progress,
        )

    def request_startup_cancel(self) -> None:
        """Forward a startup cancel request into fail-closed cleanup."""

        self._failure_controller.request_startup_cancel()

    def handle_managed_startup_failure(self, incident: object) -> None:
        """Forward a managed startup incident into fail-closed cleanup."""

        self._failure_controller.handle_managed_startup_failure(incident)

    def add_task(self, name: str, callback: Callable[[], None]) -> None:
        """Add one GUI startup task to the owned queue."""

        self._require_queue().add(name, callback)

    def start_queue(self) -> None:
        """Start the owned GUI startup queue."""

        self._require_queue().start()

    def cancel_queue(self) -> None:
        """Cancel the owned GUI startup queue."""

        self._require_queue().cancel()

    @property
    def queue(self) -> GuiStartupTaskQueue:
        """Return the owned GUI startup queue for startup task ordering helpers."""

        return self._require_queue()

    def _require_queue(self) -> GuiStartupTaskQueue:
        """Return the queue after construction has completed."""

        if self._gui_queue is None:
            raise RuntimeError("Ready-shell GUI startup queue is not available.")
        return self._gui_queue


def create_ready_shell_failure_queue(
    *,
    is_startup_cancelled: Callable[[], bool],
    mark_startup_cancelled: Callable[[], None],
    readiness_timers: Callable[[], Sequence[StartupTimerProtocol]],
    runtime_compatibility_probes: Callable[
        [], Sequence[RuntimeCompatibilityProbeProtocol]
    ],
    managed_comfy_state: Callable[[], object | None],
    splash: Callable[[], StartupProgressSplash | None],
    cleanup: Callable[[], object],
    quit_app: Callable[[], None],
    trace_fields: Callable[[], dict[str, object]],
    managed_failure_report_factory: Callable[[ComfyStartupIncident], Any],
    present_startup_failure_report: Callable[[Any], None],
    scheduler: Callable[[int, Callable[[], None]], None],
    startup_timer: StartupTimer,
) -> ReadyShellFailureQueue:
    """Create the live ready-shell failure queue."""

    return ReadyShellFailureQueue(
        is_startup_cancelled=is_startup_cancelled,
        mark_startup_cancelled=mark_startup_cancelled,
        readiness_timers=readiness_timers,
        runtime_compatibility_probes=runtime_compatibility_probes,
        managed_comfy_state=managed_comfy_state,
        splash=splash,
        cleanup=cleanup,
        quit_app=quit_app,
        trace_fields=trace_fields,
        managed_failure_report_factory=managed_failure_report_factory,
        present_startup_failure_report=present_startup_failure_report,
        scheduler=scheduler,
        startup_timer=startup_timer,
    )
