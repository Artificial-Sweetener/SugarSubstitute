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
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, IO, Any

from launcher.sugarsubstitute_launcher.runtime_policy import runtime_environment
from sugarsubstitute_shared.supervised_text_process import (
    SupervisedTextProcess,
    TextProcessStarter,
    start_supervised_text_process,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
)
from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient
from sugarsubstitute_shared.launch_splash.session import (
    LEGACY_SPLASH_PROTOCOL_VERSION,
    SplashSessionSpec,
    splash_session_args,
    splash_cancel_signal_path,
)
from sugarsubstitute_shared.launch_splash.session import validate_splash_session_spec
from sugarsubstitute_shared.launch_splash.timing import (
    SPLASH_HOST_EXIT_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from launcher.sugarsubstitute_launcher.startup_splash_session import (
        StartupSplashSession,
    )
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


_LOGGER = logging.getLogger(__name__)
_HOST_MODULE = "substitute.app.bootstrap.shared_splash_host"
_READY_TIMEOUT_SECONDS = 8.0
_HOST_PROCESS_REQUESTED_MONOTONIC_NS_ENV = (
    "SUGAR_SUBSTITUTE_SPLASH_HOST_PROCESS_REQUESTED_MONOTONIC_NS"
)


@dataclass(frozen=True, slots=True)
class LauncherSplashSession:
    """Own a launcher-created splash process through application handoff."""

    client: SocketSplashSessionClient
    app_arguments: tuple[str, ...]
    host_pid: int
    process: SupervisedTextProcess

    def present(self) -> str | None:
        """Bring the startup surface forward for a secondary invocation."""

        return "startup-splash" if self.client.activate() else None

    def cancellation_requested(self) -> bool:
        """Observe only the explicit cancel signal for this authenticated session."""
        return splash_cancel_signal_path(self.client.spec).is_file()

    def ensure_closed(self) -> None:
        """Confirm splash exit or terminate the launcher-owned helper."""

        try:
            self.process.wait(timeout=SPLASH_HOST_EXIT_TIMEOUT_SECONDS)
            return
        except subprocess.TimeoutExpired:
            _LOGGER.warning(
                "Splash host remained alive after application readiness; terminating it."
            )
        _terminate_failed_splash_host(self.process)

    def close(self) -> None:
        """Request splash closure and enforce launcher-owned process cleanup."""

        if self.process.poll() is not None:
            return
        if not self.client.close():
            _LOGGER.warning("Splash host did not acknowledge closure; terminating it.")
        self.ensure_closed()


def start_launcher_splash_session(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    process_starter: TextProcessStarter = start_supervised_text_process,
) -> LauncherSplashSession | None:
    """Start the shared splash host process for production app handoff."""

    process: SupervisedTextProcess | None = None
    try:
        process = _start_splash_host_process(
            layout=layout,
            locale_override=locale_override,
            process_starter=process_starter,
        )
        _start_background_pipe_reader(
            stream=process.stderr,
            label="stderr",
            ignore_ready_message=False,
        )
        spec = _read_ready_spec(process=process, timeout_seconds=_READY_TIMEOUT_SECONDS)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        _LOGGER.warning("Shared launcher splash session unavailable: %r", error)
        if process is not None:
            _terminate_failed_splash_host(process)
            if process.poll() is not None:
                process.stdout.close()
        return None

    _start_background_pipe_reader(
        stream=process.stdout,
        label="stdout",
        ignore_ready_message=True,
    )
    return LauncherSplashSession(
        client=SocketSplashSessionClient(spec),
        app_arguments=tuple(splash_session_args(spec)),
        host_pid=spec.host_pid,
        process=process,
    )


def _terminate_failed_splash_host(process: SupervisedTextProcess) -> None:
    """Stop a visible splash host whose session could not be handed off."""

    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            _LOGGER.warning("Failed splash host did not exit after forced termination.")
    except OSError as error:
        _LOGGER.warning("Failed to terminate unusable splash host: %r", error)


def _start_splash_host_process(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    process_starter: TextProcessStarter,
) -> SupervisedTextProcess:
    """Launch the app-payload splash host without importing app code."""

    command = [
        subprocess_path(layout.runtime_python),
        "-m",
        _HOST_MODULE,
    ]
    if locale_override is not None:
        command.append(f"--locale={locale_override}")
    return process_starter(
        command,
        cwd=layout.root,
        environment=_splash_host_environment(layout),
    )


def _splash_host_environment(layout: InstallLayout) -> dict[str, str]:
    """Build a runtime environment without application handoff authority."""

    environment = runtime_environment(layout=layout)
    environment.setdefault(
        "SUGAR_SUBSTITUTE_SPLASH_REQUESTED_MONOTONIC_NS",
        str(time.monotonic_ns()),
    )
    environment[_HOST_PROCESS_REQUESTED_MONOTONIC_NS_ENV] = str(time.monotonic_ns())
    return environment


def _read_ready_spec(
    *,
    process: SupervisedTextProcess,
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
        protocol_version=_optional_int(
            payload,
            "protocol_version",
            default=LEGACY_SPLASH_PROTOCOL_VERSION,
        ),
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
        """Own this pipe until its process family closes every writer."""
        with stream:
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


def _optional_int(payload: dict[Any, Any], key: str, *, default: int) -> int:
    """Read one optional integer while preserving legacy ready messages."""

    value = payload.get(key, default)
    if not isinstance(value, int):
        raise ValueError(f"Splash host ready field is invalid: {key}")
    return value


def _parse_endpoint(endpoint: str) -> tuple[str, int]:
    """Parse one local host and port endpoint."""

    host, separator, raw_port = endpoint.rpartition(":")
    if not separator:
        raise ValueError("Splash host endpoint is invalid.")
    return host, int(raw_port)


def append_splash_session_args(
    command: Sequence[str],
    session: StartupSplashSession | None,
) -> list[str]:
    """Append splash handoff arguments when a launcher session exists."""

    if session is None:
        return list(command)
    return [*command, *session.app_arguments]
