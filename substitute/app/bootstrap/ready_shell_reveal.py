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

"""Reveal the ready application shell and publish observable readiness."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import ContextManager, Protocol

from substitute.app.bootstrap.application_readiness import (
    schedule_main_shell_readiness_receipt,
)
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.app.bootstrap.startup_warmup_controller import (
    StartupWarmupState,
    connect_restore_finalized_warmups,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info


_LOGGER = get_logger("app.bootstrap.ready_shell_reveal")


class ReadyShellRevealTimerProtocol(Protocol):
    """Measure and mark ready-shell reveal phases."""

    def phase(self, name: str) -> ContextManager[None]:
        """Return a context manager for the named phase."""

    def mark(self, name: str) -> object:
        """Record one named startup milestone."""


class ReadyShellSplashProtocol(Protocol):
    """Close the launch splash when the ready shell becomes visible."""

    def close(self) -> object:
        """Close the splash surface."""


ReadyShellSplashProvider = Callable[[], ReadyShellSplashProtocol | None]
ReadyShellSplashSetter = Callable[[ReadyShellSplashProtocol | None], None]


@dataclass(frozen=True)
class ReadyShellRevealResult:
    """Return updated startup references after revealing the ready shell."""

    shell_frame: object
    splash: ReadyShellSplashProtocol | None


def reveal_ready_shell_main_window(
    *,
    splash: ReadyShellSplashProtocol | None,
    shell_frame: object,
    initial_shell_placement: object | None,
    comfy_http_ready: bool,
    startup_timer: ReadyShellRevealTimerProtocol,
    show_built_main_window: Callable[..., object],
    set_current_shell: Callable[[object], None],
    update_backend_state: Callable[[str], object],
    connect_restore_finalized_warmups: Callable[[], object],
    request_startup_diagnostics_update: Callable[[], object],
    schedule_post_show_hydration: Callable[[], object],
    trace_fields: Callable[[], Mapping[str, object]],
    schedule_readiness_receipt: Callable[[], bool] = (
        schedule_main_shell_readiness_receipt
    ),
) -> ReadyShellRevealResult:
    """Close splash, show the ready shell, and publish post-event-loop readiness."""

    active_splash = splash
    try:
        if active_splash is not None:
            with startup_timer.phase("startup.close_launch_splash"):
                with trace_span("launch_splash.close"):
                    active_splash.close()
            active_splash = None
            startup_timer.mark("splash_closed")
            trace_mark("launch_splash.closed", **dict(trace_fields()))
    except Exception:
        log_exception(
            _LOGGER,
            "Failed to close splash after readiness check",
        )

    with startup_timer.phase("startup.show_main_window"):
        with trace_span("main_shell.show"):
            revealed_shell_frame = show_built_main_window(
                shell_frame,
                initial_shell_placement=initial_shell_placement,
            )
    set_current_shell(revealed_shell_frame)
    startup_timer.mark("main_shell_shown")
    trace_mark("main_shell.shown", **dict(trace_fields()))
    schedule_readiness_receipt()
    update_backend_state("ready" if comfy_http_ready else "starting")
    log_info(
        _LOGGER,
        "Main shell revealed",
        comfy_http_ready=comfy_http_ready,
    )
    connect_restore_finalized_warmups()
    request_startup_diagnostics_update()
    schedule_post_show_hydration()
    return ReadyShellRevealResult(
        shell_frame=revealed_shell_frame,
        splash=active_splash,
    )


class ReadyShellRevealTask:
    """Adapt live startup state into the ready-shell reveal task."""

    def __init__(
        self,
        *,
        splash: Callable[[], ReadyShellSplashProtocol | None],
        shell_frame: Callable[[], object | None],
        initial_shell_placement: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        startup_timer: ReadyShellRevealTimerProtocol,
        show_built_main_window: Callable[..., object],
        set_current_shell: Callable[[object], None],
        update_backend_state: Callable[[str], object],
        startup_warmup_state: StartupWarmupState,
        schedule_warmups: Callable[[str], None],
        request_startup_diagnostics_update: Callable[[object], object],
        schedule_post_show_hydration: Callable[[], object],
        set_shell_frame: Callable[[object], None],
        set_splash: Callable[[ReadyShellSplashProtocol | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> None:
        """Store ports required to reveal the ready shell."""

        self._splash = splash
        self._shell_frame = shell_frame
        self._initial_shell_placement = initial_shell_placement
        self._comfy_http_ready = comfy_http_ready
        self._startup_timer = startup_timer
        self._show_built_main_window = show_built_main_window
        self._set_current_shell = set_current_shell
        self._update_backend_state = update_backend_state
        self._startup_warmup_state = startup_warmup_state
        self._schedule_warmups = schedule_warmups
        self._request_startup_diagnostics_update = request_startup_diagnostics_update
        self._schedule_post_show_hydration = schedule_post_show_hydration
        self._set_shell_frame = set_shell_frame
        self._set_splash = set_splash
        self._trace_fields = trace_fields

    def reveal(self, main_window: object) -> ReadyShellRevealResult:
        """Reveal the shell using current splash and shell-frame state."""

        shell_frame = self._shell_frame()
        assert shell_frame is not None
        reveal_result = reveal_ready_shell_main_window(
            splash=self._splash(),
            shell_frame=shell_frame,
            initial_shell_placement=self._initial_shell_placement(),
            comfy_http_ready=self._comfy_http_ready(),
            startup_timer=self._startup_timer,
            show_built_main_window=self._show_built_main_window,
            set_current_shell=self._set_current_shell,
            update_backend_state=self._update_backend_state,
            connect_restore_finalized_warmups=lambda: (
                connect_ready_shell_restore_finalized_warmups(
                    state=self._startup_warmup_state,
                    main_window=main_window,
                    schedule_warmups=self._schedule_warmups,
                    trace_fields=self._trace_fields,
                )
            ),
            request_startup_diagnostics_update=lambda: (
                self._request_startup_diagnostics_update(main_window)
            ),
            schedule_post_show_hydration=self._schedule_post_show_hydration,
            trace_fields=self._trace_fields,
        )
        self._set_shell_frame(reveal_result.shell_frame)
        self._set_splash(reveal_result.splash)
        return reveal_result


def create_ready_shell_reveal_task(
    *,
    splash: Callable[[], ReadyShellSplashProtocol | None],
    shell_frame: Callable[[], object | None],
    initial_shell_placement: Callable[[], object | None],
    comfy_http_ready: Callable[[], bool],
    startup_timer: ReadyShellRevealTimerProtocol,
    show_built_main_window: Callable[..., object],
    set_current_shell: Callable[[object], None],
    update_backend_state: Callable[[str], object],
    startup_warmup_state: StartupWarmupState,
    schedule_warmups: Callable[[str], None],
    request_startup_diagnostics_update: Callable[[object], object],
    schedule_post_show_hydration: Callable[[], object],
    set_shell_frame: Callable[[object], None],
    set_splash: Callable[[ReadyShellSplashProtocol | None], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> ReadyShellRevealTask:
    """Create the live ready-shell reveal task."""

    return ReadyShellRevealTask(
        splash=splash,
        shell_frame=shell_frame,
        initial_shell_placement=initial_shell_placement,
        comfy_http_ready=comfy_http_ready,
        startup_timer=startup_timer,
        show_built_main_window=show_built_main_window,
        set_current_shell=set_current_shell,
        update_backend_state=update_backend_state,
        startup_warmup_state=startup_warmup_state,
        schedule_warmups=schedule_warmups,
        request_startup_diagnostics_update=request_startup_diagnostics_update,
        schedule_post_show_hydration=schedule_post_show_hydration,
        set_shell_frame=set_shell_frame,
        set_splash=set_splash,
        trace_fields=trace_fields,
    )


def connect_ready_shell_restore_finalized_warmups(
    *,
    state: StartupWarmupState,
    main_window: object,
    schedule_warmups: Callable[[str], None],
    trace_fields: Callable[[], Mapping[str, object]],
) -> None:
    """Connect restore finalization to background warmup scheduling."""

    connect_restore_finalized_warmups(
        state=state,
        main_window=main_window,
        schedule_warmups=schedule_warmups,
        trace_fields=lambda: dict(trace_fields()),
    )


__all__ = [
    "ReadyShellRevealResult",
    "ReadyShellRevealTask",
    "ReadyShellRevealTimerProtocol",
    "ReadyShellSplashProvider",
    "ReadyShellSplashProtocol",
    "ReadyShellSplashSetter",
    "connect_ready_shell_restore_finalized_warmups",
    "create_ready_shell_reveal_task",
    "reveal_ready_shell_main_window",
]
