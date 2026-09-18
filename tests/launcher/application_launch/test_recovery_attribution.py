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

"""Preserve replacement owners when discovery outlives a failed admission attempt."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import (
    application_instance_recovery,
    application_process_discovery,
    launcher_ui_supervision,
    selected_installation_admission,
)
from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_election import (
    ApplicationInstanceReservation,
    application_instance_endpoints,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
)
from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope
from sugarsubstitute_shared.process_identity import ProcessIdentity


@pytest.mark.parametrize("admission", ["launch", "selected-folder"])
@pytest.mark.parametrize(
    ("had_previous_owner", "has_replacement"),
    [(False, True), (True, True), (True, False)],
)
def test_changed_owner_invalidates_unattributed_admission_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    had_previous_owner: bool,
    has_replacement: bool,
    admission: str,
) -> None:
    """Repeat admission instead of terminating a replacement for an earlier failure."""
    layout = InstallLayout.from_root(tmp_path)
    earlier = ProcessIdentity(1001, 1.0)
    replacement = ProcessIdentity(1002, 2.0)
    visible_owner = earlier if had_previous_owner else None
    attempts = 0
    retired: list[ProcessIdentity] = []

    def discover(
        target: InstallLayout, endpoint: ApplicationInstanceEndpoint | None
    ) -> ProcessIdentity | None:
        """Expose the actual owner at each externally synchronized phase."""
        assert target == layout
        assert endpoint in application_instance_endpoints(layout.root)
        return visible_owner

    def elect(
        target: InstallLayout, arguments: Sequence[str]
    ) -> ApplicationInstanceBroker | None:
        """Publish another launch's successful replacement before reporting timeout."""
        nonlocal attempts, visible_owner
        attempts += 1
        if attempts == 1:
            visible_owner = replacement if has_replacement else None
            raise ApplicationInstanceBrokerError(
                "Earlier connection timed out",
                endpoint=application_instance_endpoints(target.root)[0],
            )
        return None

    def terminate(identity: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Record destructive actions without touching an actual process."""
        retired.append(identity)
        return True

    def reject_ui(**kwargs: object) -> None:
        """A healthy replacement must accept the launch without recovery prompts."""
        pytest.fail("Changed ownership produced recovery UI")

    monkeypatch.setattr(
        application_process_discovery, "discover_previous_installed_instance", discover
    )
    monkeypatch.setattr(
        application_instance_recovery, "terminate_verified_process", terminate
    )
    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", reject_ui
    )
    if admission == "launch":
        assert (
            ApplicationElectionRecovery(
                layout=layout, process_arguments=(), locale_override=None, elect=elect
            ).run()
            is None
        )
    else:

        def reserve(
            root: Path, invocation: ApplicationInvocation
        ) -> ApplicationInstanceReservation | None:
            """Exercise the same failure transition through selected-folder admission."""
            assert elect(InstallLayout.from_root(root), invocation.arguments) is None
            return None

        monkeypatch.setattr(
            selected_installation_admission, "reserve_application_instance", reserve
        )
        assert (
            selected_installation_admission.reserve_selected_installation(
                layout.root, ApplicationInvocation.capture(()), lambda: None
            )
            is None
        )
    assert attempts == 2
    assert retired == []
