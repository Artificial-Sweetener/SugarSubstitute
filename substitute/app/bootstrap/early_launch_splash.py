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

"""Own early launch-splash startup before full bootstrap composition exists."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, cast

from sugarsubstitute_shared.launch_splash import (
    SocketSplashSessionClient,
    SplashSessionSpec,
    splash_cancel_signal_path,
    splash_session_from_args,
)
from sugarsubstitute_shared.launch_splash.session import validate_splash_session_spec

from substitute.application.execution import (
    CancellationSource,
    DirectExecutionDispatcher,
    ExecutionContext,
    TaskIdentity,
)
from substitute.app.bootstrap.launch_splash import (
    LaunchSplashCancelRelay,
    LaunchSplashClient,
    NullLaunchSplashClient,
    ProcessPumpTaskHandle,
    ProcessPumpWork,
    decode_splash_helper_event,
)
from substitute.app.bootstrap.standalone_long_lived_execution import (
    StandaloneLongLivedExecutionOwner,
)
from substitute.shared.logging.logger import get_logger, log_warning


_LOGGER = get_logger("app.bootstrap.early_launch_splash")
_SHARED_SPLASH_HOST_MODULE = "substitute.app.bootstrap.shared_splash_host"
_CANCEL_SIGNAL_POLL_SECONDS = 0.25
_CANCEL_SIGNAL_MAX_SECONDS = 1800.0


def start_early_launch_splash(
    argv: list[str],
    app_root: Path,
) -> tuple[LaunchSplashClient | None, LaunchSplashCancelRelay | None]:
    """Start the early splash helper before the full app runtime is composed."""

    if "--no-comfy" in argv or os.environ.get("SUGAR_SUBSTITUTE_STARTUP_HARNESS"):
        return None, None

    cancel_relay = LaunchSplashCancelRelay()
    adopted_spec: SplashSessionSpec | None = None
    splash, adopted_spec = _adopt_existing_launch_splash(argv)
    adopted_existing_splash = splash is not None
    if splash is None:
        splash, adopted_spec = _start_new_launch_splash(app_root, cancel_relay)
    if isinstance(splash, NullLaunchSplashClient):
        return None, None
    if adopted_spec is not None:
        _start_cancel_signal_watcher(
            spec=adopted_spec,
            cancel_relay=cancel_relay,
            process_pump_task_factory=_create_early_process_pump_task,
        )
    try:
        splash.append_log("Starting SugarSubstitute.")
    except OSError as error:
        if adopted_existing_splash:
            log_warning(
                _LOGGER,
                "Failed to adopt launcher splash session; starting app splash",
                error=error,
            )
            splash, adopted_spec = _start_new_launch_splash(app_root, cancel_relay)
            if isinstance(splash, NullLaunchSplashClient):
                return None, None
            if adopted_spec is not None:
                _start_cancel_signal_watcher(
                    spec=adopted_spec,
                    cancel_relay=cancel_relay,
                    process_pump_task_factory=_create_early_process_pump_task,
                )
            splash.append_log("Starting SugarSubstitute.")
        else:
            raise
    return splash, cancel_relay


def _adopt_existing_launch_splash(
    argv: list[str],
) -> tuple[LaunchSplashClient | None, SplashSessionSpec | None]:
    """Return a client for a launcher-provided splash session when available."""

    try:
        spec = splash_session_from_args(argv)
    except ValueError as error:
        log_warning(
            _LOGGER,
            "Ignoring invalid launcher splash session arguments",
            error=error,
        )
        return None, None
    if spec is None:
        return None, None
    return _connect_splash_session(spec), spec


def _connect_splash_session(spec: SplashSessionSpec) -> LaunchSplashClient:
    """Connect to an existing shared splash session."""

    return cast(LaunchSplashClient, SocketSplashSessionClient(spec))


def _start_new_launch_splash(
    app_root: Path,
    cancel_relay: LaunchSplashCancelRelay,
) -> tuple[LaunchSplashClient, SplashSessionSpec | None]:
    """Start an app-owned shared launch-splash session."""

    return start_shared_launch_splash(
        app_root=app_root,
        on_cancel_requested=cancel_relay.request_cancel,
        process_pump_task_factory=_create_early_process_pump_task,
    )


def start_shared_launch_splash(
    *,
    app_root: Path,
    on_cancel_requested: Callable[[], None],
    process_pump_task_factory: Callable[
        [TaskIdentity, ExecutionContext, ProcessPumpWork, str],
        ProcessPumpTaskHandle,
    ],
) -> tuple[LaunchSplashClient, SplashSessionSpec | None]:
    """Start the shared splash host process for direct app launches."""

    try:
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                _SHARED_SPLASH_HOST_MODULE,
            ],
            cwd=app_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except OSError as error:
        log_warning(_LOGGER, "Shared launch splash host failed to start", error=error)
        return NullLaunchSplashClient(), None
    if process.stdout is None:
        log_warning(_LOGGER, "Shared launch splash host started without stdout")
        return NullLaunchSplashClient(), None
    try:
        spec = _read_shared_splash_ready_spec(process)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        log_warning(
            _LOGGER, "Shared launch splash host did not become ready", error=error
        )
        return NullLaunchSplashClient(), None

    _start_shared_splash_stdout_reader(
        stream=process.stdout,
        on_cancel_requested=on_cancel_requested,
        process_pump_task_factory=process_pump_task_factory,
    )
    if process.stderr is not None:
        stderr_stream = process.stderr
        process_pump_task_factory(
            TaskIdentity(request_id=2, domain="shared_launch_splash_stderr_reader"),
            ExecutionContext(
                operation="shared_launch_splash_stderr_reader",
                reason="shared_launch_splash_host_stderr",
                lane="process_pump",
            ),
            lambda cancellation: _drain_shared_splash_stderr(
                stream=stderr_stream,
                cancellation=cancellation,
            ),
            "substitute-shared-launch-splash-stderr",
        )
    return cast(LaunchSplashClient, SocketSplashSessionClient(spec)), spec


def _start_cancel_signal_watcher(
    *,
    spec: SplashSessionSpec,
    cancel_relay: LaunchSplashCancelRelay,
    process_pump_task_factory: Callable[
        [TaskIdentity, ExecutionContext, ProcessPumpWork, str],
        ProcessPumpTaskHandle,
    ],
) -> None:
    """Watch for host-originated cancel signals after launcher handoff."""

    cancel_path = splash_cancel_signal_path(spec)
    process_pump_task_factory(
        TaskIdentity(request_id=3, domain="shared_launch_splash_cancel_watcher"),
        ExecutionContext(
            operation="shared_launch_splash_cancel_watcher",
            reason="shared_launch_splash_cancel_signal",
            lane="process_pump",
        ),
        lambda cancellation: _watch_cancel_signal(
            cancel_path=cancel_path,
            cancel_relay=cancel_relay,
            cancellation=cancellation,
        ),
        "substitute-shared-launch-splash-cancel",
    )


def _watch_cancel_signal(
    *,
    cancel_path: Path,
    cancel_relay: LaunchSplashCancelRelay,
    cancellation: CancellationSource,
) -> None:
    """Poll the shared splash cancel signal until cancellation or timeout."""

    deadline = time.monotonic() + _CANCEL_SIGNAL_MAX_SECONDS
    while time.monotonic() < deadline:
        if cancellation.is_cancelled:
            return
        if cancel_path.exists():
            cancel_relay.request_cancel()
            return
        time.sleep(_CANCEL_SIGNAL_POLL_SECONDS)


def _read_shared_splash_ready_spec(
    process: subprocess.Popen[str],
) -> SplashSessionSpec:
    """Read the shared splash host ready line from stdout."""

    stdout = process.stdout
    if stdout is None:
        raise ValueError("Shared splash host stdout is unavailable.")
    line = stdout.readline()
    payload = json.loads(line)
    if not isinstance(payload, dict) or payload.get("type") != "ready":
        raise ValueError("Shared splash host did not send a ready message.")
    endpoint = payload.get("endpoint")
    token = payload.get("token")
    host_pid = payload.get("host_pid")
    if not isinstance(endpoint, str) or not isinstance(token, str):
        raise ValueError("Shared splash host ready message is incomplete.")
    if not isinstance(host_pid, int):
        raise ValueError("Shared splash host PID is invalid.")
    host, separator, raw_port = endpoint.rpartition(":")
    if not separator:
        raise ValueError("Shared splash host endpoint is invalid.")
    spec = SplashSessionSpec(
        host=host,
        port=int(raw_port),
        token=token,
        host_pid=host_pid,
    )
    validate_splash_session_spec(spec)
    return spec


def _start_shared_splash_stdout_reader(
    *,
    stream: IO[str],
    on_cancel_requested: Callable[[], None],
    process_pump_task_factory: Callable[
        [TaskIdentity, ExecutionContext, ProcessPumpWork, str],
        ProcessPumpTaskHandle,
    ],
) -> ProcessPumpTaskHandle:
    """Start reading cancel events from the shared splash host stdout."""

    return process_pump_task_factory(
        TaskIdentity(request_id=1, domain="shared_launch_splash_event_reader"),
        ExecutionContext(
            operation="shared_launch_splash_event_reader",
            reason="shared_launch_splash_host_events",
            lane="process_pump",
        ),
        lambda cancellation: _read_shared_splash_events(
            stream=stream,
            on_cancel_requested=on_cancel_requested,
            cancellation=cancellation,
        ),
        "substitute-shared-launch-splash-events",
    )


def _read_shared_splash_events(
    *,
    stream: IO[str],
    on_cancel_requested: Callable[[], None],
    cancellation: CancellationSource,
) -> None:
    """Read shared splash host stdout events after the ready line."""

    for line in stream:
        if cancellation.is_cancelled:
            return
        event = decode_splash_helper_event(line)
        if event is not None and event["type"] == "cancel":
            on_cancel_requested()


def _drain_shared_splash_stderr(
    *,
    stream: IO[str],
    cancellation: CancellationSource,
) -> None:
    """Forward shared splash host stderr into app logging."""

    for line in stream:
        if cancellation.is_cancelled:
            return
        stderr_line = line.rstrip("\r\n")
        if stderr_line:
            log_warning(_LOGGER, "Shared launch splash host stderr", line=stderr_line)


def _create_early_process_pump_task(
    identity: TaskIdentity,
    context: ExecutionContext,
    work: ProcessPumpWork,
    thread_name: str,
) -> ProcessPumpTaskHandle:
    """Create an early process-pump task before `ExecutionRuntime` exists."""

    owner = StandaloneLongLivedExecutionOwner(dispatcher=DirectExecutionDispatcher())
    return owner.start(
        identity=identity,
        context=context,
        work=work,
        thread_name=thread_name,
    )


__all__ = ["start_early_launch_splash"]
