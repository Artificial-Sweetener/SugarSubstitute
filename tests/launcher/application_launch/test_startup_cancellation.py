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

"""Verify explicit cancellation exits the installed launcher without repair."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher import (
    app,
    application_launch,
    installed_app_handoff,
    launcher_ui_supervision,
    splash_session,
    startup_recovery,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    InstallationStartupDeferred,
    ApplicationStartupCancelled,
)

from tests.launcher.application_launch.instance_routing_support import (
    BrokerDouble,
    installed_layout,
)


@pytest.mark.parametrize(
    "source,deferred",
    [
        ("handoff", False),
        ("recovery", False),
        ("splash", False),
        ("handoff", True),
        ("recovery", True),
    ],
)
def test_stopped_installed_startup_closes_splash_and_broker_without_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: str,
    deferred: bool,
) -> None:
    """Respect user cancellation even though the application never became ready."""
    layout = installed_layout(tmp_path)
    broker = BrokerDouble()
    closed: list[bool] = []

    class Splash:
        """Expose only the launcher-owned surface lifecycle boundary."""

        def present(self) -> str:
            """Keep startup presentation available before cancellation."""
            return "startup-splash"

        def close(self) -> None:
            """Record release of the launcher's visible helper."""
            closed.append(True)

        def cancellation_requested(self) -> bool:
            """Leave the separate handoff cancellation as the test's trigger."""
            return False

    def cancelled(*args: object, **kwargs: object) -> None:
        """Report explicit cancellation after the handoff retires its child."""
        raise (
            InstallationStartupDeferred() if deferred else ApplicationStartupCancelled()
        )

    monkeypatch.setattr(sys, "executable", str(layout.executable_path))
    monkeypatch.setattr(application_launch, "elect_application", lambda *_args: broker)
    monkeypatch.setattr(
        splash_session, "start_launcher_splash_session", lambda **_kwargs: Splash()
    )
    if source == "handoff":
        monkeypatch.setattr(
            installed_app_handoff, "complete_installed_app_handoff", cancelled
        )
    elif source == "recovery":
        monkeypatch.setattr(startup_recovery, "recover_startup_candidate", cancelled)
    else:
        monkeypatch.setattr(splash_session, "start_launcher_splash_session", cancelled)
    monkeypatch.setattr(
        launcher_ui_supervision,
        "supervise_launcher_window",
        lambda **_kwargs: pytest.fail("Cancellation must not open repair"),
    )
    assert app.main([]) == 0
    assert broker.closed
    assert closed == ([] if source == "splash" else [True])
