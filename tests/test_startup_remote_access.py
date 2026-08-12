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

"""Tests for the launch-scoped sticky remote-access decision."""

from __future__ import annotations

from sugarsubstitute_shared.startup_remote_access import (
    STARTUP_REMOTE_DEGRADED_ENV,
    StartupRemoteAccess,
)


def test_remote_access_preserves_first_failure_for_the_launch() -> None:
    """Later outcomes must not replace or clear the first degradation."""

    remote_access = StartupRemoteAccess()

    remote_access.degrade(reason="manifest")
    remote_access.degrade(reason="nodepacks")

    assert remote_access.allows_remote_work is False
    assert remote_access.degradation_reason == "manifest"
    assert remote_access.child_environment({}) == {STARTUP_REMOTE_DEGRADED_ENV: "1"}


def test_available_launch_clears_inherited_degradation() -> None:
    """A fresh launcher decision must reset degradation from an older process."""

    remote_access = StartupRemoteAccess()

    assert remote_access.child_environment(
        {STARTUP_REMOTE_DEGRADED_ENV: "1", "PATH": "runtime"}
    ) == {"PATH": "runtime"}
