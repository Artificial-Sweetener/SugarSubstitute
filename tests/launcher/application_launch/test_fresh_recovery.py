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

"""Require installed recovery to work without a successful pipe connection."""

from __future__ import annotations

from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope

from collections.abc import Sequence
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher import application_instance_recovery
from sugarsubstitute_shared import windows_application_processes
from sugarsubstitute_shared.process_identity import ProcessIdentity
from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
)
from sugarsubstitute_shared.application_instance_transport import instance_identity
from sugarsubstitute_shared.application_instance_transport import (
    instance_endpoint,
)


@pytest.mark.platforms("windows")
def test_fresh_packaged_recovery_inspects_os_identity_when_pipe_is_busy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reach independent process discovery before offering recovery for a busy pipe."""
    layout = InstallLayout.from_root(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    offered: list[bool] = []

    def elect(
        _layout: InstallLayout, _arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Reproduce an owner whose pipe cannot accept this launch at all."""
        raise ApplicationInstanceBrokerError(
            "Pipe busy",
            endpoint=instance_endpoint(instance_identity(layout.root)),
        )

    def present(**kwargs: object) -> InstanceRecoveryAction:
        """End this attempt after observing the recovery decision."""
        offered.append("can_end_owner" in kwargs)
        return InstanceRecoveryAction.EXIT

    # A packaged identity must be checked against the real executable before discovery.
    # The source test process cannot qualify as the installed launcher.
    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    ApplicationElectionRecovery(
        layout=layout, process_arguments=(), locale_override="en", elect=elect
    ).run()
    assert offered == [False]


@pytest.mark.platforms("windows")
def test_fresh_recovery_automatically_retires_the_independently_verified_instance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Recover a saturated pipe even though this invocation never connected to it."""
    layout = InstallLayout.from_root(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    identity = ProcessIdentity(4401, 123.0)
    discovered: list[Path] = []
    ended: list[ProcessIdentity] = []
    offered: list[bool] = []
    failures = iter(
        [
            ApplicationInstanceBrokerError(
                "busy",
                endpoint=instance_endpoint(instance_identity(layout.root)),
            )
        ]
    )

    def discover(
        scope: ApplicationProcessScope,
    ) -> ProcessIdentity:
        """Supply an independently verified OS process identity."""
        executable = layout.executable_path
        assert scope.accepts_executable(executable)
        discovered.append(executable)
        assert scope.accepts_invocation(executable, [str(executable)], layout.root)
        assert not scope.accepts_invocation(
            executable,
            [str(executable), "--install-root", str(layout.root / "other")],
            layout.root,
        )
        return identity

    def elect(
        _layout: InstallLayout, _arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Allow election after automatic retirement of the earlier process."""
        error = next(failures, None)
        if error is not None:
            raise error
        return None

    def present(**kwargs: object) -> InstanceRecoveryAction:
        """Reject manual recovery for an independently verified unavailable owner."""
        pytest.fail("Verified process required manual recovery")

    def terminate(identity: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Record the exact identity selected for automatic retirement."""
        assert scope.accepts_executable(layout.executable_path)
        ended.append(identity)
        return True

    monkeypatch.setattr(
        windows_application_processes, "find_previous_application_process", discover
    )
    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    monkeypatch.setattr(
        application_instance_recovery,
        "terminate_verified_process",
        terminate,
        raising=False,
    )
    ApplicationElectionRecovery(
        layout=layout, process_arguments=(), locale_override="en", elect=elect
    ).run()
    assert offered == []
    assert discovered == [layout.executable_path]
    assert ended == [identity]


@pytest.mark.platforms("windows")
@pytest.mark.parametrize(
    "scope", ["source", "other-install", "other-endpoint", "unknown-endpoint"]
)
def test_independent_discovery_requires_the_exact_installed_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scope: str,
) -> None:
    """Keep source runs and unrelated election failures outside installed recovery."""
    layout = InstallLayout.from_root(tmp_path)
    monkeypatch.setattr(sys, "frozen", scope != "source", raising=False)
    monkeypatch.setattr(
        sys,
        "executable",
        str(
            tmp_path / "other.exe"
            if scope == "other-install"
            else layout.executable_path
        ),
    )
    endpoint = instance_endpoint(instance_identity(layout.root))
    failure = ApplicationInstanceBrokerError(
        "unavailable",
        endpoint=None
        if scope == "unknown-endpoint"
        else ApplicationInstanceEndpoint("windows-named-pipe", "other")
        if scope == "other-endpoint"
        else endpoint,
    )

    def discover(
        scope: ApplicationProcessScope,
    ) -> ProcessIdentity:
        """Reject any attempt to cross the recovery scope boundary."""
        pytest.fail("Process discovery ran outside the installed endpoint scope")

    def elect(
        _layout: InstallLayout, _arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Raise the selected unqualified election failure."""
        raise failure

    def present(**kwargs: object) -> InstanceRecoveryAction:
        """Verify that an unqualified process cannot be offered for termination."""
        assert "can_end_owner" not in kwargs
        return InstanceRecoveryAction.EXIT

    monkeypatch.setattr(
        windows_application_processes, "find_previous_application_process", discover
    )
    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    ApplicationElectionRecovery(
        layout=layout, process_arguments=(), locale_override="en", elect=elect
    ).run()
