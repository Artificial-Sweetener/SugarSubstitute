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

"""Qualify exact Windows process waits with hidden native child processes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
from threading import Event

import pytest

from sugarsubstitute_shared.process_identity import capture_process_identity
from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi
from sugarsubstitute_shared.windows_process_wait import (
    wait_for_windows_process_exit,
)


@pytest.mark.platforms("windows")
def test_wait_finishes_when_the_verified_native_process_exits() -> None:
    """Observe real kernel completion after identity verification through one handle."""
    verified = Event()

    class ObservedApi(NativeProcessHandleApi):
        """Expose the verified boundary without replacing native operations."""

        def creation_time(self, handle: int) -> float:
            """Signal that the native process object has been identified."""
            created = super().creation_time(handle)
            verified.set()
            return created

    with subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as process:
        try:
            identity = capture_process_identity(process.pid)
            with ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    wait_for_windows_process_exit,
                    identity,
                    timeout_seconds=10.0,
                    api=ObservedApi(),
                )
                assert verified.wait(timeout=5.0)
                assert process.stdin is not None
                process.stdin.write(b"x")
                process.stdin.flush()
                result.result(timeout=15.0)
            assert process.wait(timeout=5.0) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5.0)
