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
    enter_installed_application_launch,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_launch_guard import (
    APPLICATION_LAUNCH_TOKEN_ENV,
)


def test_shortcut_launch_allows_only_one_launcher_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A second shortcut invocation must stop before app or splash startup."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    monkeypatch.setenv(APPLICATION_LAUNCH_TOKEN_ENV, "inherited-poison-token")

    first_launch = enter_installed_application_launch(layout)

    assert first_launch is not None
    assert enter_installed_application_launch(layout) is None
    assert (
        first_launch.initial_handoff_environment()[APPLICATION_LAUNCH_TOKEN_ENV]
        != "inherited-poison-token"
    )

    first_launch.release()
