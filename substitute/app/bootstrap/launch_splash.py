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

"""Provide launch-splash clients for bootstrap startup orchestration."""

from __future__ import annotations

from collections.abc import Callable
from itertools import count
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from typing import IO, Any, Protocol

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.shared.logging.logger import (
    get_logger,
    log_error,
    log_info,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.launch_splash")
_HELPER_MODULE = "substitute.app.bootstrap.splash_process"
_CLOSE_TIMEOUT_SECONDS = 2.0
_SPLASH_READER_REQUEST_IDS = count(1)

SplashCancelCallback = Callable[[], None]
ProcessPumpWork = Callable[[CancellationSource], None]
ProcessPumpTaskFactory = Callable[
    [TaskIdentity, ExecutionContext, ProcessPumpWork, str],
    "ProcessPumpTaskHandle",
]


class ProcessPumpTaskHandle(Protocol):
    """Describe a launch-splash process-pump task handle."""

    @property
    def is_finished(self) -> bool:
        """Return whether the process-pump task has finished."""

    def stop(self, *, reason: str) -> None:
        """Request task cancellation."""


class LaunchSplashCancelRelay:
    """Buffer launch-splash cancellation until bootstrap can handle it."""

    def __init__(self) -> None:
        """Initialize the relay without an attached bootstrap callback."""

        self._lock = Lock()
        self._callback: SplashCancelCallback | None = None
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Record a cancel request and notify the attached callback if available."""

        callback: SplashCancelCallback | None
        with self._lock:
            self._cancel_requested = True
            callback = self._callback
        if callback is not None:
            callback()

    def connect(self, callback: SplashCancelCallback) -> None:
        """Attach bootstrap cancellation handling and replay pending cancellation."""

        should_replay = False
        with self._lock:
            self._callback = callback
            should_replay = self._cancel_requested
        if should_replay:
            callback()

    def cancel_requested(self) -> bool:
        """Return whether the splash helper has already requested cancellation."""

        with self._lock:
            return self._cancel_requested


class LaunchSplashClient(Protocol):
    """Describe the narrow launch-splash surface used by startup."""

    def append_log(self, line: str) -> None:
        """Append one status or log line to the launch splash."""

    def close(self) -> None:
        """Close the launch splash if it is still available."""


class NullLaunchSplashClient:
    """Ignore launch-splash calls when the helper is unavailable."""

    def append_log(self, line: str) -> None:
        """Discard one splash line."""

        _ = line

    def close(self) -> None:
        """Complete a no-op close."""


class InProcessLaunchSplashClient:
    """Adapt an existing in-process splash widget to the launch-splash protocol."""

    def __init__(self, splash_window: Any) -> None:
        """Store the concrete splash widget used by fallback and tests."""

        self._splash_window = splash_window

    def append_log(self, line: str) -> None:
        """Append one line to the in-process splash widget."""

        self._splash_window.append_log(line)

    def close(self) -> None:
        """Close the in-process splash widget."""

        self._splash_window.close()


class LaunchSplashProcessClient:
    """Send launch-splash messages to an internal helper process."""

    def __init__(
        self,
        *,
        process: subprocess.Popen[str],
        stdin: IO[str],
        stdout: IO[str] | None = None,
        stderr: IO[str] | None = None,
        on_cancel_requested: SplashCancelCallback | None = None,
        process_pump_task_factory: ProcessPumpTaskFactory,
    ) -> None:
        """Store process handles needed for splash IPC and cleanup."""

        self._process = process
        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self._on_cancel_requested = on_cancel_requested
        self._lock = Lock()
        self._reader_tasks: list[ProcessPumpTaskHandle] = []
        self._write_failure_logged = False
        self._closed = False
        if self._stderr is not None:
            stderr_stream = self._stderr
            self._reader_tasks.append(
                _start_splash_reader_task(
                    task_factory=process_pump_task_factory,
                    domain="launch_splash_stderr_reader",
                    operation="launch_splash_stderr_reader",
                    reason="launch_splash_helper_stderr",
                    thread_name="substitute-launch-splash-stderr",
                    work=lambda cancellation: _read_helper_stderr(
                        stream=stderr_stream,
                        helper_pid=self._process.pid,
                        cancellation=cancellation,
                    ),
                )
            )
        if self._stdout is not None and self._on_cancel_requested is not None:
            stdout_stream = self._stdout
            cancel_requested = self._on_cancel_requested
            self._reader_tasks.append(
                _start_splash_reader_task(
                    task_factory=process_pump_task_factory,
                    domain="launch_splash_event_reader",
                    operation="launch_splash_event_reader",
                    reason="launch_splash_helper_events",
                    thread_name="substitute-launch-splash-events",
                    work=lambda cancellation: _read_helper_events(
                        stream=stdout_stream,
                        on_cancel_requested=cancel_requested,
                        cancellation=cancellation,
                    ),
                )
            )

    @classmethod
    def start(
        cls,
        *,
        parent_pid: int,
        python_executable: str = sys.executable,
        cwd: Path | None = None,
        theme_mode: str | None = None,
        accent_color: str | None = None,
        backdrop_mode: str | None = None,
        on_cancel_requested: SplashCancelCallback | None = None,
        process_pump_task_factory: ProcessPumpTaskFactory,
        popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> LaunchSplashClient:
        """Start the helper process and return a disposable splash client."""

        command = [
            python_executable,
            "-m",
            _HELPER_MODULE,
            "--parent-pid",
            str(parent_pid),
        ]
        if theme_mode:
            command.extend(["--theme-mode", theme_mode])
        if accent_color:
            command.extend(["--accent-color", accent_color])
        if backdrop_mode:
            command.extend(["--backdrop-mode", backdrop_mode])
        try:
            process = popen(
                command,
                cwd=str(cwd) if cwd is not None else None,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            log_warning(
                _LOGGER,
                "Launch splash helper failed to start",
                error=error,
            )
            return NullLaunchSplashClient()

        if process.stdin is None:
            log_warning(_LOGGER, "Launch splash helper started without stdin")
            _terminate_process(process)
            return NullLaunchSplashClient()

        stdout = process.stdout
        if on_cancel_requested is not None and stdout is None:
            log_warning(_LOGGER, "Launch splash helper started without stdout")
            _terminate_process(process)
            return NullLaunchSplashClient()

        log_info(
            _LOGGER,
            "Launch splash helper started",
            parent_pid=parent_pid,
            helper_pid=process.pid,
        )
        return cls(
            process=process,
            stdin=process.stdin,
            stdout=stdout,
            stderr=process.stderr,
            on_cancel_requested=on_cancel_requested,
            process_pump_task_factory=process_pump_task_factory,
        )

    def append_log(self, line: str) -> None:
        """Send one log line to the helper process."""

        self._send({"type": "log", "line": line})

    def close(self) -> None:
        """Ask the helper to close, then clean up if it does not exit promptly."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._write_unlocked({"type": "close"})
            except OSError as error:
                self._log_write_failure(error)
            try:
                self._stdin.close()
            except OSError as error:
                self._log_write_failure(error)

        try:
            self._process.wait(timeout=_CLOSE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            log_warning(
                _LOGGER,
                "Launch splash helper did not exit after close request",
                helper_pid=self._process.pid,
            )
            _terminate_process(self._process)
        self._stop_reader_tasks(reason="launch_splash_closed")

    def _send(self, message: dict[str, str]) -> None:
        """Write one JSON message unless the client has been closed."""

        with self._lock:
            if self._closed:
                return
            try:
                self._write_unlocked(message)
            except OSError as error:
                self._log_write_failure(error)

    def _write_unlocked(self, message: dict[str, str]) -> None:
        """Serialize one helper message while the caller holds the write lock."""

        self._stdin.write(encode_splash_message(message) + "\n")
        self._stdin.flush()

    def _log_write_failure(self, error: OSError) -> None:
        """Log one splash IPC write failure without flooding startup logs."""

        if self._write_failure_logged:
            return
        self._write_failure_logged = True
        log_warning(
            _LOGGER,
            "Launch splash helper IPC failed",
            helper_pid=self._process.pid,
            error=error,
        )

    def _stop_reader_tasks(self, *, reason: str) -> None:
        """Request all helper reader tasks to stop."""

        for task in self._reader_tasks:
            task.stop(reason=reason)


def start_launch_splash(
    *,
    startup_timer: StartupTimer | None = None,
    cwd: Path | None = None,
    theme_mode: str | None = None,
    accent_color: str | None = None,
    backdrop_mode: str | None = None,
    on_cancel_requested: SplashCancelCallback | None = None,
    process_pump_task_factory: ProcessPumpTaskFactory,
) -> LaunchSplashClient:
    """Start the process-backed launch splash for a ready-launch path."""

    if startup_timer is None:
        return LaunchSplashProcessClient.start(
            parent_pid=os.getpid(),
            cwd=cwd,
            theme_mode=theme_mode,
            accent_color=accent_color,
            backdrop_mode=backdrop_mode,
            on_cancel_requested=on_cancel_requested,
            process_pump_task_factory=process_pump_task_factory,
        )
    with startup_timer.phase("startup.launch_splash_helper"):
        return LaunchSplashProcessClient.start(
            parent_pid=os.getpid(),
            cwd=cwd,
            theme_mode=theme_mode,
            accent_color=accent_color,
            backdrop_mode=backdrop_mode,
            on_cancel_requested=on_cancel_requested,
            process_pump_task_factory=process_pump_task_factory,
        )


def encode_splash_message(message: dict[str, str]) -> str:
    """Return one compact JSON splash IPC message."""

    return json.dumps(message, ensure_ascii=True, separators=(",", ":"))


def decode_splash_helper_event(line: str) -> dict[str, str] | None:
    """Decode one newline-delimited helper-to-parent splash event."""

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    message_type = payload.get("type")
    if message_type != "cancel":
        return None
    return {"type": message_type}


def _read_helper_events(
    *,
    stream: IO[str],
    on_cancel_requested: SplashCancelCallback,
    cancellation: CancellationSource,
) -> None:
    """Read helper stdout events and dispatch supported parent callbacks."""

    try:
        for line in stream:
            if cancellation.is_cancelled:
                return
            event = decode_splash_helper_event(line)
            if event is not None and event["type"] == "cancel":
                on_cancel_requested()
    except OSError as error:
        log_warning(
            _LOGGER,
            "Launch splash helper event stream failed",
            error=error,
        )


def _read_helper_stderr(
    *,
    stream: IO[str],
    helper_pid: int,
    cancellation: CancellationSource,
) -> None:
    """Forward launch-splash helper stderr into normal application logging."""

    try:
        for line in stream:
            if cancellation.is_cancelled:
                return
            stderr_line = line.rstrip("\r\n")
            if stderr_line:
                log_error(
                    _LOGGER,
                    "Launch splash helper stderr",
                    helper_pid=helper_pid,
                    line=stderr_line,
                )
    except OSError as error:
        log_warning(
            _LOGGER,
            "Launch splash helper stderr stream failed",
            helper_pid=helper_pid,
            error=error,
        )


def _start_splash_reader_task(
    *,
    task_factory: ProcessPumpTaskFactory,
    domain: str,
    operation: str,
    reason: str,
    thread_name: str,
    work: ProcessPumpWork,
) -> ProcessPumpTaskHandle:
    """Start one long-lived launch-splash helper reader task."""

    return task_factory(
        TaskIdentity(
            request_id=next(_SPLASH_READER_REQUEST_IDS),
            domain=domain,
        ),
        ExecutionContext(
            operation=operation,
            reason=reason,
            lane="process_pump",
        ),
        work,
        thread_name,
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    """Terminate one helper process without affecting the main app or ComfyUI."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1.0)


__all__ = [
    "InProcessLaunchSplashClient",
    "LaunchSplashCancelRelay",
    "LaunchSplashClient",
    "LaunchSplashProcessClient",
    "NullLaunchSplashClient",
    "decode_splash_helper_event",
    "encode_splash_message",
    "start_launch_splash",
]
