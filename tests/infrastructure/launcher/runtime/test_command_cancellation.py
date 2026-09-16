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

"""Require runtime cancellation to reclaim its native execution before returning."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from threading import Event

import psutil  # type: ignore[import-untyped]  # psutil ships without type information.
import pytest

from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeCommandCancelled
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    wait_for_process_exit,
)


def test_cancelled_runtime_command_never_starts(tmp_path: Path) -> None:
    """Honor close before admitting another package-management command."""
    cancellation = Event()
    cancellation.set()
    marker = tmp_path / "unexpected-start"
    runner = SubprocessRuntimeCommandRunner(cancellation=cancellation)
    with pytest.raises(RuntimeCommandCancelled, match="cancelled"):
        runner.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
                str(marker),
            ],
            cwd=tmp_path,
            env=os.environ,
        )
    assert not marker.exists()


@pytest.mark.platforms("windows")
def test_cancelled_runtime_command_reclaims_silent_native_family(
    tmp_path: Path,
) -> None:
    """An open output handle and a silent descendant cannot prevent cancellation."""
    cancellation = Event()
    children: list[psutil.Process] = []

    def observe(line: str) -> None:
        """Retain exact child identities once both native processes are ready."""
        children.extend(psutil.Process(pid) for pid in json.loads(line))
        cancellation.set()

    script = (
        "import json, os, subprocess, sys; from threading import Event; "
        "child = subprocess.Popen([sys.executable, '-c', 'from threading import Event; Event().wait(20)']); "
        "print(json.dumps([os.getpid(), child.pid]), flush=True); "
        "sys.stdout.write('partial output without a newline'); sys.stdout.flush(); "
        "Event().wait(20)"
    )
    try:
        with pytest.raises(RuntimeCommandCancelled, match="cancelled"):
            SubprocessRuntimeCommandRunner(observe, cancellation=cancellation).run(
                [sys.executable, "-c", script], cwd=tmp_path, env=os.environ
            )
        assert len(children) == 2
        assert all(not child.is_running() for child in children)
    finally:
        for child in children:
            if child.is_running():
                child.kill()
                child.wait(5)


def test_callback_failure_reclaims_native_runtime_child(tmp_path: Path) -> None:
    """Exceptional output consumers must not abandon a live runtime command."""
    children: list[psutil.Process] = []

    def observe(line: str) -> None:
        """Model an unexpected consumer failure after native process admission."""
        children.append(psutil.Process(int(line)))
        raise ValueError("qualification consumer failure")

    try:
        with pytest.raises(ValueError, match="qualification consumer failure"):
            SubprocessRuntimeCommandRunner(observe).run(
                [
                    sys.executable,
                    "-c",
                    "import os; from threading import Event; print(os.getpid(), flush=True); Event().wait(20)",
                ],
                cwd=tmp_path,
                env=os.environ,
            )
        assert children
        assert all(not child.is_running() for child in children)
    finally:
        for child in children:
            if child.is_running():
                child.kill()
                child.wait(5)


@pytest.mark.platforms("windows")
def test_successful_runtime_root_reclaims_remaining_descendant(tmp_path: Path) -> None:
    """A successful tool must not leave an output-holding helper running behind it."""
    descendants: list[ProcessIdentity] = []

    def observe(line: str) -> None:
        """Read birth identity even if the runner has already reclaimed the child."""
        pid, created = json.loads(line)
        descendants.append(ProcessIdentity(int(pid), float(created)))

    script = (
        "import json, psutil, subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'from threading import Event; Event().wait(20)']); "
        "print(json.dumps([child.pid, psutil.Process(child.pid).create_time()]), flush=True)"
    )
    try:
        SubprocessRuntimeCommandRunner(observe).run(
            [sys.executable, "-c", script], cwd=tmp_path, env=os.environ
        )
        assert len(descendants) == 1
        for identity in descendants:
            wait_for_process_exit(identity, timeout_seconds=0)
    finally:
        for identity in descendants:
            try:
                child = psutil.Process(identity.pid)
                if abs(child.create_time() - identity.created_at) < 0.000001:
                    child.kill()
                    child.wait(5)
            except psutil.NoSuchProcess:
                pass
