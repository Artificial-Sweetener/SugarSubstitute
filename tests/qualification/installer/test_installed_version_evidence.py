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

"""Qualify durable installed-version evidence after candidate readiness."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from tools.ci.installed_version_evidence import wait_for_installed_version


def test_version_wait_survives_receipt_before_activation_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shell receipt may arrive immediately before durable state is committed."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    version_path = layout.app_dir / "substitute" / "_version.py"
    version_path.parent.mkdir(parents=True)
    version_path.write_text('__version__ = "2.0.0"\n', encoding="utf-8")
    LauncherUpdateState(installed_app_version="1.0.0").save(layout.state_path)

    def commit_during_wait(_seconds: float) -> None:
        """Model the supervisor committing after the app publishes readiness."""

        LauncherUpdateState(installed_app_version="2.0.0").save(layout.state_path)

    monkeypatch.setattr(
        "tools.ci.installed_version_evidence.time.sleep",
        commit_during_wait,
    )

    wait_for_installed_version(
        install_root=layout.root,
        expected_version="2.0.0",
        timeout_seconds=1.0,
    )
