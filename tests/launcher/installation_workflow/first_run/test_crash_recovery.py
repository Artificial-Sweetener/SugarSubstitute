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

"""Require continuation to recover one coherent application/configuration version."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from launcher.sugarsubstitute_launcher.startup_plan import (
    LauncherStartupCandidate,
    is_installed_app_launchable,
)
from launcher.sugarsubstitute_launcher.startup_recovery import recover_startup_candidate
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from tests.launcher.installation_workflow.first_run.support import (
    write_manifest,
    write_valid_payload_zip,
)


@pytest.mark.parametrize(
    "boundary",
    [
        "app_retired",
        "app_promoted",
        "config_written",
        "config_partial",
        "state_written",
    ],
)
def test_startup_recovers_interrupted_continuation(
    tmp_path: Path, boundary: str
) -> None:
    """Recover prior content before commitment and complete publication afterward."""
    release = tmp_path / "release"
    payload = write_valid_payload_zip(release / "app.zip")
    write_manifest(release / "manifest.json", app_zip=payload)
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.create_base_directories()
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_bytes(b"previous application")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_bytes(b"previous runtime")
    LauncherConfig.from_layout(layout=layout, channel="preview").save(
        layout.config_path
    )
    LauncherUpdateState(installed_app_version="0.1.0").save(layout.state_path)
    old_config = layout.config_path.read_bytes()
    old_state = layout.state_path.read_bytes()
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.installation_workflow.first_run.interruption_process",
            str(layout.root),
            str(release),
            boundary,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert child.returncode == 73, child.stderr
    assert InstallationRecovery(layout).pending
    recovered = recover_startup_candidate(LauncherStartupCandidate(layout, True))
    assert is_installed_app_launchable(recovered.layout)
    assert not InstallationRecovery(layout).pending
    assert layout.runtime_python.read_bytes() == b"previous runtime"
    if boundary.startswith("app_"):
        assert layout.app_entrypoint.read_bytes() == b"previous application"
        assert layout.config_path.read_bytes() == old_config
        assert layout.state_path.read_bytes() == old_state
    else:
        assert layout.app_entrypoint.read_bytes() != b"previous application"
        assert LauncherConfig.load(layout.config_path).channel == "stable"
        assert (
            LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"
        )
