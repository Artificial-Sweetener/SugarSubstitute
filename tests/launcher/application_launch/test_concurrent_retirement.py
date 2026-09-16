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

"""Require native terminal evidence to settle concurrent instance retirement."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import sys
from threading import Barrier, BrokenBarrierError

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher import application_instance_recovery
from launcher.sugarsubstitute_launcher.instance_process_control import InstanceProcess
from sugarsubstitute_shared.application_process_scope import ExactExecutableProcessScope
from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared import windows_process_security


@pytest.mark.parametrize(
    "operation", ["identity", "image", "arguments", "directory", "termination", "wait"]
)
@pytest.mark.parametrize("exited", [False, True])
def test_concurrent_retirement_uses_retained_exit_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    exited: bool,
) -> None:
    """Accept an independently completed exit without hiding a live access failure."""
    image = tmp_path / "SugarSubstitute.exe"
    closed: list[bool] = []

    class RetiringProcess:
        """Expose native operation failure while another actor may finish retirement."""

        def __init__(self) -> None:
            """Keep the operation race separate from authoritative exit evidence."""
            self.failed = False
            self.terminated = False

        def _observe(self, name: str) -> None:
            """Fail exactly where concurrent native retirement invalidates metadata."""
            if name == operation and not self.failed:
                self.failed = True
                raise PermissionError("Native process operation lost an exit race")

        def create_time(self) -> float:
            """Expose the retained process incarnation."""
            self._observe("identity")
            return 123.0

        def exe(self) -> str:
            """Read image metadata subject to native teardown."""
            self._observe("image")
            return str(image)

        def cmdline(self) -> Sequence[str]:
            """Read invocation metadata subject to native teardown."""
            self._observe("arguments")
            return (str(image),)

        def cwd(self) -> str:
            """Read directory metadata subject to native teardown."""
            self._observe("directory")
            return str(tmp_path)

        def terminate(self) -> None:
            """Request termination without treating request completion as process exit."""
            self._observe("termination")
            self.terminated = True

        def kill(self) -> None:
            """Retain the same identity for forced termination."""
            self.terminate()

        def wait(self, *, timeout: float) -> None:
            """Publish actual terminal evidence independently from operation errors."""
            assert timeout > 0
            self._observe("wait")
            if not exited:
                raise psutil.TimeoutExpired(timeout, pid=4401)

    process = RetiringProcess()

    @contextmanager
    def open_process(pid: int) -> Iterator[InstanceProcess]:
        """Keep exit evidence valid until the recovery owner finishes its decision."""
        assert pid == 4401
        try:
            yield process
        finally:
            closed.append(True)

    monkeypatch.setattr(
        application_instance_recovery, "open_instance_process", open_process
    )
    monkeypatch.setattr(windows_process_security, "process_session_id", lambda _pid: 1)
    assert (
        application_instance_recovery.terminate_verified_process(
            ProcessIdentity(4401, 123.0), scope=ExactExecutableProcessScope((image,))
        )
        is exited
    )
    assert closed == [True]
    if operation in {"identity", "image", "arguments", "directory"}:
        assert not process.terminated


@pytest.mark.platforms("windows")
def test_concurrent_native_retirement_converges_on_one_process_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain eight real handles and retire the same hidden native process together."""
    from launcher.sugarsubstitute_launcher.instance_process_control import (
        NativeInstanceProcess,
    )
    from launcher.sugarsubstitute_launcher.process_execution import (
        spawn_supervised_process,
    )
    from sugarsubstitute_shared.process_identity import capture_process_identity
    from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi

    child, _log = spawn_supervised_process(
        [sys.executable, "-c", "from threading import Event; Event().wait(30)"],
        startup_log_path=tmp_path / "native-owner.log",
    )
    barrier = Barrier(8)

    class ConcurrentControl(NativeProcessHandleApi):
        """Synchronize contenders after each has pinned the actual native object."""

        def open(self, pid: int) -> int | None:
            """Retain native handles before allowing concurrent metadata and control."""
            handle = super().open(pid)
            assert handle is not None
            try:
                barrier.wait(timeout=10)
            except BrokenBarrierError:
                self.close(handle)
                raise
            return handle

    @contextmanager
    def open_process(pid: int) -> Iterator[InstanceProcess]:
        """Replace scheduling only; keep real native identity, control and wait calls."""
        assert pid == child.pid
        process = NativeInstanceProcess(
            pid, api=ConcurrentControl(allow_termination=True)
        )
        try:
            yield process
        finally:
            process.close()

    try:
        identity = capture_process_identity(child.pid)
        scope = ExactExecutableProcessScope((Path(psutil.Process(child.pid).exe()),))
        monkeypatch.setattr(
            application_instance_recovery, "open_instance_process", open_process
        )

        def retire(_index: int) -> bool:
            """Request ordinary verified retirement through the production owner."""
            return application_instance_recovery.terminate_verified_process(
                identity, scope=scope
            )

        with ThreadPoolExecutor(max_workers=8) as contenders:
            results = list(contenders.map(retire, range(8)))
        assert results == [True] * 8
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
