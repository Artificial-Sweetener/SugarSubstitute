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

"""Require hung-instance recovery without a user-operated process workflow."""

from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import (
    application_instance_recovery,
    launcher_ui_supervision,
)
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
    ApplicationInstanceFailureReason,
)
from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_process_identity,
)


@pytest.mark.parametrize(
    "reason",
    [
        ApplicationInstanceFailureReason.UNAVAILABLE,
        ApplicationInstanceFailureReason.OTHER_SESSION,
        ApplicationInstanceFailureReason.SESSION_UNVERIFIED,
    ],
)
def test_launch_recovers_unavailable_owner_without_manual_process_controls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reason: ApplicationInstanceFailureReason,
) -> None:
    """Retire a verified hung owner automatically, preserving other session work."""
    owner = capture_process_identity(os.getpid())
    failure = ApplicationInstanceBrokerError(
        "Activation unavailable",
        owner_identity=owner,
        endpoint=ApplicationInstanceEndpoint("windows-named-pipe", "test-owner"),
        reason=reason,
    )
    elections = 0
    terminated: list[ProcessIdentity] = []
    presentations: list[bool] = []

    def elect(
        layout: InstallLayout, arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Publish a failed activation followed by successful normal election."""
        nonlocal elections
        elections += 1
        if elections == 1:
            raise failure
        return None

    def terminate(identity: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Record automatic retirement at the native process-control boundary."""
        terminated.append(identity)
        return True

    def present(**arguments: object) -> InstanceRecoveryAction:
        """Record whether failure presentation exposes manual process control."""
        presentations.append("can_end_owner" in arguments)
        return InstanceRecoveryAction.EXIT

    monkeypatch.setattr(
        application_instance_recovery, "terminate_verified_process", terminate
    )
    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    ApplicationElectionRecovery(
        layout=InstallLayout.from_root(tmp_path),
        process_arguments=(),
        locale_override="en",
        elect=elect,
    ).run()
    if reason is ApplicationInstanceFailureReason.UNAVAILABLE:
        assert terminated == [owner]
        assert elections == 2
        assert presentations == []
    else:
        assert terminated == []
        assert elections == 1
        assert presentations == [False]
