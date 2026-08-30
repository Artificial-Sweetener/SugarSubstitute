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

"""Protect readiness assessment for remote Comfy targets."""

from __future__ import annotations

from pathlib import Path

from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
)
from substitute.domain.onboarding.readiness_models import ReadinessIssueCode

from .support import (
    FakeBackendCompatibility,
    FakeReadinessChecks,
    present_files,
    readiness_service,
)


def remote_target() -> ComfyTargetConfiguration:
    """Build one remote target configuration."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )


def test_readiness_assess_reports_unreachable_remote_endpoint(tmp_path: Path) -> None:
    """Remote readiness should fail when the saved endpoint is offline."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        remote_target(),
        FakeReadinessChecks(
            files=present_files(installation), endpoint_reachable=False
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE


def test_readiness_assess_routes_reachable_remote_backend_incompatibility_to_repair(
    tmp_path: Path,
) -> None:
    """Reachable remote targets should enforce backend compatibility."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        remote_target(),
        FakeReadinessChecks(files=present_files(installation)),
        backend_compatibility=FakeBackendCompatibility(
            result=BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
                summary="Substitute BackEnd version is incompatible.",
                installed_backend_version="1.5.0",
                required_backend_version=">=1.6.2,<2.0.0",
                repairable=True,
            ),
            assessed_targets=[],
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.BACKEND_COMPATIBILITY_FAILED
    assert "backend_too_old" in assessment.issues[0].detail
