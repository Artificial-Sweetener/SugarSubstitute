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
from types import SimpleNamespace

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.launcher_update.models import LauncherInstallationRecord
from tools.ci.historical_update_qualification import (
    HistoricalUpdateQualification,
    HistoricalUpdateRoute,
    assert_installed_root_launcher_version,
    historical_update_route,
    qualify_historical_update,
)
from tools.ci.historical_launcher_chain_evidence import (
    assert_root_main_shell_acknowledgement,
)
from tools.ci.loopback_port_lease import LoopbackPortLease
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


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
        "tools.ci.historical_update_qualification.assert_installed_root_launcher_version",
        lambda **_arguments: events.append("root"),
    )
    monkeypatch.setattr(
        "tools.ci.historical_update_qualification.assert_candidate_root_readiness",
        lambda **_arguments: events.append("root_ready"),
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
    assert events[1:] == [
        "launch",
        "verify",
        "root",
        "root_ready",
        "channel",
        "cleanup",
    ]


def test_historical_update_rejects_visible_app_under_outdated_root(
    tmp_path: Path,
) -> None:
    """A candidate shell alone cannot qualify an old launcher root."""

    root = tmp_path / "installation"
    record_path = root / "launcher" / "installation.json"
    record_path.parent.mkdir(parents=True)
    LauncherInstallationRecord(version="0.23.1", target_key="windows_x64").save(
        record_path
    )

    with pytest.raises(InstallerLifecycleError, match="expected 0.24.2, got 0.23.1"):
        assert_installed_root_launcher_version(
            install_root=root, expected_version="0.24.2"
        )


def test_historical_update_requires_root_to_accept_the_new_main_shell(
    tmp_path: Path,
) -> None:
    """A selected launcher's receipt cannot stand in for the root's receipt."""

    install_root = tmp_path / "installation"
    log_path = install_root / "launcher" / "logs" / "launcher.log"
    log_path.parent.mkdir(parents=True)
    old_line = (
        "INFO process=99 launcher.sugarsubstitute_launcher."
        "application_readiness_supervisor Accepted painted application surface | "
        "candidate_pid=100 | surface_pid=500 | surface=main_shell | "
        "outer_contract=False\n"
    )
    log_path.write_text(old_line, encoding="utf-8")
    launch = SimpleNamespace(progress_baselines=((log_path, (True, len(old_line))),))
    selected_line = (
        "INFO process=200 launcher.sugarsubstitute_launcher."
        "application_readiness_supervisor Accepted painted application surface | "
        "candidate_pid=300 | surface_pid=500 | surface=main_shell | "
        "outer_contract=True\n"
    )
    with log_path.open("a", encoding="utf-8") as output:
        output.write(selected_line)

    with pytest.raises(InstallerLifecycleError, match="root did not accept"):
        assert_root_main_shell_acknowledgement(
            install_root=install_root,
            candidate_launch=launch,
            surface_pid=500,
        )

    with log_path.open("a", encoding="utf-8") as output:
        output.write(
            "INFO process=400 launcher.sugarsubstitute_launcher."
            "application_readiness_supervisor Accepted painted application surface | "
            "candidate_pid=200 | surface_pid=500 | surface=main_shell | "
            "outer_contract=False\n"
        )
    assert_root_main_shell_acknowledgement(
        install_root=install_root,
        candidate_launch=launch,
        surface_pid=500,
    )
