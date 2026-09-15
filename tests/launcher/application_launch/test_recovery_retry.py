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

"""Preserve verified recovery authority across failed launch retries."""

from __future__ import annotations

from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope

from collections.abc import Sequence
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher import application_instance_recovery
from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity


@pytest.mark.parametrize(
    ("second_endpoint", "second_identity", "expected_identity"),
    [
        (
            ApplicationInstanceEndpoint("windows-named-pipe", "test-owner"),
            None,
            ProcessIdentity(123, 456.0),
        ),
        (
            ApplicationInstanceEndpoint("windows-named-pipe", "different-owner"),
            None,
            None,
        ),
        (None, None, None),
        (
            ApplicationInstanceEndpoint("windows-named-pipe", "test-owner"),
            ProcessIdentity(124, 789.0),
            ProcessIdentity(124, 789.0),
        ),
        (
            ApplicationInstanceEndpoint("windows-named-pipe", "test-owner"),
            ProcessIdentity(123, 789.0),
            ProcessIdentity(123, 789.0),
        ),
    ],
    ids=[
        "busy-same-endpoint",
        "different-endpoint",
        "unknown-endpoint",
        "replacement-owner",
        "reused-pid",
    ],
)
def test_retry_preserves_only_the_matching_verified_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    second_endpoint: ApplicationInstanceEndpoint | None,
    second_identity: ProcessIdentity | None,
    expected_identity: ProcessIdentity | None,
) -> None:
    """Keep End and retry usable after a frozen owner's pipe queue fills."""
    endpoint = ApplicationInstanceEndpoint("windows-named-pipe", "test-owner")
    identity = ProcessIdentity(123, 456.0)
    failures = iter(
        (
            ApplicationInstanceBrokerError(
                "timed out", endpoint=endpoint, owner_identity=identity
            ),
            ApplicationInstanceBrokerError(
                "pipe busy", endpoint=second_endpoint, owner_identity=second_identity
            ),
        )
    )
    actions = iter((InstanceRecoveryAction.RETRY, InstanceRecoveryAction.END_AND_RETRY))
    eligibility: list[bool] = []
    terminated: list[ProcessIdentity | None] = []

    def elect(
        _layout: InstallLayout, _arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Model a verified timeout followed by a saturated transport."""
        error = next(failures, None)
        if error is not None:
            raise error
        return None

    def present(**kwargs: object) -> InstanceRecoveryAction:
        """Record whether the actual recovery flow offers termination."""
        eligibility.append(bool(kwargs["can_end_owner"]))
        return next(actions)

    def terminate(identity: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Record the proof passed across the process termination boundary."""
        terminated.append(identity)
        return True

    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    monkeypatch.setattr(
        application_instance_recovery, "terminate_verified_process", terminate
    )
    ApplicationElectionRecovery(
        layout=InstallLayout.from_root(tmp_path),
        process_arguments=("Substitute",),
        locale_override="en",
        elect=elect,
    ).run()
    assert eligibility == [True, expected_identity is not None]
    assert terminated == ([] if expected_identity is None else [expected_identity])


@pytest.mark.parametrize("terminated_successfully", [True, False])
def test_termination_releases_proof_only_after_verified_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    terminated_successfully: bool,
) -> None:
    """Keep failed termination recoverable and discard proof after owner retirement."""
    endpoint = ApplicationInstanceEndpoint("windows-named-pipe", "test-owner")
    failures = iter(
        (
            ApplicationInstanceBrokerError(
                "hung", endpoint=endpoint, owner_identity=ProcessIdentity(123, 456.0)
            ),
            ApplicationInstanceBrokerError("busy", endpoint=endpoint),
        )
    )
    actions = iter((InstanceRecoveryAction.END_AND_RETRY, InstanceRecoveryAction.EXIT))
    eligibility: list[bool] = []

    def elect(
        _layout: InstallLayout, _arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Present a subsequent failure after the termination outcome."""
        raise next(failures)

    def present(**kwargs: object) -> InstanceRecoveryAction:
        """Observe recovery availability until the user exits."""
        eligibility.append(bool(kwargs["can_end_owner"]))
        return next(actions)

    def terminate(identity: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Return the controlled OS termination result."""
        return terminated_successfully

    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", present
    )
    monkeypatch.setattr(
        application_instance_recovery, "terminate_verified_process", terminate
    )
    ApplicationElectionRecovery(
        layout=InstallLayout.from_root(tmp_path),
        process_arguments=("Substitute",),
        locale_override="en",
        elect=elect,
    ).run()
    assert eligibility == [True, not terminated_successfully]
