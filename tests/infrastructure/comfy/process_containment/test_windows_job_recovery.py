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

"""Qualify persisted managed-job ownership against real Windows process families."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import os
from pathlib import Path
import subprocess
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy import managed_process_probe
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedContainmentLaunchResult,
    build_launch_request,
    launch_managed_process,
)
from substitute.infrastructure.comfy.managed_process_probe import ManagedListenerStatus
from substitute.infrastructure.comfy.managed_termination_result import (
    ManagedProcessTerminationStatus,
)
from substitute.infrastructure.comfy.managed_shutdown import (
    kill_managed_comfy_metadata,
)
from substitute.infrastructure.comfy.windows_job_containment import (
    WindowsJobContainmentHandle,
    close_job_containment_handle,
)

pytestmark = pytest.mark.platforms("windows")


@dataclass(frozen=True)
class _ManagedJob:
    """Retain the launched root and the Python process inside its native job."""

    launch: ManagedContainmentLaunchResult
    python_process: psutil.Process


@pytest.fixture
def managed_job(tmp_path: Path) -> Iterator[_ManagedJob]:
    """Publish child readiness over a bounded pipe and always retire the owned job."""
    script = tmp_path / "main.py"
    script.write_text(
        "import os, threading\nprint(os.getpid(), flush=True)\n"
        "threading.Event().wait(120)\n",
        encoding="utf-8",
    )
    launch = launch_managed_process(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace=tmp_path,
        request=build_launch_request(
            command=(
                sys.executable,
                str(script),
                "--listen",
                "127.0.0.1",
                "--port",
                "8188",
            ),
            cwd=tmp_path,
            env=os.environ.copy(),
            capture_output=True,
        ),
    )
    assert isinstance(launch.containment_handle, WindowsJobContainmentHandle)
    assert launch.stdout_stream is not None
    reader = ThreadPoolExecutor(max_workers=1)
    processes = [psutil.Process(launch.process.pid)]
    try:
        ready = reader.submit(launch.stdout_stream.readline)
        python_pid = int(ready.result(timeout=15))
        python_process = psutil.Process(python_pid)
        if python_pid != launch.process.pid:
            processes.append(python_process)
        yield _ManagedJob(launch, python_process)
    finally:
        close_job_containment_handle(launch.containment_handle)
        reader.shutdown(wait=True)
        launch.stdout_stream.close()
        _gone, alive = psutil.wait_procs(processes, timeout=10)
        assert not alive, "Native fixture job did not retire its processes"


def test_listener_in_owned_job_is_healthy_even_when_pid_differs_from_root(
    managed_job: _ManagedJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recognize the native Python child behind Windows' virtualenv redirector."""
    metadata = managed_job.launch.metadata
    assert managed_job.python_process.pid != metadata.pid
    monkeypatch.setattr(managed_process_probe, "is_endpoint_listening", lambda *_: True)
    monkeypatch.setattr(
        managed_process_probe,
        "get_listener_pid",
        lambda *_: managed_job.python_process.pid,
    )
    result = managed_process_probe.probe_managed_listener(
        host=metadata.host,
        port=metadata.port,
        workspace=metadata.workspace_path,
        metadata=metadata,
    )
    assert result.status is ManagedListenerStatus.OWNED_HEALTHY
    assert managed_job.python_process.is_running()


def test_recovered_job_cleanup_does_not_depend_on_taskkill(
    managed_job: _ManagedJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reopen the persisted native family and confirm all members exit without a CLI."""

    def unavailable(command: object, **kwargs: object) -> object:
        """Expose accidental reliance on an external termination command."""
        raise OSError("External process termination command is unavailable")

    monkeypatch.setattr(subprocess, "run", unavailable)
    result = kill_managed_comfy_metadata(managed_job.launch.metadata)
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert not managed_job.python_process.is_running()


def test_job_cleanup_ignores_a_reused_metadata_pid(
    managed_job: _ManagedJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep an unrelated live PID untouched while retiring the recorded native job."""

    def forbid_pid_command(command: object, **kwargs: object) -> object:
        """Prevent a regressed PID-based command from terminating the test host."""
        raise AssertionError("Persisted native job cleanup must not run a PID command")

    monkeypatch.setattr(subprocess, "run", forbid_pid_command)
    metadata = replace(managed_job.launch.metadata, pid=os.getpid())
    result = kill_managed_comfy_metadata(metadata)
    assert result.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert not managed_job.python_process.is_running()


@pytest.mark.parametrize("listener_resolved", [False, True])
def test_unrelated_listener_is_not_adopted(
    managed_job: _ManagedJob,
    monkeypatch: pytest.MonkeyPatch,
    listener_resolved: bool,
) -> None:
    """Reject a listener outside the recorded job despite matching endpoint metadata."""
    metadata = managed_job.launch.metadata
    listener_pid = os.getpid() if listener_resolved else None
    monkeypatch.setattr(managed_process_probe, "is_endpoint_listening", lambda *_: True)
    monkeypatch.setattr(
        managed_process_probe, "get_listener_pid", lambda *_: listener_pid
    )
    result = managed_process_probe.probe_managed_listener(
        host=metadata.host,
        port=metadata.port,
        workspace=metadata.workspace_path,
        metadata=metadata,
    )
    assert result.status is ManagedListenerStatus.FOREIGN


@pytest.mark.parametrize("release_owner", [False, True])
def test_repeated_cleanup_accepts_an_already_retired_family(
    managed_job: _ManagedJob, release_owner: bool
) -> None:
    """Complete cleanup with either an empty retained job or an absent native job."""
    first = kill_managed_comfy_metadata(managed_job.launch.metadata)
    assert first.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    if release_owner:
        handle = managed_job.launch.containment_handle
        assert isinstance(handle, WindowsJobContainmentHandle)
        close_job_containment_handle(handle)
    repeated = kill_managed_comfy_metadata(managed_job.launch.metadata)
    assert repeated.status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED
    assert not managed_job.python_process.is_running()
