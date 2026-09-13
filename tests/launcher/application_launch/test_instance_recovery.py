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

"""Verify that explicit instance recovery cannot terminate an unrelated process."""

from __future__ import annotations

from pathlib import Path

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher import application_instance_recovery
from launcher.sugarsubstitute_launcher.application_instance_recovery import (
    terminate_verified_instance_owner,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
)


class _Connection:
    """Expose a kernel-identity result at the recovery boundary."""

    def __init__(self, peer_process_id: int | None) -> None:
        """Store the simulated endpoint owner."""

        self._peer_process_id = peer_process_id
        self.closed = False

    def peer_process_id(self) -> int | None:
        """Return the simulated peer identity."""

        return self._peer_process_id

    def close(self) -> None:
        """Record connection cleanup."""

        self.closed = True


class _Process:
    """Record process control after endpoint and executable verification."""

    def __init__(self, executable: Path, *, hang_on_terminate: bool = False) -> None:
        """Store executable identity and optional forced escalation."""

        self._executable = executable
        self._hang_on_terminate = hang_on_terminate
        self.terminated = False
        self.killed = False
        self.wait_count = 0

    def exe(self) -> str:
        """Return the simulated executable path."""

        return str(self._executable)

    def terminate(self) -> None:
        """Record graceful termination."""

        self.terminated = True

    def kill(self) -> None:
        """Record forced termination."""

        self.killed = True

    def wait(self, *, timeout: float) -> None:
        """Optionally force the first bounded wait to time out."""

        _ = timeout
        self.wait_count += 1
        if self._hang_on_terminate and self.wait_count == 1:
            raise psutil.TimeoutExpired(timeout, pid=4401)


def test_recovery_refuses_pid_that_no_longer_owns_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PID reuse or owner replacement must fail closed before process lookup."""

    connection = _Connection(peer_process_id=9902)
    monkeypatch.setattr(
        application_instance_recovery,
        "connect_instance_endpoint",
        lambda _endpoint: connection,
    )
    process_lookups: list[int] = []
    monkeypatch.setattr(
        psutil,
        "Process",
        lambda pid: process_lookups.append(pid),
    )

    assert not terminate_verified_instance_owner(
        _recovery_error(owner_process_id=4401),
        expected_executable=tmp_path / "SugarSubstitute.exe",
    )
    assert process_lookups == []
    assert connection.closed


def test_recovery_refuses_same_pid_with_different_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A matching endpoint PID is insufficient without executable identity."""

    process = _Process(tmp_path / "unrelated.exe")
    monkeypatch.setattr(
        application_instance_recovery,
        "connect_instance_endpoint",
        lambda _endpoint: _Connection(peer_process_id=4401),
    )
    monkeypatch.setattr(
        psutil,
        "Process",
        lambda _pid: process,
    )

    assert not terminate_verified_instance_owner(
        _recovery_error(owner_process_id=4401),
        expected_executable=tmp_path / "SugarSubstitute.exe",
    )
    assert not process.terminated
    assert not process.killed


@pytest.mark.parametrize("hang_on_terminate", [False, True])
def test_recovery_terminates_only_reverified_exact_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    hang_on_terminate: bool,
) -> None:
    """An explicit recovery action may escalate only for the exact live owner."""

    executable = tmp_path / "SugarSubstitute.exe"
    process = _Process(executable, hang_on_terminate=hang_on_terminate)
    monkeypatch.setattr(
        application_instance_recovery,
        "connect_instance_endpoint",
        lambda _endpoint: _Connection(peer_process_id=4401),
    )
    monkeypatch.setattr(
        psutil,
        "Process",
        lambda _pid: process,
    )

    assert terminate_verified_instance_owner(
        _recovery_error(owner_process_id=4401),
        expected_executable=executable,
    )
    assert process.terminated
    assert process.killed is hang_on_terminate
    assert process.wait_count == (2 if hang_on_terminate else 1)


def _recovery_error(*, owner_process_id: int) -> ApplicationInstanceBrokerError:
    """Return one recoverable broker failure with a concrete native endpoint."""

    return ApplicationInstanceBrokerError(
        "unavailable",
        owner_process_id=owner_process_id,
        endpoint=ApplicationInstanceEndpoint(
            transport="windows-named-pipe",
            address=r"\\.\pipe\SugarSubstitute-test",
        ),
    )
