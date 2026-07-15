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

"""Own managed ComfyUI lifetime on POSIX hosts through a guardian process."""

from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
from typing import IO, Any
from uuid import uuid4

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentError,
    ManagedContainmentLaunchRequest,
    ManagedContainmentLaunchResult,
    ManagedContainmentRuntimeStatus,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ContainmentMode,
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_process_probe import is_process_running
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.comfy.posix_guardian_containment")
_GUARDIAN_READY_TIMEOUT_SECONDS = 10.0


class PosixGuardianManagedProcess:
    """Expose one guardian-owned managed child through the lifecycle protocol."""

    def __init__(
        self,
        *,
        pid: int,
        guardian_process: subprocess.Popen[bytes],
        stdout_stream: IO[bytes] | None,
    ) -> None:
        """Store the guardian process and managed child identifier."""

        self.pid = pid
        self.stdout = stdout_stream
        self._guardian_process = guardian_process

    def poll(self) -> int | None:
        """Return the child exit code when the managed process is no longer alive."""

        if is_process_running(self.pid):
            return None
        guardian_returncode = self._guardian_process.poll()
        return 0 if guardian_returncode is None else guardian_returncode


class PosixGuardianContainmentHandle:
    """Retain guardian control pipes and keepalive ownership for cleanup."""

    def __init__(
        self,
        *,
        guardian_process: subprocess.Popen[bytes],
        keepalive_write_fd: int,
        guardian_pipe_token: str,
        process_group_id: int,
    ) -> None:
        """Store the live guardian process and explicit keepalive resources."""

        self.guardian_process = guardian_process
        self.keepalive_write_fd = keepalive_write_fd
        self.guardian_pipe_token = guardian_pipe_token
        self.process_group_id = process_group_id
        self._closed = False

    def close(self) -> None:
        """Release guardian control pipes exactly once."""

        if self._closed:
            return
        self._closed = True
        try:
            os.close(self.keepalive_write_fd)
        except OSError:
            pass
        if self.guardian_process.stdin is not None:
            self.guardian_process.stdin.close()
        if self.guardian_process.stdout is not None:
            self.guardian_process.stdout.close()


def launch_with_guardian(
    *,
    endpoint: ComfyEndpoint,
    workspace: Path,
    request: ManagedContainmentLaunchRequest,
    containment_mode: ContainmentMode = "posix_guardian",
) -> ManagedContainmentLaunchResult:
    """Launch one managed ComfyUI child through the POSIX guardian process."""

    if containment_mode != "posix_guardian":
        raise ManagedContainmentError(
            f"POSIX guardian cannot use containment mode: {containment_mode}"
        )

    keepalive_read_fd, keepalive_write_fd = os.pipe()
    guardian_process: subprocess.Popen[bytes] | None = None
    guardian_pipe_token = uuid4().hex[:12]
    try:
        os.set_inheritable(keepalive_read_fd, True)
        guardian_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "substitute.infrastructure.comfy.posix_guardian_entry",
                "--keepalive-fd",
                str(keepalive_read_fd),
                "--pipe-token",
                guardian_pipe_token,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            pass_fds=(keepalive_read_fd,),
        )
        os.close(keepalive_read_fd)
        payload = {
            "command": list(request.command),
            "cwd": str(request.cwd),
            "env": dict(request.env),
            "capture_output": request.capture_output,
        }
        assert guardian_process.stdin is not None
        guardian_process.stdin.write(
            (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        )
        guardian_process.stdin.flush()
        ready_payload = _read_guardian_payload(guardian_process)
        managed_pid = int(ready_payload["child_pid"])
        process_group_id = int(ready_payload["process_group_id"])
        metadata = ManagedProcessMetadata(
            pid=managed_pid,
            host=endpoint.host,
            port=endpoint.port,
            workspace_path=workspace,
            parent_pid=os.getpid(),
            last_launched_at=_timestamp_now(),
            containment_mode=containment_mode,
            owner_pid=guardian_process.pid,
            process_group_id=process_group_id,
            guardian_pipe_token=guardian_pipe_token,
        )
        log_info(
            _LOGGER,
            "POSIX guardian reported child pid and pgid",
            containment_mode=containment_mode,
            launch_phase="guardian_ready",
            owner_pid=metadata.owner_pid,
            managed_pid=metadata.pid,
            process_group_id=metadata.process_group_id,
        )
        stdout_stream = guardian_process.stderr
        process = PosixGuardianManagedProcess(
            pid=managed_pid,
            guardian_process=guardian_process,
            stdout_stream=stdout_stream,
        )
        containment_handle = PosixGuardianContainmentHandle(
            guardian_process=guardian_process,
            keepalive_write_fd=keepalive_write_fd,
            guardian_pipe_token=guardian_pipe_token,
            process_group_id=process_group_id,
        )
        return ManagedContainmentLaunchResult(
            process=process,
            metadata=metadata,
            stdout_stream=stdout_stream,
            containment_handle=containment_handle,
        )
    except Exception as error:
        try:
            os.close(keepalive_read_fd)
        except OSError:
            pass
        try:
            os.close(keepalive_write_fd)
        except OSError:
            pass
        if guardian_process is not None:
            guardian_process.kill()
        raise ManagedContainmentError(
            f"POSIX guardian containment failed: {error}"
        ) from error


def request_guardian_stop(handle: PosixGuardianContainmentHandle) -> None:
    """Request guardian-owned shutdown through the live control pipe when possible."""

    if handle.guardian_process.poll() is not None:
        return
    try:
        if handle.guardian_process.stdin is not None:
            handle.guardian_process.stdin.write(b'{"type":"stop"}\n')
            handle.guardian_process.stdin.flush()
            return
    except OSError:
        pass
    request_guardian_stop_by_pid(handle.guardian_process.pid)


def request_guardian_stop_by_pid(owner_pid: int | None) -> None:
    """Request guardian-owned shutdown through the guardian pid."""

    if owner_pid is None or owner_pid <= 0:
        return
    try:
        os.kill(owner_pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def terminate_process_group(
    process_group_id: int | None, *, timeout_seconds: float
) -> None:
    """Terminate one POSIX managed process group with TERM then KILL."""

    if process_group_id is None or process_group_id <= 0:
        return
    if not is_process_group_running(process_group_id):
        return
    _kill_process_group(process_group_id, signal.SIGTERM)
    from time import monotonic, sleep

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if not is_process_group_running(process_group_id):
            return
        sleep(0.1)
    if is_process_group_running(process_group_id):
        _kill_process_group(
            process_group_id,
            getattr(signal, "SIGKILL", signal.SIGTERM),
        )


def describe_posix_guardian_runtime(
    metadata: ManagedProcessMetadata,
) -> ManagedContainmentRuntimeStatus:
    """Return persisted runtime facts for one guardian-owned POSIX launch."""

    return ManagedContainmentRuntimeStatus(
        managed_process_running=is_process_running(metadata.pid),
        owner_process_running=is_process_running(metadata.owner_pid),
        process_group_running=is_process_group_running(metadata.process_group_id),
    )


def is_process_group_running(process_group_id: int | None) -> bool:
    """Return whether the supplied process group still exists."""

    if process_group_id is None or process_group_id <= 0:
        return False
    try:
        _kill_process_group(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _kill_process_group(process_group_id: int, signum: int) -> None:
    """Send one signal to the supplied POSIX process group."""

    killpg = getattr(os, "killpg", None)
    if killpg is None:
        raise RuntimeError("POSIX guardian containment requires os.killpg.")
    killpg(process_group_id, signum)


def _read_guardian_payload(guardian_process: subprocess.Popen[bytes]) -> dict[str, Any]:
    """Read the guardian ready payload or fail with a typed containment error."""

    stdout_stream = guardian_process.stdout
    if stdout_stream is None:
        raise ManagedContainmentError("POSIX guardian did not expose a control pipe.")
    selector = selectors.DefaultSelector()
    try:
        selector.register(stdout_stream, selectors.EVENT_READ)
        ready_events = selector.select(_GUARDIAN_READY_TIMEOUT_SECONDS)
        if not ready_events:
            raise ManagedContainmentError(
                "POSIX guardian did not report readiness before the timeout."
            )
        line = stdout_stream.readline()
    finally:
        selector.close()
    if not line:
        stderr_text = _read_guardian_stderr(guardian_process)
        raise ManagedContainmentError(
            "POSIX guardian exited before reporting readiness."
            + (f" stderr={stderr_text!r}" if stderr_text else "")
        )
    payload = json.loads(line.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ManagedContainmentError(
            f"POSIX guardian returned a non-object payload: {payload!r}"
        )
    if payload.get("status") == "error":
        raise ManagedContainmentError(
            str(payload.get("detail") or "POSIX guardian failed.")
        )
    if payload.get("status") != "ready":
        raise ManagedContainmentError(
            f"POSIX guardian returned an unexpected payload: {payload!r}"
        )
    return payload


def _read_guardian_stderr(guardian_process: subprocess.Popen[bytes]) -> str:
    """Return one sanitized guardian stderr snapshot for launch diagnostics."""

    stderr_stream = guardian_process.stderr
    if stderr_stream is None:
        return ""
    try:
        stderr_payload: bytes = stderr_stream.read()
        return stderr_payload.decode("utf-8", "replace").strip()
    except OSError:
        return ""


def _timestamp_now() -> str:
    """Return one UTC ISO timestamp for managed launch metadata."""

    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


__all__ = [
    "PosixGuardianContainmentHandle",
    "PosixGuardianManagedProcess",
    "describe_posix_guardian_runtime",
    "is_process_group_running",
    "launch_with_guardian",
    "request_guardian_stop",
    "request_guardian_stop_by_pid",
    "terminate_process_group",
]
