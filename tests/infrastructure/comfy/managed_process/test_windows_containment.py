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

"""Tests for one managed ComfyUI process behavior owner."""

from __future__ import annotations

from __future__ import annotations
import os
from pathlib import Path
import subprocess
from typing import Any, cast
import pytest
from substitute.infrastructure.comfy import (
    managed_shutdown,
    windows_job_containment,
)
from substitute.infrastructure.comfy.managed_process_metadata import (
    ManagedProcessMetadata,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationStatus,
    kill_managed_comfy,
    kill_managed_comfy_pid,
)
from substitute.infrastructure.comfy.windows_job_containment import (
    WindowsJobContainmentHandle,
)


class _FakeProcess:
    """Provide the minimal Popen surface used by lifecycle tests."""

    def __init__(self, pid: int, returncode: int | None = None) -> None:
        self.pid = pid
        self._returncode = returncode

    def poll(self) -> int | None:
        """Return the configured process exit status."""

        return self._returncode


def test_kill_managed_comfy_reports_success_when_process_already_gone() -> None:
    """Termination should report success when no live process remains."""

    result = kill_managed_comfy(
        cast(subprocess.Popen[Any], _FakeProcess(123, returncode=0))
    )

    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert result.attempted is False


def test_kill_managed_comfy_pid_reports_windows_taskkill_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows termination should report taskkill timeouts explicitly."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _raise_taskkill_timeout(*args, **kwargs),
    )

    result = kill_managed_comfy_pid(123)

    assert result.attempted is True
    assert result.status is ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED
    assert result.termination_command_timed_out is True
    assert result.verification_timed_out is False


def test_kill_managed_comfy_pid_reports_windows_verification_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful Windows taskkill should still count as confirmed shutdown."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="terminated",
            stderr="",
        ),
    )
    monkeypatch.setattr(managed_shutdown, "is_process_running", lambda _pid: True)

    result = kill_managed_comfy_pid(124)

    assert result.attempted is True
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert result.termination_command_timed_out is False
    assert result.verification_timed_out is True
    assert "SUCCESS:" not in result.user_safe_detail


def test_kill_managed_comfy_pid_captures_windows_stdout_only_in_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw taskkill stdout should remain diagnostic-only."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="SUCCESS: Sent termination signal.",
            stderr="",
        ),
    )
    monkeypatch.setattr(managed_shutdown, "is_process_running", lambda _pid: True)

    result = kill_managed_comfy_pid(126)

    assert "SUCCESS:" not in result.user_safe_detail
    assert "SUCCESS:" in result.diagnostic_detail
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED


def test_kill_managed_comfy_pid_reports_windows_invocation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows termination should surface invocation failures as command failures."""

    monkeypatch.setattr(os, "name", "nt", raising=False)

    def _raise_os_error(*args: object, **kwargs: object) -> object:
        raise OSError("taskkill unavailable")

    monkeypatch.setattr(subprocess, "run", _raise_os_error)

    result = kill_managed_comfy_pid(127)

    assert result.status is ManagedProcessTerminationStatus.TERMINATION_COMMAND_FAILED
    assert "taskkill unavailable" in result.diagnostic_detail


def test_kill_managed_comfy_pid_reports_windows_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows termination should report success when exit verification passes."""

    monkeypatch.setattr(os, "name", "nt", raising=False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="terminated",
            stderr="",
        ),
    )
    monkeypatch.setattr(managed_shutdown, "is_process_running", lambda _pid: False)

    result = kill_managed_comfy_pid(125)

    assert result.attempted is True
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert result.termination_command_timed_out is False
    assert result.verification_timed_out is False
    assert result.user_safe_detail == "Shutdown finished cleanly."
    assert "terminated" in result.diagnostic_detail


def test_windows_job_owned_shutdown_closes_only_containment_handles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows contained shutdown should close the job handle before exit verification."""

    close_calls: list[str] = []
    verification_calls: list[int] = []
    handle = WindowsJobContainmentHandle(
        job_handle=11,
        process_handle=22,
        job_name="job-1",
    )
    metadata = ManagedProcessMetadata(
        pid=321,
        host="127.0.0.1",
        port=8188,
        workspace_path=tmp_path / "comfyui",
        containment_mode="windows_job_object",
        owner_pid=654,
        job_name="job-1",
    )
    monkeypatch.setattr(
        windows_job_containment,
        "close_job_containment_handle",
        lambda raw_handle: close_calls.append(raw_handle.job_name),
    )
    monkeypatch.setattr(
        managed_shutdown,
        "_verify_process_exit",
        lambda pid, **kwargs: _record_verification(verification_calls, pid),
    )

    result = managed_shutdown.kill_managed_comfy_metadata(
        metadata,
        containment_handle=handle,
    )

    assert close_calls == ["job-1"]
    assert verification_calls == [321]
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED


def _raise_taskkill_timeout(*args: object, **kwargs: object) -> object:
    """Raise one deterministic taskkill timeout for unit tests."""

    timeout = kwargs.get("timeout")
    command = cast(list[str], args[0])
    raise subprocess.TimeoutExpired(
        cmd=command,
        timeout=timeout if isinstance(timeout, int | float) else 5.0,
    )


def _record_verification(
    calls: list[int],
    pid: int,
) -> tuple[bool, bool]:
    """Record one verification request and report a confirmed exit."""

    calls.append(pid)
    return True, False
