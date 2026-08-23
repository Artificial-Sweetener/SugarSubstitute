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

"""Protect readiness assessment for attached-local Comfy targets."""

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


def attached_target(workspace: Path | None) -> ComfyTargetConfiguration:
    """Build one launch-owned attached-local target."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=workspace,
        install_owned=False,
        launch_owned=True,
    )


def test_readiness_assess_returns_ready_for_existing_local_setup_when_stopped(
    tmp_path: Path,
) -> None:
    """Stopped attached-local setups should stay ready for launcher startup."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        attached_target(tmp_path / "ComfyUI"),
        FakeReadinessChecks(
            files=present_files(installation), endpoint_reachable=False
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()


def test_readiness_assess_skips_backend_compatibility_when_attached_local_is_stopped(
    tmp_path: Path,
) -> None:
    """Stopped attached-local targets should not be compatibility-assessed."""

    installation = InstallationConfiguration.create_default(tmp_path)
    compatibility = FakeBackendCompatibility(
        result=BackendCompatibilityResult(
            status=RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
            summary="Substitute BackEnd version is incompatible.",
            installed_backend_version="1.5.0",
            required_backend_version=">=1.6.2,<2.0.0",
            repairable=True,
        ),
        assessed_targets=[],
    )
    service = readiness_service(
        installation,
        attached_target(tmp_path / "ComfyUI"),
        FakeReadinessChecks(
            files=present_files(installation), endpoint_reachable=False
        ),
        backend_compatibility=compatibility,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()
    assert compatibility.assessed_targets == []


def test_readiness_assess_reports_existing_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Attached-local readiness should require a configured workspace."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        attached_target(None),
        FakeReadinessChecks(files=present_files(installation)),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING


def test_readiness_assess_reports_missing_attached_workspace(tmp_path: Path) -> None:
    """Attached-local readiness should reject an unavailable workspace."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        attached_target(tmp_path / "ComfyUI"),
        FakeReadinessChecks(
            files=present_files(installation),
            attached_workspace_present=False,
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING
