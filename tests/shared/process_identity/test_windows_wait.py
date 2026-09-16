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

"""Verify the Windows wait owner keeps one process object across PID changes."""

from __future__ import annotations

import pytest

from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
)
from sugarsubstitute_shared.windows_process_wait import wait_for_windows_process_exit


@pytest.mark.parametrize(
    "outcome",
    [
        "exited",
        "reused-after-query",
        "missing",
        "mismatch",
        "timeout",
        "query-error",
        "wait-error",
    ],
)
def test_windows_wait_retains_identity_through_terminal_state(outcome: str) -> None:
    """Use one retained object and release it after every terminal path."""
    identity = ProcessIdentity(pid=123, created_at=1000.25)

    class Kernel:
        """Model kernel object handles independently of recyclable process IDs."""

        def __init__(self) -> None:
            """Begin with one original object reachable by the fixture PID."""
            self.pid_object = 7
            self.retained: set[int] = set()
            self.waited: list[int] = []
            self.open_count = 0

        def open(self, pid: int) -> int | None:
            """Retain the currently named object, never a PID-shaped handle."""
            assert pid == identity.pid
            self.open_count += 1
            if outcome == "missing":
                return None
            self.retained.add(self.pid_object)
            return self.pid_object

        def creation_time(self, handle: int) -> float:
            """Change the PID mapping after verification to expose reopen races."""
            assert handle in self.retained
            if outcome == "query-error":
                raise OSError("creation query failed")
            if outcome == "reused-after-query":
                self.pid_object = 8
            return identity.created_at + (1 if outcome == "mismatch" else 0)

        def wait(self, handle: int, milliseconds: int) -> bool:
            """The original object has exited even if another object owns its PID."""
            assert milliseconds == 250
            assert handle in self.retained
            self.waited.append(handle)
            if outcome == "wait-error":
                raise OSError("wait failed")
            return outcome != "timeout" and handle == 7

        def close(self, handle: int) -> None:
            """Release the held object independently of the current PID mapping."""
            self.retained.remove(handle)

    kernel = Kernel()
    if outcome in {"timeout", "query-error", "wait-error"}:
        with pytest.raises(ProcessIdentityError):
            wait_for_windows_process_exit(identity, timeout_seconds=0.25, api=kernel)
    else:
        wait_for_windows_process_exit(identity, timeout_seconds=0.25, api=kernel)
    assert kernel.open_count == 1
    assert not kernel.retained
    assert kernel.waited == (
        [] if outcome in {"missing", "mismatch", "query-error"} else [7]
    )
