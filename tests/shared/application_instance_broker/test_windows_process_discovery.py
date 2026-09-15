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

"""Verify recovery discovery is scoped to one earlier installed Windows instance."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
import os
from pathlib import Path

import psutil  # type: ignore[import-untyped]
import pytest

from sugarsubstitute_shared import windows_application_processes as discovery
from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared.windows_process_security import (
    process_session_id,
    process_user_sid,
)


@dataclass
class _Process:
    """Supply controlled kernel observations without creating or ending processes."""

    pid: int
    executable: Path
    created: float
    user: str = "user-a"
    session: int = 1
    running: bool = True
    inaccessible: bool = False

    def exe(self) -> str:
        """Return a controlled image path or an access failure."""
        if self.inaccessible:
            raise psutil.AccessDenied(self.pid)
        return str(self.executable)

    def create_time(self) -> float:
        """Return this process incarnation's creation timestamp."""
        return self.created

    def is_running(self) -> bool:
        """Model the final PID-reuse and process-exit check."""
        return self.running

    def cmdline(self) -> list[str]:
        """Return this fixture's default launcher invocation."""
        return [str(self.executable)]

    def cwd(self) -> str:
        """Resolve relative installation arguments against this process directory."""
        return str(self.executable.parent)


def _accept_invocation(arguments: Sequence[str], working_directory: Path) -> bool:
    """Leave application argument policy outside these OS adapter tests."""
    return True


def _install_processes(
    monkeypatch: pytest.MonkeyPatch, processes: list[_Process]
) -> None:
    """Replace only the external process and token query boundaries."""
    by_pid = {process.pid: process for process in processes}
    monkeypatch.setattr(psutil, "pids", lambda: list(by_pid))
    monkeypatch.setattr(psutil, "Process", lambda pid: by_pid[pid])
    monkeypatch.setattr(discovery, "process_user_sid", lambda pid: by_pid[pid].user)
    monkeypatch.setattr(
        discovery, "process_session_id", lambda pid: by_pid[pid].session
    )


def test_discovery_selects_oldest_matching_earlier_instance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ignore unrelated installations, users, sessions, replacements and recycled PIDs."""
    executable = tmp_path / "installed" / "SugarSubstitute.exe"
    caller = _Process(os.getpid(), executable, 100.0)
    processes = [
        caller,
        _Process(1, executable, 30.0),
        _Process(2, executable, 20.0),
        _Process(3, tmp_path / "other" / "SugarSubstitute.exe", 1.0),
        _Process(4, executable, 1.0, user="user-b"),
        _Process(5, executable, 1.0, session=2),
        _Process(6, executable, 1.0, running=False),
        _Process(7, executable, 1.0, inaccessible=True),
        _Process(8, executable, 101.0),
        _Process(9, executable, 100.0),
    ]
    _install_processes(monkeypatch, processes)
    assert discovery.find_previous_application_process(
        executable, accepts_invocation=_accept_invocation
    ) == ProcessIdentity(2, 20.0)


@pytest.mark.parametrize(
    "mismatch", ["executable", "user", "session", "newer", "exited", "access"]
)
def test_discovery_never_offers_an_ineligible_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mismatch: str,
) -> None:
    """A candidate must independently satisfy every scope and lifetime requirement."""
    executable = tmp_path / "SugarSubstitute.exe"
    caller = _Process(os.getpid(), executable, 100.0)
    candidate = _Process(1, executable, 1.0)
    if mismatch == "executable":
        candidate.executable = tmp_path / "other" / "SugarSubstitute.exe"
    elif mismatch == "user":
        candidate.user = "other-user"
    elif mismatch == "session":
        candidate.session = 2
    elif mismatch == "newer":
        candidate.created = 101.0
    elif mismatch == "exited":
        candidate.running = False
    else:
        candidate.inaccessible = True
    _install_processes(monkeypatch, [caller, candidate])
    assert (
        discovery.find_previous_application_process(
            executable, accepts_invocation=_accept_invocation
        )
        is None
    )


def test_source_interpreter_cannot_discover_installed_recovery_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Do not use a claimed packaged path as authority to inspect other instances."""
    executable = tmp_path / "SugarSubstitute.exe"
    _install_processes(
        monkeypatch,
        [
            _Process(os.getpid(), tmp_path / "python.exe", 100.0),
            _Process(1, executable, 1.0),
        ],
    )
    assert (
        discovery.find_previous_application_process(
            executable, accepts_invocation=_accept_invocation
        )
        is None
    )


@pytest.mark.platforms("windows")
def test_native_process_security_identity_matches_current_token() -> None:
    """Read the actual process token and Windows session without application IPC."""
    assert process_user_sid(None) == process_user_sid(os.getpid())
    assert process_user_sid(None).startswith("S-1-")
    assert process_session_id(os.getpid()) >= 0
    with pytest.raises(OSError):
        process_session_id(0xFFFFFFFF)
