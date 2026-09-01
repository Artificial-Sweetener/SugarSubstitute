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

"""Verify launcher-owned operation-specific splash activity copy."""

from __future__ import annotations

import pytest

from launcher.sugarsubstitute_launcher.update_activity import (
    application_dependencies_activity,
    application_install_activity,
    launcher_update_activity,
)
from sugarsubstitute_shared.launch_splash import SplashActivity


@pytest.mark.parametrize(
    ("activity", "operation"),
    (
        (application_install_activity("0.4.0"), "SugarSubstitute 0.4.0"),
        (application_dependencies_activity(), "SugarSubstitute dependencies"),
        (launcher_update_activity("0.4.0"), "SugarSubstitute launcher"),
    ),
)
def test_launcher_activity_names_operation_at_every_wait_stage(
    activity: SplashActivity,
    operation: str,
) -> None:
    """Keep each install or update identifiable after every time transition."""

    assert operation in activity.initial_text
    assert operation in activity.long_wait_text
    assert operation in activity.extended_wait_text
    assert "taking longer than usual" in activity.long_wait_text
    assert "delay" in activity.extended_wait_text
    assert not activity.initial_text.endswith(".")
    assert not activity.long_wait_text.endswith(".")
    assert not activity.extended_wait_text.endswith(".")
