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

"""Keep an exited session owner from blocking an otherwise valid launch."""

from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher import launcher_ui_supervision
from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
    ApplicationInstanceFailureReason,
)
from sugarsubstitute_shared.process_identity import capture_process_identity


@pytest.mark.parametrize(
    "reason",
    [
        ApplicationInstanceFailureReason.SESSION_UNVERIFIED,
        ApplicationInstanceFailureReason.OTHER_SESSION,
    ],
)
def test_departed_owner_reenters_election_without_session_failure_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: ApplicationInstanceFailureReason,
) -> None:
    """Exercise native exit observation and replace only election and UI boundaries."""
    with subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    ) as process:
        identity = capture_process_identity(process.pid)
        process.communicate(b"x", timeout=10)
        assert process.returncode == 0
        elections = 0

        def elect(
            layout: InstallLayout, arguments: Sequence[str]
        ) -> ApplicationInstanceBroker | None:
            """Surface session evidence obtained just before the real owner exited."""
            nonlocal elections
            elections += 1
            if elections == 1:
                raise ApplicationInstanceBrokerError(
                    "Session observation crossed owner shutdown",
                    owner_identity=identity,
                    endpoint=ApplicationInstanceEndpoint("windows-named-pipe", "test"),
                    reason=reason,
                )
            return None

        def unexpected_dialog(**arguments: object) -> None:
            """Reject a recovery workflow for a process that no longer owns anything."""
            pytest.fail("Departed owner caused user-facing session recovery")

        monkeypatch.setattr(
            launcher_ui_supervision,
            "supervise_instance_recovery_window",
            unexpected_dialog,
        )
        ApplicationElectionRecovery(
            layout=InstallLayout.from_root(tmp_path),
            process_arguments=(),
            locale_override="en",
            elect=elect,
        ).run()
        assert elections == 2
