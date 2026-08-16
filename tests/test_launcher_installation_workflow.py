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

"""Tests for the presentation-independent installation application workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ApplicationInstallationRequest,
    InstallationPreparation,
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.first_run import (
    ContinuedInstallResult,
    DownloadedLauncherInstallResult,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installer import InstallPreparationResult
from launcher.sugarsubstitute_launcher.manifest import ReleaseManifest
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeProvisioningResult


class UnusedReleaseSource:
    """Reject unexpected manifest loading by workflow orchestration tests."""

    def load_manifest(self) -> ReleaseManifest:
        """Fail because fake artifact adapters should not load a manifest."""

        raise AssertionError("The workflow should pass release sources to adapters.")


@dataclass
class RecordingLayoutPreparer:
    """Record layout preparation requests."""

    layout: InstallLayout
    calls: int = 0

    def prepare(self, install_root: Path) -> InstallPreparationResult:
        """Return the configured prepared layout."""

        assert install_root == self.layout.root
        self.calls += 1
        return InstallPreparationResult(
            layout=self.layout,
            config=LauncherConfig.from_layout(layout=self.layout),
        )


@dataclass
class RecordingArtifactInstaller:
    """Record launcher and payload artifact installation requests."""

    layout: InstallLayout
    launcher_calls: int = 0
    payload_calls: int = 0

    def install_downloaded_launcher(
        self,
        *,
        install_root: Path,
        release_source: ReleaseManifestSource,
        handoff_geometry: str | None = None,
        launch_installed: bool = True,
    ) -> DownloadedLauncherInstallResult:
        """Record permanent launcher installation without process handoff."""

        assert install_root == self.layout.root
        assert isinstance(release_source, UnusedReleaseSource)
        assert handoff_geometry == "1,2,1260,800"
        assert launch_installed is False
        self.launcher_calls += 1
        return DownloadedLauncherInstallResult(
            layout=self.layout,
            continue_command=[],
        )

    def continue_install(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
    ) -> ContinuedInstallResult:
        """Record payload installation and return its command."""

        assert layout == self.layout
        assert isinstance(release_source, UnusedReleaseSource)
        self.payload_calls += 1
        return ContinuedInstallResult(
            layout=layout,
            app_command=["python.exe", "main.py"],
            app_version="1.2.3",
        )


@dataclass
class RecordingRuntimeProvisioner:
    """Record runtime provisioning requests."""

    layout: InstallLayout
    calls: int = 0

    def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
        """Return a deterministic runtime result."""

        assert layout == self.layout
        self.calls += 1
        return RuntimeProvisioningResult(
            python_executable=layout.runtime_python,
            requirements_path=layout.app_dir / "requirements.txt",
        )


@pytest.mark.parametrize(
    ("preparation", "expected_layout_calls", "expected_launcher_calls"),
    [
        (InstallationPreparation.INSTALL_LAUNCHER, 0, 1),
        (InstallationPreparation.PREPARE_LAYOUT, 1, 0),
        (InstallationPreparation.USE_EXISTING_LAYOUT, 0, 0),
    ],
)
def test_workflow_owns_each_layout_preparation_path(
    tmp_path: Path,
    preparation: InstallationPreparation,
    expected_layout_calls: int,
    expected_launcher_calls: int,
) -> None:
    """Every installer entry mode should converge on one payload workflow."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    layout_preparer = RecordingLayoutPreparer(layout)
    artifact_installer = RecordingArtifactInstaller(layout)
    runtime_provisioner = RecordingRuntimeProvisioner(layout)
    workflow = InstallationWorkflow(
        layout_preparer=layout_preparer,
        artifact_installer=artifact_installer,
        runtime_provisioner=runtime_provisioner,
        process_starter=lambda _command: None,
    )

    result = workflow.install_application(
        ApplicationInstallationRequest(
            layout=layout,
            release_source=UnusedReleaseSource(),
            preparation=preparation,
            handoff_geometry="1,2,1260,800",
        )
    )

    assert layout_preparer.calls == expected_layout_calls
    assert artifact_installer.launcher_calls == expected_launcher_calls
    assert artifact_installer.payload_calls == 1
    assert result.layout == layout
    assert result.app_command == ("python.exe", "main.py")
    assert result.app_version == "1.2.3"
    assert result.launcher_installed is bool(expected_launcher_calls)


def test_workflow_provisions_runtime_and_delegates_setup_handoff(
    tmp_path: Path,
) -> None:
    """Runtime and process adapters should remain behind the application workflow."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    layout_preparer = RecordingLayoutPreparer(layout)
    artifact_installer = RecordingArtifactInstaller(layout)
    runtime_provisioner = RecordingRuntimeProvisioner(layout)
    started_commands: list[list[str]] = []
    workflow = InstallationWorkflow(
        layout_preparer=layout_preparer,
        artifact_installer=artifact_installer,
        runtime_provisioner=runtime_provisioner,
        process_starter=lambda command: started_commands.append(list(command)),
    )
    application = workflow.install_application(
        ApplicationInstallationRequest(
            layout=layout,
            release_source=UnusedReleaseSource(),
            preparation=InstallationPreparation.USE_EXISTING_LAYOUT,
        )
    )

    completed = workflow.provision_runtime(application)
    workflow.start_setup(application.app_command)

    assert runtime_provisioner.calls == 1
    assert completed.application == application
    assert completed.runtime_python == layout.runtime_python
    assert started_commands == [["python.exe", "main.py"]]
