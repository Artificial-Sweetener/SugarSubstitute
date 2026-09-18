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

"""Require first-run entrypoints to respect another installation writer."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.release_sources import LocalFolderReleaseSource
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationBusyError,
    installation_mutation,
)
from tests.launcher.installation_workflow.first_run.support import (
    write_manifest,
    write_valid_launcher_bundle_zip,
    write_valid_payload_zip,
)


@pytest.mark.parametrize(
    "downloaded",
    [False, pytest.param(True, marks=pytest.mark.platforms("windows"))],
)
def test_first_run_preserves_owned_installation_and_retries_after_release(
    tmp_path: Path, downloaded: bool
) -> None:
    """Reject before changing existing state, then succeed after the writer exits."""
    release_root = tmp_path / "release"
    app_zip = write_valid_payload_zip(release_root / "app.zip")
    launcher_zip = write_valid_launcher_bundle_zip(release_root / "launcher.zip")
    write_manifest(
        release_root / "manifest.json", app_zip=app_zip, launcher_zip=launcher_zip
    )
    source = LocalFolderReleaseSource(release_root)
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.create_base_directories()
    LauncherConfig.from_layout(layout=layout, channel="preview").save(
        layout.config_path
    )
    LauncherUpdateState(installed_app_version="0.1.0").save(layout.state_path)
    originals = {
        layout.config_path: layout.config_path.read_bytes(),
        layout.state_path: layout.state_path.read_bytes(),
        layout.app_entrypoint: b"existing application",
    }
    for path, contents in originals.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    installer = FirstRunInstaller()

    def install() -> None:
        """Exercise the production entrypoint without launching a process."""
        if downloaded:
            installer.install_downloaded_launcher(
                install_root=layout.root,
                release_source=source,
                launch_installed=False,
            )
        else:
            installer.continue_install(layout=layout, release_source=source)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with installation_mutation(layout.root):
            with pytest.raises(InstallationMutationBusyError):
                pool.submit(install).result(timeout=30)
            assert {path: path.read_bytes() for path in originals} == originals
        pool.submit(install).result(timeout=30)
    assert layout.config_path.read_bytes() != originals[layout.config_path]
    if not downloaded:
        assert layout.app_entrypoint.read_bytes() != originals[layout.app_entrypoint]


def test_continuation_recovers_interrupted_update_before_installing(
    tmp_path: Path,
) -> None:
    """Retire earlier rollback intent before publishing a new installed payload."""
    release_root = tmp_path / "release"
    app_zip = write_valid_payload_zip(release_root / "app.zip")
    write_manifest(release_root / "manifest.json", app_zip=app_zip)
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.create_base_directories()
    layout.app_entrypoint.parent.mkdir(parents=True, exist_ok=True)
    layout.app_entrypoint.write_bytes(b"previous application")
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_bytes(b"previous runtime")
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.launcher.update_activation.ownership_process",
            str(layout.root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    assert child.returncode == 73, child.stderr
    assert not layout.runtime_python.exists()
    assert InstallationRecovery(layout).pending

    result = FirstRunInstaller().continue_install(
        layout=layout, release_source=LocalFolderReleaseSource(release_root)
    )

    assert result.app_version == "0.4.0"
    assert layout.runtime_python.read_bytes() == b"previous runtime"
    installed_app = layout.app_entrypoint.read_bytes()
    assert installed_app != b"previous application"
    assert not InstallationRecovery(layout).pending
    assert not InstallationRecovery(layout).recover()
    assert layout.app_entrypoint.read_bytes() == installed_app
