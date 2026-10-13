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

"""Prove failed bursts retain per-invocation evidence without changing ownership."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
from typing import NamedTuple, cast

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.process_identity import ProcessIdentity
from tools.single_instance_packaged_launcher import PackagedLauncherProcess
from tools.single_instance_qualification_diagnostics import (
    capture_failure_diagnostics,
    capture_launcher_snapshot,
)


class _CpuTimes(NamedTuple):
    """Provide the two measured CPU counters used by diagnostic snapshots."""

    user: float = 1.0
    system: float = 2.0


class _Memory(NamedTuple):
    """Provide the observed resident-memory count."""

    rss: int = 4096


@dataclass
class _NativeProcess:
    """Model only kernel observations, never qualification ownership decisions."""

    pid: int
    created: float
    parent: int = 0
    descendants: list[_NativeProcess] = field(default_factory=list)

    def create_time(self) -> float:
        """Return this observed process incarnation."""
        return self.created

    def is_running(self) -> bool:
        """Keep the deterministic snapshot incarnation alive."""
        return True

    def exe(self) -> str:
        """Return the mapped image independently from launch arguments."""
        return "SugarSubstitute.exe"

    def ppid(self) -> int:
        """Return kernel ancestry for this observation."""
        return self.parent

    def status(self) -> str:
        """Report the process state without affecting it."""
        return "running"

    def cpu_times(self) -> _CpuTimes:
        """Return deterministic activity counters."""
        return _CpuTimes()

    def memory_info(self) -> _Memory:
        """Return deterministic residency evidence."""
        return _Memory()

    def num_threads(self) -> int:
        """Return an observed native thread count."""
        return 3

    def children(self) -> list[_NativeProcess]:
        """Return direct children so production code must traverse deeper layers."""
        return self.descendants


class _Bootstrap:
    """Represent a still-live outer process without manufacturing runtime evidence."""

    pid = 100

    def poll(self) -> int | None:
        """Report a blocked bootstrap, the failing qualification boundary."""
        return None


def _launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> PackagedLauncherProcess:
    """Construct the real handle with an external process boundary and output file."""
    monkeypatch.setattr(
        "tools.single_instance_packaged_launcher.capture_process_identity",
        lambda pid: ProcessIdentity(pid, 10.0),
    )
    return PackagedLauncherProcess(
        cast(subprocess.Popen[bytes], _Bootstrap()),
        InstallLayout.from_root(tmp_path),
        output_path=tmp_path / "bootstrap.log",
    )


def test_snapshot_retains_all_layers_without_waiting_for_runtime_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capture bootstrap, onefile child, and deeper descendants before any log exists."""
    launcher = _launcher(tmp_path, monkeypatch)
    grandchild = _NativeProcess(102, 12.0, 101)
    child = _NativeProcess(101, 11.0, 100, [grandchild])
    bootstrap = _NativeProcess(100, 10.0, 99, [child])
    processes = {process.pid: process for process in (bootstrap, child, grandchild)}
    monkeypatch.setattr(
        "tools.single_instance_qualification_diagnostics.psutil.Process",
        processes.__getitem__,
    )

    snapshot = capture_launcher_snapshot(launcher)

    assert snapshot["bootstrap_identity"] == {"pid": 100, "created_at": 10.0}
    assert snapshot["returncode"] is None
    assert snapshot["output_file"] == "bootstrap.log"
    tree = cast(dict[str, object], snapshot["process_tree"])
    assert tree["rss_bytes"] == 4096
    children = cast(list[dict[str, object]], tree["children"])
    assert children[0]["pid"] == 101
    grandchildren = cast(list[dict[str, object]], children[0]["children"])
    assert grandchildren[0]["pid"] == 102


@pytest.mark.parametrize("failure", ["reused", "exited", "access"])
def test_snapshot_does_not_attribute_unavailable_or_reused_processes(
    failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retain explicit uncertainty instead of borrowing a replacement PID's facts."""
    launcher = _launcher(tmp_path, monkeypatch)

    def observe(pid: int) -> _NativeProcess:
        """Model the three native failure boundaries without waiting or signalling."""
        if failure == "exited":
            raise psutil.NoSuchProcess(pid)
        if failure == "access":
            raise psutil.AccessDenied(pid)
        return _NativeProcess(pid, 99.0)

    monkeypatch.setattr(
        "tools.single_instance_qualification_diagnostics.psutil.Process", observe
    )
    tree = cast(dict[str, object], capture_launcher_snapshot(launcher)["process_tree"])
    assert (
        tree["observation"]
        == {
            "reused": "incarnation_exited",
            "exited": "NoSuchProcess",
            "access": "AccessDenied",
        }[failure]
    )
    assert "image" not in tree
    assert "children" not in tree


def test_failure_retains_bootstrap_output_and_survives_missing_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An early onefile failure must leave correlated native output and bootstrap logs."""
    launcher = _launcher(tmp_path, monkeypatch)
    layout = InstallLayout.from_root(tmp_path)
    layout.logs_dir.mkdir(parents=True)
    (layout.logs_dir / "launcher-bootstrap.log").write_text("bootstrap traceback")
    assert launcher.output_path is not None
    launcher.output_path.write_text("native loader failure")

    def departed(pid: int) -> _NativeProcess:
        """Keep process exit from preventing log retention."""
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(
        "tools.single_instance_qualification_diagnostics.psutil.Process", departed
    )
    artifact = tmp_path / "artifacts"
    capture_failure_diagnostics(layout, artifact, [launcher])
    retained = artifact / "failure-diagnostics"
    assert (retained / "bootstrap.log").read_text() == "native loader failure"
    assert (retained / "launcher-bootstrap.log").read_text() == "bootstrap traceback"
    records = json.loads((retained / "launcher-processes.json").read_text())
    assert records[0]["process_tree"]["observation"] == "NoSuchProcess"


def test_diagnostic_destination_failure_preserves_original_qualification_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evidence failure must not replace the real timeout or assertion being diagnosed."""
    launcher = _launcher(tmp_path, monkeypatch)
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied")
    capture_failure_diagnostics(InstallLayout.from_root(tmp_path), blocked, [launcher])


def test_each_launch_retains_its_own_bootstrap_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redirect native diagnostics to independent files without pipes or environment edits."""
    from typing import BinaryIO

    from tools.qualify_single_instance_windows import _launch

    layout = InstallLayout.from_root(tmp_path)
    observed: list[dict[str, object]] = []

    def launch(*args: object, **kwargs: object) -> _Bootstrap:
        """Write native output while the real file handle is open at process creation."""
        observed.append(kwargs)
        stream = cast(BinaryIO, kwargs["stdout"])
        stream.write(b"native bootstrap output")
        assert kwargs["stderr"] == subprocess.STDOUT
        assert kwargs["stdin"] == subprocess.DEVNULL
        return _Bootstrap()

    monkeypatch.setattr(
        "tools.qualify_single_instance_windows.subprocess.Popen", launch
    )
    monkeypatch.setattr(
        "tools.single_instance_packaged_launcher.capture_process_identity",
        lambda pid: ProcessIdentity(pid, 10.0),
    )
    first = _launch(layout)
    second = _launch(layout)
    assert first.output_path is not None and second.output_path is not None
    assert first.output_path != second.output_path
    assert first.output_path.read_bytes() == b"native bootstrap output"
    assert second.output_path.read_bytes() == b"native bootstrap output"
    assert len(observed) == 2
