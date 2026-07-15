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

"""Tests for Windows Job Object managed ComfyUI containment."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path

import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentError,
    build_launch_request,
)
from substitute.infrastructure.comfy import windows_job_containment

pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Windows Job Object containment applies only on Windows.",
)


def test_launch_in_job_assigns_before_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows job launch should create the process before assignment and resume after assignment."""

    call_order: list[str] = []
    monkeypatch.setattr(
        windows_job_containment,
        "_create_job_object",
        lambda job_name: _record_job_creation(call_order, job_name),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_configure_kill_on_job_close",
        lambda job_handle: call_order.append(f"configure:{job_handle}"),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_create_stdout_pipe",
        lambda: _record_stdout_pipe(call_order),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_create_suspended_process",
        lambda **kwargs: _record_created_process(call_order),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_assign_process_to_job",
        lambda **kwargs: call_order.append("assign"),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_resume_primary_thread",
        lambda thread_handle: call_order.append(f"resume:{thread_handle}"),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_close_handle",
        lambda handle: call_order.append(f"close:{handle}"),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_timestamp_now",
        lambda: "2026-03-24T00:00:00+00:00",
    )

    result = windows_job_containment.launch_in_job(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=Path("E:/managed/comfy"),
        request=build_launch_request(
            command=("python.exe", "main.py"),
            cwd=Path("E:/managed/comfy"),
            env={"PATH": "E:/managed/comfy/.venv/Scripts"},
            capture_output=True,
        ),
    )

    assert call_order.index("create_process") < call_order.index("assign")
    assert call_order.index("assign") < call_order.index("resume:333")
    assert result.metadata.containment_mode == "windows_job_object"
    assert result.metadata.owner_pid == os.getpid()
    assert result.process.pid == 123


def test_close_job_containment_handle_closes_job_and_process_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing the containment handle should close the job and process handles exactly once."""

    closed_handles: list[int] = []
    handle = windows_job_containment.WindowsJobContainmentHandle(
        job_handle=11,
        process_handle=22,
        job_name="job-1",
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_close_handle",
        lambda raw_handle: closed_handles.append(raw_handle),
    )

    windows_job_containment.close_job_containment_handle(handle)
    windows_job_containment.close_job_containment_handle(handle)

    assert closed_handles == [11, 22]


def test_launch_in_job_wraps_assignment_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Job assignment failures should surface a typed containment error."""

    monkeypatch.setattr(
        windows_job_containment, "_create_job_object", lambda _job_name: 99
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_configure_kill_on_job_close",
        lambda _job_handle: None,
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_create_suspended_process",
        lambda **kwargs: windows_job_containment._CreatedProcess(
            pid=123,
            process_handle=222,
            thread_handle=333,
        ),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_assign_process_to_job",
        lambda **kwargs: (_ for _ in ()).throw(OSError("assignment failed")),
    )
    monkeypatch.setattr(
        windows_job_containment,
        "_close_handle",
        lambda _handle: None,
    )

    with pytest.raises(ManagedContainmentError, match="assignment failed"):
        windows_job_containment.launch_in_job(
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace=Path("E:/managed/comfy"),
            request=build_launch_request(
                command=("python.exe", "main.py"),
                cwd=Path("E:/managed/comfy"),
                env={"PATH": "E:/managed/comfy/.venv/Scripts"},
                capture_output=False,
            ),
        )


def _record_job_creation(call_order: list[str], _job_name: str) -> int:
    """Record Job Object creation for launch-order assertions."""

    call_order.append("create_job")
    return 777


def _record_stdout_pipe(call_order: list[str]) -> tuple[BytesIO, int]:
    """Record stdout pipe creation for launch-order assertions."""

    call_order.append("create_pipe")
    return BytesIO(), 444


def _record_created_process(
    call_order: list[str],
) -> windows_job_containment._CreatedProcess:
    """Record suspended process creation for launch-order assertions."""

    call_order.append("create_process")
    return windows_job_containment._CreatedProcess(
        pid=123,
        process_handle=222,
        thread_handle=333,
    )
