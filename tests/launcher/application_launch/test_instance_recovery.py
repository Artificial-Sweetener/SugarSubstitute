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
from collections.abc import Sequence
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
from sugarsubstitute_shared.application_instance_transport import (
    instance_endpoint,
    instance_identity,
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
        if self._hang_on_terminate and self.wait_count == 1:
            raise psutil.TimeoutExpired(timeout, pid=4401)


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
    monkeypatch.setattr(psutil, "Process", lambda _pid: process)
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
        """Choose the actual recovery action offered by the application."""
        assert kwargs["can_end_owner"]
        return InstanceRecoveryAction.END_AND_RETRY

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
    monkeypatch.setattr(psutil, "Process", lambda _pid: process)
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
    monkeypatch.setattr(psutil, "Process", lambda _pid: process)
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
    monkeypatch.setattr(
        psutil,
        "Process",
        lambda _pid: process,
    )

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
    monkeypatch.setattr(
        psutil,
        "Process",
        lambda _pid: process,
    )

    assert terminate_verified_process(
        ProcessIdentity(pid=4401, created_at=123.0),
        scope=ExactExecutableProcessScope((executable,)),
    )
    assert process.terminated
    assert process.killed is hang_on_terminate
    assert process.wait_count == (2 if hang_on_terminate else 1)
