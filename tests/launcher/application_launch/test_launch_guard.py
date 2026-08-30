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

"""Verify non-Qt shortcut launch ownership."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application_launch import (
    begin_installed_application_launch,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_launch_guard import (
    APPLICATION_LAUNCH_TOKEN_ENV,
    ApplicationLaunchGuard,
)


def test_shortcut_launch_allows_only_one_launcher_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A second shortcut invocation must stop before app or splash startup."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    monkeypatch.setenv(APPLICATION_LAUNCH_TOKEN_ENV, "inherited-poison-token")

    first_session = begin_installed_application_launch(layout)
    second_session = begin_installed_application_launch(layout)

    assert first_session is not None
    assert second_session is None
    first_guard = first_session.claim_application()
    assert first_guard is not None
    assert (
        first_guard.initial_handoff_environment()[APPLICATION_LAUNCH_TOKEN_ENV]
        != "inherited-poison-token"
    )

    first_guard.release()
    first_session.release()
    replacement_session = begin_installed_application_launch(layout)
    assert replacement_session is not None
    replacement_session.release()


def test_shortcut_launch_distinguishes_a_running_application_from_launcher_work(
    tmp_path: Path,
) -> None:
    """Only a live application lease should enter active-instance negotiation."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    application = ApplicationLaunchGuard.enter(layout.root)
    assert application is not None
    session = begin_installed_application_launch(layout)
    assert session is not None

    try:
        assert session.claim_application() is None
    finally:
        session.release()
        application.release()


def test_launcher_session_recovers_a_legacy_live_pid_record_without_native_owner(
    tmp_path: Path,
) -> None:
    """Native leases should prove a PID-reused launch record is abandoned."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    legacy_guard = ApplicationLaunchGuard.enter(
        layout.root,
        allow_initial_handoff=True,
        acquire_instance_lease=False,
    )
    assert legacy_guard is not None
    session = begin_installed_application_launch(layout)
    assert session is not None

    try:
        recovered_guard = session.claim_application()
        assert recovered_guard is not None
        recovered_guard.release()
    finally:
        session.release()
        legacy_guard.release()
