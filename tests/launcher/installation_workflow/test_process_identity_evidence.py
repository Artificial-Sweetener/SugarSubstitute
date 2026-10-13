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

"""Prove launcher ancestry survives serialization without accepting partial identity."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LauncherProcessEvidence,
    capture_launcher_process_evidence,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
)


@dataclass
class ObservedProcess:
    """Control the operating-system observation boundary without inventing evidence."""

    pid: int
    created_at: float
    executable: str
    parent_pid: int = 0
    running: bool = True
    changed_parent_pid: int | None = None
    parent_reads: int = 0

    def create_time(self) -> float:
        """Supply the kernel timestamp independently from wall-clock time."""
        return self.created_at

    def exe(self) -> str:
        """Supply the process image independently from the Python executable."""
        return self.executable

    def ppid(self) -> int:
        """Simulate an optional reparenting between identity observations."""
        self.parent_reads += 1
        if self.parent_reads > 1 and self.changed_parent_pid is not None:
            return self.changed_parent_pid
        return self.parent_pid

    def is_running(self) -> bool:
        """Expose departure or PID reuse after executable capture."""
        return self.running


@pytest.fixture
def observed_processes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[ObservedProcess, ObservedProcess]:
    """Bind current and parent observations to portable installed image paths."""
    executable = str(tmp_path / "SugarSubstitute")
    parent = ObservedProcess(420, 1700000000.125, executable)
    child = ObservedProcess(421, 1700000000.25, executable, parent_pid=parent.pid)

    def process_for(pid: int | None = None) -> ObservedProcess:
        """Resolve only the observed current process and its recorded parent."""
        if pid is None or pid == child.pid:
            return child
        if pid == parent.pid:
            return parent
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", process_for)
    return child, parent


def test_capture_records_kernel_identities_and_images(
    observed_processes: tuple[ObservedProcess, ObservedProcess],
) -> None:
    """Keep runtime ancestry available after both observed processes have exited."""
    child, parent = observed_processes

    evidence = capture_launcher_process_evidence()
    payload = json.loads(json.dumps(evidence.to_json()))
    restored = LauncherProcessEvidence.from_json(payload)

    assert restored == evidence
    assert restored.identity == ProcessIdentity(child.pid, child.created_at)
    assert restored.parent_identity == ProcessIdentity(parent.pid, parent.created_at)
    assert restored.executable == child.executable
    assert restored.parent_executable == parent.executable


def test_capture_preserves_different_parent_executable(
    observed_processes: tuple[ObservedProcess, ObservedProcess], tmp_path: Path
) -> None:
    """Leave image matching to qualification without disguising an unrelated parent."""
    _, parent = observed_processes
    parent.executable = str(tmp_path / "unrelated-parent")

    evidence = capture_launcher_process_evidence()

    assert evidence.parent_executable == parent.executable
    assert evidence.parent_executable != evidence.executable


@pytest.mark.parametrize("failure", ["reparented", "exited", "reused", "missing"])
def test_capture_rejects_unverified_ancestry(
    observed_processes: tuple[ObservedProcess, ObservedProcess], failure: str
) -> None:
    """Never emit usable evidence for a missing, departed, or replaced parent."""
    child, parent = observed_processes
    if failure == "reparented":
        child.changed_parent_pid = parent.pid + 100
    elif failure == "exited":
        parent.running = False
    elif failure == "reused":
        parent.created_at = child.created_at + 1.0
    else:
        child.parent_pid = 0

    with pytest.raises(ProcessIdentityError):
        capture_launcher_process_evidence()


@pytest.mark.parametrize("target", ["runtime", "parent"])
@pytest.mark.parametrize("operation", ["create_time", "exe"])
@pytest.mark.parametrize("error_kind", ["access_denied", "no_such_process", "os_error"])
def test_capture_reports_process_observation_failure(
    observed_processes: tuple[ObservedProcess, ObservedProcess],
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    operation: str,
    error_kind: str,
) -> None:
    """Retain the inspection failure as the cause rather than fabricating identity."""
    child, parent = observed_processes
    process = child if target == "runtime" else parent
    error: Exception
    if error_kind == "access_denied":
        error = psutil.AccessDenied(process.pid)
    elif error_kind == "no_such_process":
        error = psutil.NoSuchProcess(process.pid)
    else:
        error = OSError("Process image inspection failed")

    def fail_observation() -> None:
        """Fail the requested kernel observation at its external boundary."""
        raise error

    monkeypatch.setattr(process, operation, fail_observation)

    with pytest.raises(ProcessIdentityError) as caught:
        capture_launcher_process_evidence()

    assert caught.value.__cause__ is error


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("identity", None),
        ("parent_identity", None),
        ("executable", None),
        ("executable", ""),
        ("executable", "  "),
        ("parent_executable", "\x00"),
    ],
)
def test_parser_rejects_incomplete_evidence(
    observed_processes: tuple[ObservedProcess, ObservedProcess],
    field: str,
    invalid: object,
) -> None:
    """Require each diagnostic field before qualification can consume a record."""
    del observed_processes
    payload = capture_launcher_process_evidence().to_json()
    payload[field] = invalid

    with pytest.raises(ValueError):
        LauncherProcessEvidence.from_json(payload)


@pytest.mark.parametrize("identity_field", ["identity", "parent_identity"])
@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("pid", 0),
        ("pid", -1),
        ("pid", True),
        ("pid", "420"),
        ("created_at", 0),
        ("created_at", -1),
        ("created_at", float("nan")),
        ("created_at", float("inf")),
        ("created_at", True),
        ("created_at", "1700000000.125"),
        ("created_at", None),
    ],
)
def test_parser_rejects_pid_only_or_invalid_identity(
    observed_processes: tuple[ObservedProcess, ObservedProcess],
    identity_field: str,
    field: str,
    invalid: object,
) -> None:
    """Keep both sides of ancestry bound to exact valid process incarnations."""
    del observed_processes
    payload = capture_launcher_process_evidence().to_json()
    identity = payload[identity_field]
    assert isinstance(identity, dict)
    identity[field] = invalid

    with pytest.raises(ValueError):
        LauncherProcessEvidence.from_json(payload)


@pytest.mark.parametrize("failure", ["same_pid", "newer_parent"])
def test_parser_rejects_inconsistent_parent(
    observed_processes: tuple[ObservedProcess, ObservedProcess], failure: str
) -> None:
    """Reject self-parenting and a reused parent that is newer than the runtime."""
    child, parent = observed_processes
    payload = capture_launcher_process_evidence().to_json()
    payload["parent_identity"] = {
        "pid": child.pid if failure == "same_pid" else parent.pid,
        "created_at": child.created_at + 1.0
        if failure == "newer_parent"
        else parent.created_at,
    }

    with pytest.raises(ValueError):
        LauncherProcessEvidence.from_json(payload)
