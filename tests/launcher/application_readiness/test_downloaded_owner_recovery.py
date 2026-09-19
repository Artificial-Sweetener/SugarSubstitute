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

"""Require native endpoint ownership to recover a downloaded setup supervisor."""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import socket
import sys

import psutil  # type: ignore[import-untyped]
import pytest

from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared import application_instance_forwarding
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from tests.launcher.application_readiness.process_family_fixture import command


@pytest.mark.platforms("windows")
def test_packaged_launch_recovers_native_owner_outside_installed_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recover the real frozen endpoint owner without a path-derived rejection UI."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        family, _log = spawn_supervised_process(
            command("broker", listener.getsockname()[1], tmp_path),
            startup_log_path=tmp_path / "broker.log",
        )
        replacement: ApplicationInstanceBroker | None = None
        try:
            connection, _address = listener.accept()
            with connection, connection.makefile("rb") as response:
                connection.settimeout(5)
                owner_pid = int(json.loads(response.read())["pid"])
            parent = psutil.Process(family.pid)
            members = {child.pid: child for child in parent.children(recursive=True)}
            members[parent.pid] = parent
            assert owner_pid in members
            owner = members[owner_pid]
            assert not Path(owner.exe()).is_relative_to(tmp_path)
            owner.suspend()
            monkeypatch.setattr(sys, "frozen", True, raising=False)
            monkeypatch.setattr(
                application_instance_forwarding, "_PRESENTATION_TIMEOUT_SECONDS", 0.1
            )

            def reject_manual_recovery(**_arguments: object) -> None:
                """Reject a user-facing recovery workflow for a proven native owner."""
                pytest.fail("Native endpoint owner required manual recovery")

            def elect(
                layout: InstallLayout, arguments: Sequence[str]
            ) -> ApplicationInstanceBroker | None:
                """Exercise native election and forwarding through production transport."""
                return ApplicationInstanceBroker.elect(
                    install_root=layout.root,
                    invocation=ApplicationInvocation.capture(arguments),
                )

            monkeypatch.setattr(
                launcher_ui_supervision,
                "supervise_instance_recovery_window",
                reject_manual_recovery,
            )
            replacement = ApplicationElectionRecovery(
                layout=InstallLayout.from_root(tmp_path),
                process_arguments=("SugarSubstitute",),
                locale_override="en",
                elect=elect,
            ).run()
            assert replacement is not None
            family.wait(timeout=5)
            assert not owner.is_running()
        finally:
            if replacement is not None:
                replacement.close()
            family.kill()
            family.wait(timeout=5)


@pytest.mark.parametrize("matching_endpoint", [False, True])
def test_downloaded_owner_authority_is_limited_to_requested_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, matching_endpoint: bool
) -> None:
    """Use a captured native image only for the installation being elected."""
    from launcher.sugarsubstitute_launcher import application_instance_recovery
    from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
        InstanceRecoveryAction,
    )
    from sugarsubstitute_shared.application_instance_election import (
        application_instance_endpoints,
    )
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInstanceBrokerError,
        NativeApplicationInstanceOwner,
    )
    from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope
    from sugarsubstitute_shared.process_identity import ProcessIdentity

    root = tmp_path / "install"
    endpoint = application_instance_endpoints(
        root if matching_endpoint else tmp_path / "other"
    )[0]
    identity = ProcessIdentity(1001, 1)
    executable = tmp_path / "downloaded" / "setup.exe"
    proof = NativeApplicationInstanceOwner(endpoint, identity, executable)
    failure = ApplicationInstanceBrokerError(
        "frozen owner", owner_identity=identity, endpoint=endpoint, native_owner=proof
    )
    observations: list[bool] = []
    elections = 0

    def elect(
        layout: InstallLayout, arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Offer one frozen-owner result before the successful replacement election."""
        nonlocal elections
        elections += 1
        if elections == 1:
            raise failure
        return None

    def terminate(owner: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Observe admission policy without terminating any real process."""
        assert owner == identity
        accepted = scope.accepts_executable(executable)
        observations.append(accepted)
        return accepted

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        application_instance_recovery, "terminate_verified_process", terminate
    )
    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_instance_recovery_window",
        lambda **_arguments: InstanceRecoveryAction.EXIT,
    )
    ApplicationElectionRecovery(
        layout=InstallLayout.from_root(root),
        process_arguments=(),
        locale_override="en",
        elect=elect,
    ).run()
    assert observations == [matching_endpoint]
    assert elections == (2 if matching_endpoint else 1)
