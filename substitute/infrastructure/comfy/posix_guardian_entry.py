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

"""Run the POSIX guardian process that owns one managed ComfyUI process group."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import threading
from time import monotonic, sleep
from typing import Any

_TERM_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class _LaunchRequest:
    """Describe one validated guardian child launch request."""

    command: tuple[str, ...]
    cwd: Path
    env: dict[str, str]
    capture_output: bool


def main(argv: list[str] | None = None) -> int:
    """Launch and monitor one managed ComfyUI child under guardian ownership."""

    args = list(sys.argv[1:] if argv is None else argv)
    keepalive_fd, pipe_token = _parse_arguments(args)
    stop_event = threading.Event()
    _install_signal_handlers(stop_event)
    launch_request = _read_launch_request()
    try:
        child_process = subprocess.Popen(
            list(launch_request.command),
            cwd=str(launch_request.cwd),
            env=launch_request.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if launch_request.capture_output else None,
            stderr=subprocess.STDOUT if launch_request.capture_output else None,
            text=False,
            bufsize=0,
            preexec_fn=_run_child_in_new_session,
        )
    except Exception as error:
        _write_control_payload({"status": "error", "detail": str(error)})
        return 1
    process_group_id = _get_process_group_id(child_process.pid)
    _write_control_payload(
        {
            "status": "ready",
            "guardian_pid": os.getpid(),
            "child_pid": child_process.pid,
            "process_group_id": process_group_id,
            "pipe_token": pipe_token,
        }
    )
    pump_thread = _start_output_forwarder(child_process)
    control_thread = _start_control_monitor(stop_event)
    try:
        return _monitor_child(
            child_process=child_process,
            process_group_id=process_group_id,
            keepalive_fd=keepalive_fd,
            stop_event=stop_event,
        )
    finally:
        os.close(keepalive_fd)
        pump_thread.join(timeout=1.0)
        control_thread.join(timeout=1.0)


def _parse_arguments(args: list[str]) -> tuple[int, str]:
    """Parse the minimal guardian CLI required for keepalive monitoring."""

    if len(args) != 4 or args[0] != "--keepalive-fd" or args[2] != "--pipe-token":
        raise RuntimeError("guardian requires --keepalive-fd <fd> --pipe-token <token>")
    return int(args[1]), args[3]


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """Map TERM and INT to an orderly managed process-group teardown request."""

    def _request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)


def _read_launch_request() -> _LaunchRequest:
    """Read and validate one JSON launch request from guardian stdin."""

    line = sys.stdin.buffer.readline()
    if not line:
        raise RuntimeError("guardian launch request was missing")
    payload = json.loads(line.decode("utf-8"))
    command_payload = payload.get("command")
    if not isinstance(command_payload, list) or not all(
        isinstance(item, str) and item for item in command_payload
    ):
        raise RuntimeError(
            "guardian launch request must contain a non-empty command list"
        )
    environment_payload = payload.get("env")
    if not isinstance(environment_payload, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in environment_payload.items()
    ):
        raise RuntimeError(
            "guardian launch request must contain a string environment map"
        )
    cwd_payload = payload.get("cwd")
    if not isinstance(cwd_payload, str) or not cwd_payload.strip():
        raise RuntimeError("guardian launch request must contain a working directory")
    return _LaunchRequest(
        command=tuple(command_payload),
        cwd=Path(cwd_payload),
        env=dict(environment_payload),
        capture_output=bool(payload.get("capture_output", False)),
    )


def _write_control_payload(payload: dict[str, Any]) -> None:
    """Write one guardian control payload to stdout as a JSON line."""

    sys.stdout.buffer.write(
        (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    )
    sys.stdout.buffer.flush()


def _start_output_forwarder(child_process: subprocess.Popen[bytes]) -> threading.Thread:
    """Forward child stdout into guardian stderr so the parent can keep streaming logs."""

    def _forward_output() -> None:
        child_stdout = child_process.stdout
        if child_stdout is None:
            return
        try:
            while True:
                chunk = child_stdout.read(4096)
                if not chunk:
                    return
                sys.stderr.buffer.write(chunk)
                sys.stderr.buffer.flush()
        finally:
            child_stdout.close()

    thread = threading.Thread(target=_forward_output, daemon=True)
    thread.start()
    return thread


def _start_control_monitor(stop_event: threading.Event) -> threading.Thread:
    """Monitor guardian stdin for explicit stop commands from the live parent."""

    def _monitor() -> None:
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return
            try:
                payload = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "stop":
                stop_event.set()
                return

    thread = threading.Thread(target=_monitor, daemon=True)
    thread.start()
    return thread


def _monitor_child(
    *,
    child_process: subprocess.Popen[bytes],
    process_group_id: int,
    keepalive_fd: int,
    stop_event: threading.Event,
) -> int:
    """Monitor keepalive, child exit, and explicit stop signals until shutdown."""

    while True:
        if stop_event.is_set():
            _terminate_process_group(process_group_id)
            return 0
        if child_process.poll() is not None:
            return int(child_process.returncode or 0)
        if _keepalive_closed(keepalive_fd):
            _terminate_process_group(process_group_id)
            return 0
        sleep(0.1)


def _keepalive_closed(keepalive_fd: int) -> bool:
    """Return whether the parent keepalive pipe has reached EOF."""

    readable, _, _ = select.select([keepalive_fd], [], [], 0)
    if not readable:
        return False
    data = os.read(keepalive_fd, 1)
    return data == b""


def _terminate_process_group(process_group_id: int) -> None:
    """Terminate one child process group with TERM then KILL escalation."""

    if not _is_process_group_running(process_group_id):
        return
    _kill_process_group(process_group_id, signal.SIGTERM)
    deadline = monotonic() + _TERM_TIMEOUT_SECONDS
    while monotonic() < deadline:
        if not _is_process_group_running(process_group_id):
            return
        sleep(0.1)
    if _is_process_group_running(process_group_id):
        _kill_process_group(
            process_group_id, getattr(signal, "SIGKILL", signal.SIGTERM)
        )


def _is_process_group_running(process_group_id: int) -> bool:
    """Return whether the supplied process group still exists."""

    try:
        _kill_process_group(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _run_child_in_new_session() -> None:
    """Place the managed child into a dedicated POSIX session and process group."""

    setsid = getattr(os, "setsid", None)
    if setsid is None:
        raise RuntimeError("guardian requires os.setsid on a POSIX host")
    setsid()


def _get_process_group_id(pid: int) -> int:
    """Return the process-group id for one managed child pid."""

    getpgid = getattr(os, "getpgid", None)
    if getpgid is None:
        raise RuntimeError("guardian requires os.getpgid on a POSIX host")
    return int(getpgid(pid))


def _kill_process_group(process_group_id: int, signum: int) -> None:
    """Send one signal to the supplied POSIX process group."""

    killpg = getattr(os, "killpg", None)
    if killpg is None:
        raise RuntimeError("guardian requires os.killpg on a POSIX host")
    killpg(process_group_id, signum)


if __name__ == "__main__":
    raise SystemExit(main())
