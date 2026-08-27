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

"""Protect readiness assessment for managed-local Comfy targets."""

from __future__ import annotations

from dataclasses import dataclass
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
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
)
from substitute.domain.onboarding.readiness_models import ReadinessIssueCode
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)

from .support import (
    FakeBackendCompatibility,
    FakeReadinessChecks,
    present_files,
    readiness_service,
)


def managed_target(installation: InstallationConfiguration) -> ComfyTargetConfiguration:
    """Build the installation-owned managed target."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )


def valid_managed_runtime() -> ManagedRuntimeConfiguration:
    """Build a valid managed-runtime record."""

    return ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )


def test_readiness_assess_returns_ready_for_valid_managed_setup_without_listener(
    tmp_path: Path,
) -> None:
    """Cold managed setup should not require ComfyUI to already be running."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        managed_target(installation),
        FakeReadinessChecks(files=present_files(installation)),
        managed_runtime=valid_managed_runtime(),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()


def test_readiness_assess_repairs_when_managed_runtime_claims_other_workspace(
    tmp_path: Path,
) -> None:
    """Managed readiness should require the configured workspace to be claimed."""

    installation = InstallationConfiguration.create_default(tmp_path)
    managed_runtime = ManagedRuntimeConfiguration(
        workspace_path=str((tmp_path / "OtherComfy").resolve()),
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
    service = readiness_service(
        installation,
        managed_target(installation),
        FakeReadinessChecks(files=present_files(installation)),
        managed_runtime=managed_runtime,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert (
        assessment.issues[0].code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_INSTALLED
    )


def test_readiness_assess_skips_prelaunch_endpoint_probe_for_managed_startup(
    tmp_path: Path,
) -> None:
    """Cold managed startup should defer both endpoint and compatibility checks."""

    installation = InstallationConfiguration.create_default(tmp_path)
    reachability_calls: list[ComfyTargetConfiguration] = []
    compatibility = FakeBackendCompatibility(
        result=BackendCompatibilityResult(
            status=RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD,
            summary="SugarCubes version is incompatible.",
            installed_backend_version="1.6.2",
            installed_sugarcubes_version="0.8.0",
            required_sugarcubes_version="0.11.0",
            repairable=True,
        ),
        assessed_targets=[],
    )
    service = readiness_service(
        installation,
        managed_target(installation),
        FakeReadinessChecks(
            files=present_files(installation),
            endpoint_reachability_calls=reachability_calls,
        ),
        managed_runtime=valid_managed_runtime(),
        backend_compatibility=compatibility,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()
    assert reachability_calls == []
    assert compatibility.assessed_targets == []


def test_readiness_assess_routes_running_managed_backend_incompatibility_to_repair(
    tmp_path: Path,
) -> None:
    """Running managed targets should be compatibility-gated before UI launch."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        managed_target(installation),
        FakeReadinessChecks(
            files=present_files(installation),
            endpoint_reachable=True,
            managed_listener_status=ManagedListenerStatus.OWNED_HEALTHY,
        ),
        managed_runtime=valid_managed_runtime(),
        backend_compatibility=FakeBackendCompatibility(
            result=BackendCompatibilityResult(
                status=RuntimeCompatibilityStatus.SUGARCUBES_TOO_OLD,
                summary="SugarCubes version is incompatible.",
                installed_backend_version="1.6.2",
                installed_sugarcubes_version="0.8.0",
                required_sugarcubes_version="0.11.0",
                repairable=True,
            ),
            assessed_targets=[],
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.BACKEND_COMPATIBILITY_FAILED
    assert "sugarcubes_too_old" in assessment.issues[0].detail


def test_readiness_assess_routes_managed_missing_nodepacks_to_repair(
    tmp_path: Path,
) -> None:
    """Managed readiness should require Substitute's core nodepacks."""

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        managed_target(installation),
        FakeReadinessChecks(
            files=present_files(installation),
            managed_nodepacks_present=False,
        ),
        managed_runtime=valid_managed_runtime(),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert (
        assessment.issues[0].code
        is ReadinessIssueCode.MANAGED_WORKSPACE_NODEPACKS_MISSING
    )


def test_readiness_assess_ignores_stale_owned_managed_process_state(
    tmp_path: Path,
) -> None:
    """Stale owned listeners should be deferred to launcher cleanup."""

    @dataclass(frozen=True)
    class StaleOwnedChecks(FakeReadinessChecks):
        """Report a stale-owned listener while retaining a healthy workspace."""

        def probe_managed_listener(
            self,
            *,
            installation: InstallationConfiguration,
            configuration: ComfyTargetConfiguration,
        ) -> ManagedListenerProbeResult:
            """Report a stale listener that launcher startup must reap later."""

            _ = installation, configuration
            return ManagedListenerProbeResult(
                status=ManagedListenerStatus.OWNED_STALE,
                reason="Owned process exists but is no longer listening.",
            )

    installation = InstallationConfiguration.create_default(tmp_path)
    service = readiness_service(
        installation,
        managed_target(installation),
        StaleOwnedChecks(files=present_files(installation)),
        managed_runtime=valid_managed_runtime(),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()
