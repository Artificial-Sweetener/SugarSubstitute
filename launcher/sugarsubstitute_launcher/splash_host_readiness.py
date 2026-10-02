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

"""Observe splash bootstrap through the supervised application's startup budget."""

from collections.abc import Callable
import logging
import subprocess
from threading import Event, Thread
import time

from launcher.sugarsubstitute_launcher.application_startup_contract import (
    DEFAULT_READINESS_TIMEOUT_SECONDS,
)
from sugarsubstitute_shared.supervised_text_process import SupervisedTextProcess

_LOGGER = logging.getLogger(__name__)
_SLOW_BOOTSTRAP_SECONDS = 8.0
_POLL_SECONDS = 0.05


def read_splash_host_ready_line(
    process: SupervisedTextProcess,
    *,
    timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    wait: Callable[[Event, float], bool] | None = None,
) -> str:
    """Retain a slow live host while enforcing terminal startup and pipe ownership.

    Eight seconds identifies slow bootstrap, not a failed application. The
    application's existing startup deadline bounds a stalled host. EOF and
    reader failures still fail immediately; the caller owns family cleanup.
    """
    if timeout_seconds <= 0:
        raise ValueError("Splash bootstrap deadline must be positive.")
    completed = Event()
    line = ""
    error: BaseException | None = None

    def read() -> None:
        """Publish one pipe result before signaling completion across threads."""
        nonlocal line, error
        try:
            line = process.stdout.readline()
        except (OSError, ValueError) as failure:
            error = failure
        finally:
            completed.set()

    Thread(target=read, name="sugarsubstitute-splash-ready-reader", daemon=True).start()
    wait_for_result = wait or (lambda signal, seconds: signal.wait(seconds))
    started = monotonic()
    slow_reported = False
    while not completed.is_set():
        elapsed = monotonic() - started
        if elapsed >= timeout_seconds:
            raise subprocess.TimeoutExpired("splash host ready", timeout_seconds)
        if elapsed >= _SLOW_BOOTSTRAP_SECONDS and not slow_reported:
            _LOGGER.info(
                "Splash host is still initializing; retaining supervised startup"
            )
            slow_reported = True
        wait_for_result(completed, min(_POLL_SECONDS, timeout_seconds - elapsed))
    if error is not None:
        raise ValueError("Splash host ready stream failed.") from error
    if not line.strip():
        raise ValueError("Splash host exited before sending a ready message.")
    return line
