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

"""Verify retained native recovery handles cannot retarget a recycled PID."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.application_instance_recovery import (
    terminate_verified_process,
)
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_process_scope import ExactExecutableProcessScope
from sugarsubstitute_shared.process_identity import capture_process_identity


def test_native_recovery_keeps_the_verified_object_after_pid_replacement(
    tmp_path: Path,
) -> None:
    """Terminate and await the held object even after the PID maps elsewhere."""
    from launcher.sugarsubstitute_launcher.instance_process_control import (
        NativeInstanceProcess,
    )

    class Kernel:
        """Separate PID lookup from the retained process-object handle."""

        def __init__(self) -> None:
            """Start with one live candidate and no retained handles."""
            self.current = 7
            self.opened: list[int] = []
            self.terminated: list[int] = []
            self.closed: list[int] = []

        def open(self, pid: int) -> int | None:
            """Bind the PID once to its current object."""
            self.opened.append(pid)
            return self.current

        def creation_time(self, handle: int) -> float:
            """Return the identity of the bound object."""
            assert handle == 7
            return 1000.25

        def image_path(self, handle: int) -> Path:
            """Retain image identity while replacing the process reached by PID."""
            assert handle == 7
            self.current = 8
            return tmp_path / "owned.exe"

        def terminate(self, handle: int) -> None:
            """Target an object rather than resolving the recycled PID."""
            self.terminated.append(handle)

        def wait(self, handle: int, milliseconds: int) -> bool:
            """Require terminal evidence from the same process that was ended."""
            assert handle == 7
            assert milliseconds == 5000
            return handle in self.terminated

        def close(self, handle: int) -> None:
            """Release only the retained candidate object."""
            self.closed.append(handle)

    kernel = Kernel()
    process = NativeInstanceProcess(123, api=kernel)
    try:
        assert process.create_time() == 1000.25
        assert process.exe() == str(tmp_path / "owned.exe")
        process.terminate()
        process.wait(timeout=5)
    finally:
        process.close()
    process.close()
    with pytest.raises(RuntimeError, match="released"):
        process.terminate()
    assert kernel.current == 8
    assert kernel.opened == [123]
    assert kernel.terminated == [7]
    assert kernel.closed == [7]


@pytest.mark.platforms("windows")
@pytest.mark.parametrize(
    "candidate", ["exact", "different-incarnation", "different-image"]
)
def test_native_recovery_requires_matching_identity_and_image(
    tmp_path: Path, candidate: str
) -> None:
    """End only an exact hidden fixture and leave rejected candidates alive."""
    process, _log = spawn_supervised_process(
        [sys.executable, "-c", "from threading import Event; Event().wait(30)"],
        startup_log_path=tmp_path / "process.log",
    )
    try:
        identity = capture_process_identity(process.pid)
        image = Path(psutil.Process(process.pid).exe())
        if candidate == "different-incarnation":
            identity = replace(identity, created_at=identity.created_at - 1)
        if candidate == "different-image":
            image = tmp_path / "unrelated.exe"
        recovered = terminate_verified_process(
            identity, scope=ExactExecutableProcessScope((image,))
        )
        if candidate == "exact":
            assert recovered
            process.wait(timeout=5)
        else:
            assert not recovered
            assert process.poll() is None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
