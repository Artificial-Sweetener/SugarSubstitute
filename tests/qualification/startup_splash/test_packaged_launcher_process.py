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

"""Prove onefile qualification tracks exact runtime incarnations and ownership."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
from typing import cast

import pytest
import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LAUNCHER_PROCESS_EVENT,
    LauncherProcessEvidence,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity
from tools.single_instance_packaged_launcher import (
    PackagedLauncherProcess,
    validate_onefile_runtime,
)


class _Bootstrap:
    """Model completion independently from the child PID in a recorded launch."""

    pid = 100
    returncode: int | None = 0

    def poll(self) -> int | None:
        """Report an already-exited forwarder to exercise durable evidence."""
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        """Propagate the runtime status through the outer bootstrap."""
        return 0


class _Runtime:
    """Expose only the native identity and signal boundary used by the handle."""

    def __init__(self, evidence: LauncherProcessEvidence) -> None:
        """Retain the observed incarnation without reimplementing validation."""
        self.evidence = evidence
        self.killed = False
        self.terminated = False

    def create_time(self) -> float:
        """Return the observed kernel creation time."""
        return self.evidence.identity.created_at

    def exe(self) -> str:
        """Return the observed executable image."""
        return self.evidence.executable

    def kill(self) -> None:
        """Record a destructive signal only when validation permits it."""
        self.killed = True

    def terminate(self) -> None:
        """Record orderly termination separately from a crash."""
        self.terminated = True


def _evidence(layout: InstallLayout) -> LauncherProcessEvidence:
    """Build a same-image child whose parent is the launched incarnation."""
    return LauncherProcessEvidence(
        ProcessIdentity(101, 11.0),
        ProcessIdentity(100, 10.0),
        str(layout.executable_path),
        str(layout.executable_path),
    )


def _handle(
    layout: InstallLayout,
    records: list[LauncherProcessEvidence],
    monkeypatch: pytest.MonkeyPatch,
) -> PackagedLauncherProcess:
    """Publish durable diagnostics before observing an already-exited invocation."""
    layout.logs_dir.mkdir(parents=True)
    (layout.logs_dir / "launcher.log").write_text(
        "".join(
            LAUNCHER_PROCESS_EVENT + json.dumps(record.to_json()) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.single_instance_packaged_launcher.capture_process_identity",
        lambda pid: ProcessIdentity(pid, 10.0),
    )
    return PackagedLauncherProcess(cast(subprocess.Popen[bytes], _Bootstrap()), layout)


def test_exited_forwarder_retains_runtime_identity_and_bootstrap_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fast forwarders remain correlated without sampling or serializing launch bursts."""
    layout = InstallLayout.from_root(tmp_path)
    evidence = _evidence(layout)
    handle = _handle(layout, [evidence, evidence], monkeypatch)
    assert handle.bootstrap_identity == ProcessIdentity(100, 10.0)
    assert handle.runtime_pid == 101
    assert handle.runtime_evidence == evidence
    assert handle.poll() == 0
    assert handle.wait(timeout=1.0) == 0
    assert handle.returncode == 0


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_parent",
        "reused_parent",
        "wrong_image",
        "wrong_parent_image",
    ],
)
def test_onefile_relationship_rejects_unproven_runtime(
    fault: str, tmp_path: Path
) -> None:
    """Never infer runtime ownership merely from a matching executable name."""
    layout = InstallLayout.from_root(tmp_path)
    evidence = _evidence(layout)
    if fault == "wrong_parent":
        evidence = replace(evidence, parent_identity=ProcessIdentity(999, 10.0))
    elif fault == "reused_parent":
        evidence = replace(evidence, parent_identity=ProcessIdentity(100, 9.0))
    elif fault == "wrong_image":
        evidence = replace(evidence, executable=str(tmp_path / "Other.exe"))
    elif fault == "wrong_parent_image":
        evidence = replace(evidence, parent_executable=str(tmp_path / "Other.exe"))
    with pytest.raises(AssertionError, match="Invalid onefile"):
        validate_onefile_runtime(
            evidence,
            bootstrap=ProcessIdentity(100, 10.0),
            executable=layout.executable_path,
        )


@pytest.mark.parametrize("fault", ["missing", "reused_parent", "multiple_children"])
def test_runtime_resolution_rejects_missing_or_ambiguous_ownership(
    fault: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed launch cannot borrow another invocation's recorded runtime."""
    layout = InstallLayout.from_root(tmp_path)
    evidence = _evidence(layout)
    records = [evidence]
    if fault == "missing":
        records = []
    elif fault == "reused_parent":
        records = [replace(evidence, parent_identity=ProcessIdentity(100, 9.0))]
    elif fault == "multiple_children":
        records.append(replace(evidence, identity=ProcessIdentity(102, 11.0)))
    handle = _handle(layout, records, monkeypatch)
    with pytest.raises(AssertionError):
        _ = handle.runtime_pid


@pytest.mark.parametrize("fault", [None, "reused_pid", "changed_image"])
def test_runtime_crash_targets_only_the_recorded_incarnation(
    fault: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crash the Python broker, leaving a reused PID or unrelated image untouched."""
    layout = InstallLayout.from_root(tmp_path)
    evidence = _evidence(layout)
    handle = _handle(layout, [evidence], monkeypatch)
    observed = evidence
    if fault == "reused_pid":
        observed = replace(evidence, identity=ProcessIdentity(101, 20.0))
    elif fault == "changed_image":
        observed = replace(evidence, executable=str(tmp_path / "Other.exe"))
    runtime = _Runtime(observed)
    requested: list[int] = []

    def process(pid: int) -> _Runtime:
        """Retain which PID the production handle actually inspects."""
        requested.append(pid)
        return runtime

    monkeypatch.setattr(
        "tools.single_instance_packaged_launcher.psutil.Process", process
    )
    if fault is None:
        handle.kill()
        assert runtime.killed
    else:
        with pytest.raises(AssertionError, match="identity changed"):
            handle.kill()
        assert not runtime.killed
    assert requested == [101]


def test_already_exited_runtime_does_not_break_bootstrap_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A native runtime may exit before its onefile parent finishes cleanup."""
    layout = InstallLayout.from_root(tmp_path)
    handle = _handle(layout, [_evidence(layout)], monkeypatch)

    def missing_process(pid: int) -> _Runtime:
        """Model an exited incarnation without signaling any replacement."""
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(
        "tools.single_instance_packaged_launcher.psutil.Process", missing_process
    )
    handle.terminate()
    handle.kill()
    assert handle.wait(timeout=1.0) == 0


def test_cleanup_reaps_bootstrap_when_runtime_never_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed extraction must not hide qualification failure with missing evidence."""
    layout = InstallLayout.from_root(tmp_path)
    handle = _handle(layout, [], monkeypatch)
    bootstrap = cast(_Bootstrap, handle.bootstrap)
    bootstrap.returncode = None
    clock = iter((0.0, 31.0))
    monkeypatch.setattr(
        "tools.single_instance_packaged_launcher.time.monotonic", lambda: next(clock)
    )
    stopped: list[int] = []

    def terminate() -> None:
        """Signal the owned Popen handle rather than guessing an unobserved child."""
        stopped.append(bootstrap.pid)
        bootstrap.returncode = 1

    monkeypatch.setattr(bootstrap, "terminate", terminate, raising=False)
    handle.cleanup()
    assert stopped == [100]


def test_runtime_identity_is_read_after_observing_fast_forwarder_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exit observed during polling must not condemn a stale pre-exit log read."""
    layout = InstallLayout.from_root(tmp_path)
    evidence = _evidence(layout)
    handle = _handle(layout, [], monkeypatch)

    def completed() -> int:
        """Publish the last flushed record exactly when completion becomes observable."""
        (layout.logs_dir / "launcher.log").write_text(
            LAUNCHER_PROCESS_EVENT + json.dumps(evidence.to_json()) + "\n",
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(handle.bootstrap, "poll", completed)
    assert handle.runtime_pid == evidence.identity.pid


@pytest.mark.parametrize(
    "failure", ["log_access", "runtime_access", "bootstrap_access"]
)
def test_cleanup_preserves_original_failure_when_process_access_is_lost(
    failure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Access failures during disposal cannot abort later installation cleanup."""
    layout = InstallLayout.from_root(tmp_path)
    handle = _handle(layout, [_evidence(layout)], monkeypatch)
    bootstrap = cast(_Bootstrap, handle.bootstrap)
    bootstrap.returncode = None

    def inaccessible_runtime() -> None:
        """Model the distinct external failures seen during cleanup."""
        if failure == "log_access":
            raise PermissionError("diagnostic log unavailable")
        raise psutil.AccessDenied(101)

    def terminate_bootstrap() -> None:
        """Fail native fallback independently from the recorded runtime."""
        if failure == "bootstrap_access":
            raise PermissionError("bootstrap unavailable")
        bootstrap.returncode = 1

    monkeypatch.setattr(handle, "terminate", inaccessible_runtime)
    monkeypatch.setattr(bootstrap, "terminate", terminate_bootstrap, raising=False)
    handle.cleanup()
