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

"""Verify admission and cleanup against a controlled native job boundary."""

from __future__ import annotations

from ctypes import wintypes
from pathlib import Path
from typing import cast

import pytest

import sugarsubstitute_shared.windows_independent_process as admission
from sugarsubstitute_shared.windows_process_job_api import (
    APPLICATION_PROCESS_FAMILY_ENV,
    ProcessInformation,
)

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize(
    "outcome",
    [
        "independent",
        "host_contained",
        "owned_breakaway",
        "owned_contained",
        "open_failure",
        "query_failure",
        "resume_failure",
    ],
)
def test_successful_breakaway_children_can_execute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: str
) -> None:
    """Accept only handoffs proven to escape their immediate process family."""
    resumed: list[object] = []
    terminated: list[int] = []
    waited: list[int] = []
    closed: list[object] = []

    class QueryMembership:
        """Model the job membership result returned for the created child."""

        argtypes: list[object] = []
        restype: object = None

        def __call__(self, handle: object, job: object, result: object) -> bool:
            """Populate the Win32 output parameter at the OS boundary."""
            assert handle == 101
            cast(wintypes.BOOL, getattr(result, "_obj")).value = (
                outcome == "owned_contained"
                if job == 88
                else outcome in {"host_contained", "owned_breakaway"}
            )
            return outcome != "query_failure"

    class ResumeOperation:
        """Record whether the suspended child was allowed to execute."""

        argtypes: list[object] = []
        restype: object = None

        def __call__(self, thread: object) -> int:
            """Release the initial suspension only when admission succeeds."""
            resumed.append(thread)
            return 0xFFFFFFFF if outcome == "resume_failure" else 1

    class Kernel:
        """Expose only the native operations used by this admission contract."""

        IsProcessInJob = QueryMembership()
        ResumeThread = ResumeOperation()

        def OpenJobObjectW(self, access: int, inherit: bool, name: str) -> int:
            """Open the application family only when its identity is supplied."""
            assert access == 0x0004
            assert inherit is False
            assert name == "fixture-family"
            return 0 if outcome == "open_failure" else 88

        def CloseHandle(self, handle: object) -> bool:
            """Record disposal of the borrowed process and thread references."""
            closed.append(handle)
            return True

    class ProcessLifetime:
        """Observe the native exit barrier for a rejected child."""

        def __init__(self, *, allow_termination: bool) -> None:
            """Require explicit termination authority for this created process."""
            assert allow_termination

        def terminate(self, handle: int) -> None:
            """Retire the child while it is still suspended."""
            terminated.append(handle)

        def wait(self, handle: int, milliseconds: int) -> bool:
            """Report verified native exit within the cleanup deadline."""
            waited.append(handle)
            return True

    process = ProcessInformation(process=101, thread=102, pid=103, tid=104)

    def create(*args: object, **kwargs: object) -> ProcessInformation:
        """Require suspension at creation before returning a controlled child."""
        assert cast(int, kwargs["creation_flags"]) & 0x4
        assert APPLICATION_PROCESS_FAMILY_ENV not in cast(
            dict[str, str], kwargs["environment"]
        )
        return process

    monkeypatch.setattr(admission, "create_windows_process", create)
    monkeypatch.setattr(admission, "load_kernel", Kernel)
    monkeypatch.setattr(admission, "NativeProcessHandleApi", ProcessLifetime)
    environment = (
        {APPLICATION_PROCESS_FAMILY_ENV: "fixture-family"}
        if outcome.startswith("owned_") or outcome in {"open_failure", "query_failure"}
        else {}
    )
    if outcome in {
        "owned_contained",
        "open_failure",
        "query_failure",
        "resume_failure",
    }:
        with pytest.raises((OSError, PermissionError)):
            admission.start_independent_windows_process(
                ["fixture.exe"],
                environment=environment,
                cwd=tmp_path,
                output_fd=1,
            )
        assert resumed == ([102] if outcome == "resume_failure" else [])
        if outcome == "open_failure":
            assert not terminated and not waited
        else:
            assert terminated == waited == [101]
    else:
        assert (
            admission.start_independent_windows_process(
                ["fixture.exe"],
                environment=environment,
                cwd=tmp_path,
                output_fd=1,
            )
            == 103
        )
        assert resumed == [102]
        assert not terminated and not waited
    expected_closed = set()
    if outcome != "open_failure":
        expected_closed.update({101, 102})
    if environment and outcome != "open_failure":
        expected_closed.add(88)
    assert set(closed) == expected_closed
