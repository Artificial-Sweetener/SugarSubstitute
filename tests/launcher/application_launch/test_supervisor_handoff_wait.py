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

"""Verify visible, identity-bound setup-supervisor handoff waiting."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import supervisor_handoff_wait
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_session import LauncherSplashSession
from sugarsubstitute_shared import process_identity
from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared.supervisor_handoff import with_supervisor_handoff


@pytest.mark.parametrize("splash_available", [True, False])
def test_handoff_waits_for_exact_supervisor_even_without_splash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    splash_available: bool,
) -> None:
    """Attempt presentation without making it a requirement for safe handoff."""

    identity = ProcessIdentity(pid=4321, created_at=123.5)
    environment = with_supervisor_handoff({"BASE": "preserved"}, identity)
    events: list[object] = []
    splash = object.__new__(LauncherSplashSession) if splash_available else None

    def start_splash(**_kwargs: object) -> LauncherSplashSession | None:
        """Record surface creation before returning the retained session."""

        events.append("splash")
        return splash

    def wait_for_exit(
        observed: ProcessIdentity,
        **_options: object,
    ) -> bool:
        """Record the exact identity wait without using a live process."""

        events.append(("wait", observed))
        return True

    monkeypatch.setattr(
        supervisor_handoff_wait,
        "start_launcher_splash_session",
        start_splash,
    )
    monkeypatch.setattr(
        process_identity,
        "wait_for_process_exit",
        wait_for_exit,
    )

    result = supervisor_handoff_wait.wait_for_outgoing_supervisor(
        layout=InstallLayout.from_root(tmp_path / "install"),
        locale_override="en",
        environment=environment,
    )

    assert result is splash
    assert events == [
        "splash",
        ("wait", identity),
    ]
    assert environment == {"BASE": "preserved"}
