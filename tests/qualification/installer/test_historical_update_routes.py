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

"""Qualify migration routing for immutable historical launcher generations."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import cast

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.ci.historical_update_qualification import (
    HistoricalUpdateQualification,
    HistoricalUpdateRoute,
    historical_update_route,
    qualify_historical_update,
)
from tools.ci.loopback_port_lease import LoopbackPortLease


@pytest.mark.parametrize(
    ("platform", "version", "expected_route"),
    [
        ("win32", "0.12.2", HistoricalUpdateRoute.AUTOMATIC_LAUNCHER_UPDATE),
        (
            "linux",
            "0.20.1",
            HistoricalUpdateRoute.CANDIDATE_INSTALLER_MIGRATION,
        ),
        (
            "darwin",
            "0.12.2",
            HistoricalUpdateRoute.CANDIDATE_INSTALLER_MIGRATION,
        ),
        ("linux", "0.21.1", HistoricalUpdateRoute.AUTOMATIC_LAUNCHER_UPDATE),
        ("darwin", "0.21.2", HistoricalUpdateRoute.AUTOMATIC_LAUNCHER_UPDATE),
    ],
)
def test_historical_update_route_preserves_automatic_update_coverage(
    platform: str,
    version: str,
    expected_route: HistoricalUpdateRoute,
) -> None:
    """Only published POSIX launchers predating routing repair need migration."""

    assert (
        historical_update_route(
            historical_version=version,
            platform=platform,
        )
        is expected_route
    )


def test_legacy_posix_route_runs_exact_candidate_installer_before_launch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Broken immutable POSIX launchers should migrate without masking newer ones."""

    install_root = tmp_path / "installed"
    layout = InstallLayout.from_root(install_root)
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    candidate_installer = tmp_path / "candidate.AppImage"
    candidate_installer.write_bytes(b"candidate")
    events: list[object] = []

    def run_installer(
        command: list[str],
        **arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        """Record the exact migration command and its bounded environment."""

        events.append(("installer", command, arguments))
        return subprocess.CompletedProcess(command, 0, "installed", "")

    def launch_candidate(**_arguments: object) -> object:
        """Record launch of the newly installed candidate launcher."""

        events.append("launch")
        return object()

    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.sys.platform",
        "linux",
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.run_owned_process",
        run_installer,
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification."
        "assert_historical_installed_launch_contract",
        lambda *_args, **_kwargs: pytest.fail(
            "A launcher with the published POSIX routing defect cannot auto-update."
        ),
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.launch_installed_candidate",
        launch_candidate,
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification._verify_candidate_evidence",
        lambda **_arguments: events.append("verify"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.assert_installed_release_channel",
        lambda **_arguments: events.append("channel"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.terminate_owned_managed_comfy",
        lambda _install_root: events.append("cleanup"),
    )

    with LoopbackPortLease.acquire() as endpoint_lease:
        route = qualify_historical_update(
            HistoricalUpdateQualification(
                install_root=install_root,
                historical_version="0.20.1",
                candidate_version="9999.0.109",
                candidate_channel="stable",
                candidate_manifest_url="https://example.test/candidate.json",
                candidate_release_root=None,
                candidate_installer_path=candidate_installer,
                expected_update_manifest_url=None,
                managed_workspace=install_root / "comfyui",
                managed_model_root=install_root / "qualified-models",
                preservation_marker=install_root / "user" / "settings" / "marker.json",
                timeout_seconds=30.0,
            ),
            endpoint_lease=endpoint_lease,
        )

    assert route is HistoricalUpdateRoute.CANDIDATE_INSTALLER_MIGRATION
    installer_event = cast(tuple[str, list[str], dict[str, object]], events[0])
    assert installer_event[0] == "installer"
    assert installer_event[1] == [
        str(candidate_installer.resolve()),
        "--headless-install",
        f"--install-root={install_root.resolve()}",
        "--manifest-url=https://example.test/candidate.json",
    ]
    assert events[1:] == ["launch", "verify", "channel", "cleanup"]
