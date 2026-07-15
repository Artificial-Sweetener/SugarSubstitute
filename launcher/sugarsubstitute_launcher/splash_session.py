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

"""Start and hand off shared launch-splash sessions from the launcher."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import IO, Any

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime import runtime_environment
from sugarsubstitute_shared.launch_splash import (
    SocketSplashSessionClient,
    SplashSessionSpec,
    splash_session_args,
)
from sugarsubstitute_shared.launch_splash.session import validate_splash_session_spec


_LOGGER = logging.getLogger(__name__)
_HOST_MODULE = "substitute.app.bootstrap.shared_splash_host"
_READY_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True, slots=True)
class LauncherSplashSession:
    """Carry a launcher-created splash session into app handoff."""

    client: SocketSplashSessionClient
    app_arguments: tuple[str, ...]
    host_pid: int


def start_launcher_splash_session(
    *,
    layout: InstallLayout,
    popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
) -> LauncherSplashSession | None:
    """Start the shared splash host process for production app handoff."""

    try:
        process = _start_splash_host_process(layout=layout, popen=popen)
        spec = _read_ready_spec(process=process, timeout_seconds=_READY_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        _LOGGER.warning("Shared launcher splash session unavailable: %r", error)
        return None

    _start_background_pipe_reader(
        stream=process.stdout,
        label="stdout",
        ignore_ready_message=True,
    )
    _start_background_pipe_reader(
        stream=process.stderr,
        label="stderr",
        ignore_ready_message=False,
    )
    return LauncherSplashSession(
        client=SocketSplashSessionClient(spec),
        app_arguments=tuple(splash_session_args(spec)),
        host_pid=spec.host_pid,
    )


def _start_splash_host_process(
    *,
    layout: InstallLayout,
    popen: Callable[..., subprocess.Popen[str]],
) -> subprocess.Popen[str]:
    """Launch the app-payload splash host without importing app code."""

    command = [
        str(layout.runtime_python),
        "-m",
        _HOST_MODULE,
    ]
    return popen(
        command,
        cwd=str(layout.root),
        env=runtime_environment(layout=layout),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_hidden_process_creation_flags(),
        startupinfo=_hidden_process_startup_info(),
        shell=False,
    )


def _read_ready_spec(
    *,
    process: subprocess.Popen[str],
    timeout_seconds: float,
) -> SplashSessionSpec:
    """Read and validate the host process ready line."""

    stdout = process.stdout
    if stdout is None:
        raise ValueError("Splash host started without stdout.")

    line = _readline_with_timeout(stdout, timeout_seconds=timeout_seconds)
    payload = json.loads(line)
    if not isinstance(payload, dict) or payload.get("type") != "ready":
        raise ValueError("Splash host did not send a ready message.")
    endpoint = _required_string(payload, "endpoint")
    host, port = _parse_endpoint(endpoint)
    spec = SplashSessionSpec(
        host=host,
        port=port,
        token=_required_string(payload, "token"),
        host_pid=_required_int(payload, "host_pid"),
    )
    validate_splash_session_spec(spec)
    return spec


def _readline_with_timeout(stream: IO[str], *, timeout_seconds: float) -> str:
    """Read one text line with a bounded wait."""

    result: dict[str, str | BaseException] = {}

    def _reader() -> None:
        try:
            result["line"] = stream.readline()
        except BaseException as error:  # pragma: no cover - defensive thread bridge
            result["error"] = error

    thread = threading.Thread(
        target=_reader,
        name="sugarsubstitute-splash-ready-reader",
        daemon=True,
    )
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise subprocess.TimeoutExpired("splash host ready", timeout_seconds)
    error = result.get("error")
    if isinstance(error, BaseException):
        raise ValueError("Splash host ready stream failed.") from error
    line = result.get("line")
    if not isinstance(line, str) or not line.strip():
        raise ValueError("Splash host exited before sending a ready message.")
    return line


def _start_background_pipe_reader(
    *,
    stream: IO[str] | None,
    label: str,
    ignore_ready_message: bool,
) -> None:
    """Drain a splash host pipe so the helper cannot block on output."""

    if stream is None:
        return

    def _reader() -> None:
        for raw_line in stream:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            if ignore_ready_message and _is_ready_message(line):
                continue
            _LOGGER.debug("Splash host %s: %s", label, line)

    thread = threading.Thread(
        target=_reader,
        name=f"sugarsubstitute-splash-host-{label}",
        daemon=True,
    )
    thread.start()


def _is_ready_message(line: str) -> bool:
    """Return whether one host stdout line is the sensitive ready payload."""

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("type") == "ready"


def _required_string(payload: dict[Any, Any], key: str) -> str:
    """Read one required string from a decoded ready payload."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Splash host ready field is invalid: {key}")
    return value


def _required_int(payload: dict[Any, Any], key: str) -> int:
    """Read one required integer from a decoded ready payload."""

    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Splash host ready field is invalid: {key}")
    return value


def _parse_endpoint(endpoint: str) -> tuple[str, int]:
    """Parse one local host and port endpoint."""

    host, separator, raw_port = endpoint.rpartition(":")
    if not separator:
        raise ValueError("Splash host endpoint is invalid.")
    return host, int(raw_port)


def _hidden_process_creation_flags() -> int:
    """Return Windows process flags for a hidden splash host console."""

    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _hidden_process_startup_info() -> subprocess.STARTUPINFO | None:
    """Return Windows startup info that suppresses console windows."""

    if sys.platform != "win32":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def append_splash_session_args(
    command: Sequence[str],
    session: LauncherSplashSession | None,
) -> list[str]:
    """Append splash handoff arguments when a launcher session exists."""

    if session is None:
        return list(command)
    return [*command, *session.app_arguments]
