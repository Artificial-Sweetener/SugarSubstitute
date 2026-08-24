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

"""Verify native-safe pytest worker timeout and evidence ownership."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from tools.ci.pytest_worker_timeout import PytestWorkerTimeoutGuard

_FAULT_NODEID = "tests/example/test_native_stall.py::test_native_call"


def test_worker_timeout_exits_native_gil_stall_with_attributable_evidence(
    tmp_path: Path,
) -> None:
    """A native call retaining the GIL should still be bounded and attributed."""

    child = textwrap.dedent(
        f"""
        import ctypes
        import sys
        from pathlib import Path

        from tools.ci.pytest_worker_timeout import PytestWorkerTimeoutGuard

        guard = PytestWorkerTimeoutGuard(
            timeout_seconds=0.1,
            evidence_directory=Path(sys.argv[1]),
            worker_id="fault-worker",
        )
        with guard.guard_test({_FAULT_NODEID!r}):
            if sys.platform == "win32":
                native = ctypes.PyDLL("kernel32")
                native.Sleep(30_000)
            else:
                native = ctypes.PyDLL(None)
                native.sleep(30)
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", child, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[4],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode != 0
    evidence_paths = tuple(tmp_path.glob("pytest-worker-fault-worker-*.txt"))
    assert len(evidence_paths) == 1
    evidence = evidence_paths[0].read_text(encoding="utf-8")
    assert "status=active" in evidence
    assert f"nodeid={_FAULT_NODEID}" in evidence
    assert "timeout_seconds=0.1" in evidence
    assert "Timeout" in evidence
    assert "test_native_stall" in evidence


def test_worker_timeout_removes_evidence_after_clean_session(tmp_path: Path) -> None:
    """Clean completion should leave no failure-like process artifact."""

    guard = PytestWorkerTimeoutGuard(
        timeout_seconds=1.0,
        evidence_directory=tmp_path,
        worker_id="clean-worker",
    )

    with guard.guard_test("tests/example/test_clean.py::test_complete"):
        pass
    guard.close_cleanly()

    assert tuple(tmp_path.iterdir()) == ()
