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

"""Bound copied recovery images without deleting active or unknown installation state."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from launcher.sugarsubstitute_launcher.baseline_recovery_bootstrap import (
    run_baseline_recovery_bootstrap,
)
from launcher.sugarsubstitute_launcher.baseline_recovery_request import (
    BaselineRecoveryRequest,
)
from sugarsubstitute_shared.process_identity import capture_process_identity
from .native_file_sharing import exclusive_read

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("state", ["inactive", "publisher-active", "sharing-locked"])
def test_canonical_startup_retires_only_inactive_owned_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    """Real process incarnations and native sharing keep pending handoffs usable."""
    root = (tmp_path / "installation").resolve()
    root.mkdir()
    canonical = root / "SugarSubstitute.exe"
    canonical.write_bytes(b"installed launcher")
    request_path = (
        root / "launcher" / "updates" / "recovery" / uuid4().hex / "request.json"
    )
    with subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as process:
        identity = capture_process_identity(process.pid)
        request = BaselineRecoveryRequest(root, (), (identity,), False)
        request.save(request_path)
        helper = request_path.parent / "Recovery.exe"
        helper.write_bytes(b"owned copied image")
        evidence = request_path.read_bytes()
        if state != "publisher-active":
            _complete_child(process)
            assert process.returncode == 0
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(canonical))
        guard = exclusive_read(helper) if state == "sharing-locked" else nullcontext()
        try:
            with guard:
                assert run_baseline_recovery_bootstrap(()) is None
                assert helper.exists() == (state != "inactive")
                assert request_path.read_bytes() == evidence
            if state == "sharing-locked":
                assert run_baseline_recovery_bootstrap(()) is None
                assert not helper.exists()
        finally:
            if process.poll() is None:
                _complete_child(process)
        assert canonical.read_bytes() == b"installed launcher"


def test_canonical_startup_preserves_unknown_recovery_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated-looking directory without valid ownership is not deletion authority."""
    root = (tmp_path / "installation").resolve()
    root.mkdir()
    canonical = root / "SugarSubstitute.exe"
    canonical.write_bytes(b"installed launcher")
    unknown = root / "launcher" / "updates" / "recovery" / uuid4().hex
    unknown.mkdir(parents=True)
    helper = unknown / "Recovery.exe"
    helper.write_bytes(b"unknown content")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(canonical))
    assert run_baseline_recovery_bootstrap(()) is None
    assert helper.read_bytes() == b"unknown content"


def _complete_child(process: subprocess.Popen[bytes]) -> None:
    """Bound both normal completion and forced cleanup if the OS child stalls."""
    try:
        process.communicate(input=b"x", timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=10)
        raise
