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

from sugarsubstitute_shared.application_process_scope import ExactExecutableProcessScope

from pathlib import Path
import os
import sys
from collections.abc import Sequence, Iterator
from contextlib import contextmanager
from launcher.sugarsubstitute_launcher import application_instance_recovery
from sugarsubstitute_shared.process_identity import ProcessIdentity

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher.application_instance_recovery import (
    terminate_verified_process,
)
from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher.application_process_discovery import (
    InstalledInvocationScope,
)
from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
)
from sugarsubstitute_shared.application_instance_identity import instance_identity
from sugarsubstitute_shared.application_instance_transport import (
    instance_endpoint,
)


class _Process:
    """Record process control after endpoint and executable verification."""

    def __init__(
        self,
        executable: Path,
        *,
        hang_on_terminate: bool = False,
        arguments: tuple[str, ...] = (),
    ) -> None:
        """Store executable identity and optional forced escalation."""

        self._executable = executable
        self._arguments = arguments
        self._hang_on_terminate = hang_on_terminate
        self.terminated = False
        self.killed = False
        self.wait_count = 0

    def create_time(self) -> float:
        """Return the exact process incarnation captured before the hang."""
        return 123.0

    def exe(self) -> str:
        """Return the simulated executable path."""

        return str(self._executable)

    def cmdline(self) -> list[str]:
        """Return the OS-observed invocation for this controlled process."""
        return [str(self._executable), *self._arguments]

    def cwd(self) -> str:
        """Bind relative process arguments to the observed working directory."""
        return str(self._executable.parent)

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
        if not self.terminated and not self.killed:
            raise psutil.TimeoutExpired(timeout, pid=4401)
        if self._hang_on_terminate and self.wait_count == 1:
            raise psutil.TimeoutExpired(timeout, pid=4401)


def _bind_process(monkeypatch: pytest.MonkeyPatch, process: _Process) -> None:
    """Replace the process boundary without ever opening a real fixture PID."""

    @contextmanager
    def open_process(pid: int) -> Iterator[_Process]:
        """Retain the deterministic candidate through the recovery transaction."""
        assert pid == 4401
        yield process

    monkeypatch.setattr(psutil, "Process", lambda _pid: process)
    monkeypatch.setattr(
        application_instance_recovery, "open_instance_process", open_process
    )
    from sugarsubstitute_shared import windows_process_security

    monkeypatch.setattr(windows_process_security, "process_session_id", lambda _pid: 1)


@pytest.mark.parametrize("copied_bundle", [False, True])
def test_normal_launch_recovers_the_authenticated_repair_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, copied_bundle: bool
) -> None:
    """Recover an authenticated repair owner even after its request is retired."""
    layout = InstallLayout.from_root(tmp_path, target=WINDOWS_X64)
    executable = (
        layout.root / ".repair/helper/1.2.3/session-owned/bundle/SugarSubstitute.exe"
        if copied_bundle
        else layout.launcher_support_path / "Repair.exe"
    )
    process = _Process(
        executable,
        arguments=(
            f"--execute-repair-request={layout.root / '.repair' / 'prepared.json'}",
        )
        if copied_bundle
        else (),
    )
    _bind_process(monkeypatch, process)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    failures = iter(
        (
            ApplicationInstanceBrokerError(
                "frozen repair",
                endpoint=instance_endpoint(instance_identity(layout.root)),
                owner_identity=ProcessIdentity(4401, 123.0),
            ),
        )
    )

    def elect(
        _layout: InstallLayout, arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Return ownership after the single recorded failed election."""
        error = next(failures, None)
        if error is not None:
            raise error
        return None

    def present(**kwargs: object) -> InstanceRecoveryAction:
        """Reject a manual workflow for automatic owner retirement."""
        pytest.fail("Verified hung owner required manual recovery")

    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    ApplicationElectionRecovery(
        layout=layout, process_arguments=(), locale_override="en", elect=elect
    ).run()
    assert process.terminated


def test_recovery_refuses_to_end_itself(tmp_path: Path) -> None:
    """A malformed recovery target cannot close the user's recovery surface."""
    assert not terminate_verified_process(
        ProcessIdentity(os.getpid(), 123.0),
        scope=ExactExecutableProcessScope((tmp_path / "app.exe",)),
    )


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("owner_session", [2, None])
def test_automatic_recovery_preserves_other_or_unverified_sessions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, owner_session: int | None
) -> None:
    """Require same-session native evidence even when process discovery succeeds."""
    from sugarsubstitute_shared import windows_process_security

    executable = tmp_path / "SugarSubstitute.exe"
    process = _Process(executable)
    _bind_process(monkeypatch, process)

    def session_id(pid: int) -> int:
        """Model another desktop or unavailable native session metadata."""
        if pid != 4401:
            return 1
        if owner_session is None:
            raise OSError("Session query failed")
        return owner_session

    monkeypatch.setattr(windows_process_security, "process_session_id", session_id)
    assert not terminate_verified_process(
        ProcessIdentity(4401, 123.0),
        scope=ExactExecutableProcessScope((executable,)),
    )
    assert not process.terminated
    assert not process.killed


def test_recovery_refuses_copied_image_running_for_another_installation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Matching PID and owned executable cannot override a different request root."""
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    process = _Process(
        layout.root / ".repair/helper/1.2.3/session-owned/bundle/SugarSubstitute.exe",
        arguments=(
            f"--execute-repair-request={tmp_path / 'other' / '.repair' / 'prepared.json'}",
        ),
    )
    _bind_process(monkeypatch, process)
    assert not terminate_verified_process(
        ProcessIdentity(4401, 123.0), scope=InstalledInvocationScope(layout)
    )
    assert not process.terminated
    assert not process.killed


def test_recovery_refuses_reused_pid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A new process with the same executable and PID must remain untouched."""
    process = _Process(tmp_path / "SugarSubstitute.exe")
    _bind_process(monkeypatch, process)
    assert not terminate_verified_process(
        ProcessIdentity(pid=4401, created_at=122.0),
        scope=ExactExecutableProcessScope((tmp_path / "SugarSubstitute.exe",)),
    )
    assert not process.terminated
    assert not process.killed


def test_recovery_refuses_same_pid_with_different_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A matching endpoint PID is insufficient without executable identity."""

    process = _Process(tmp_path / "unrelated.exe")
    _bind_process(monkeypatch, process)

    assert not terminate_verified_process(
        ProcessIdentity(pid=4401, created_at=123.0),
        scope=ExactExecutableProcessScope((tmp_path / "SugarSubstitute.exe",)),
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
    _bind_process(monkeypatch, process)

    assert terminate_verified_process(
        ProcessIdentity(pid=4401, created_at=123.0),
        scope=ExactExecutableProcessScope((executable,)),
    )
    assert process.terminated
    assert process.killed is hang_on_terminate
    assert process.wait_count == (2 if hang_on_terminate else 1)


@pytest.mark.parametrize(
    "request_kind", ["attempt", "foreign-root", "bad-identity", "other-file"]
)
def test_repair_scope_recognizes_only_owned_attempt_requests(
    tmp_path: Path, request_kind: str
) -> None:
    """Keep a retired attempt recoverable without accepting arbitrary helper work."""
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    image = (
        layout.root / ".repair/helper/1.2.3/session-owned/bundle/SugarSubstitute.exe"
    )
    request = layout.root / ".repair/staging/1.2.3" / ("a" * 32) / "request.json"
    if request_kind == "foreign-root":
        request = tmp_path / "other" / request.relative_to(layout.root)
    elif request_kind == "bad-identity":
        request = layout.root / ".repair/staging/1.2.3/not-an-attempt/request.json"
    elif request_kind == "other-file":
        request = request.with_name("unrelated.json")
    scope = InstalledInvocationScope(layout)
    assert scope.accepts_invocation(
        image, (str(image), f"--execute-repair-request={request}"), layout.root
    ) == (request_kind == "attempt")
