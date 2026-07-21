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

"""Tests for bootstrap readiness assessment across managed and attached targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.installation_service import InstallationService
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.onboarding.readiness_service import (
    BootstrapReadinessService,
)
from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.onboarding.readiness_models import ReadinessIssueCode
from substitute.infrastructure.onboarding.readiness_checks import (
    ConfigurationFileSet,
)
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)


@dataclass(frozen=True)
class _StaticInstallationService:
    """Return one persisted installation configuration for readiness tests."""

    configuration: InstallationConfiguration | None

    def load_persisted(self) -> InstallationConfiguration | None:
        """Return the persisted installation configuration."""

        return self.configuration


@dataclass(frozen=True)
class _StaticRuntimeService:
    """Return one persisted runtime configuration for readiness tests."""

    configuration: RuntimeConfiguration | None

    def load_persisted(self) -> RuntimeConfiguration | None:
        """Return the persisted runtime configuration."""

        return self.configuration


@dataclass(frozen=True)
class _StaticTargetService:
    """Return one persisted target configuration for readiness tests."""

    configuration: ComfyTargetConfiguration | None

    def load_persisted(self) -> ComfyTargetConfiguration | None:
        """Return the persisted target configuration."""

        return self.configuration


@dataclass(frozen=True)
class _StaticManagedRuntimeService:
    """Return one persisted managed runtime configuration for readiness tests."""

    configuration: ManagedRuntimeConfiguration | None = None

    def load_persisted(self) -> ManagedRuntimeConfiguration | None:
        """Return the persisted managed runtime configuration."""

        return self.configuration


@dataclass(frozen=True)
class _FakeChecks:
    """Provide deterministic readiness check outcomes for one scenario."""

    files: ConfigurationFileSet
    installation_valid: bool = True
    runtime_valid: bool = True
    runtime_python_present: bool = True
    target_valid: bool = True
    managed_workspace_installed: bool = True
    managed_workspace_launchable: bool = True
    managed_nodepacks_present: bool = True
    attached_workspace_present: bool = True
    endpoint_reachable: bool = True
    managed_listener_status: ManagedListenerStatus = ManagedListenerStatus.ABSENT
    endpoint_reachability_calls: list[ComfyTargetConfiguration] | None = None

    def configuration_files(self, installation_root: Path) -> ConfigurationFileSet:
        """Return the configured file set."""

        _ = installation_root
        return self.files

    def is_installation_configuration_valid(
        self,
        configuration: InstallationConfiguration,
    ) -> bool:
        """Return the configured installation validation result."""

        _ = configuration
        return self.installation_valid

    def is_runtime_configuration_valid(
        self, configuration: RuntimeConfiguration
    ) -> bool:
        """Return the configured runtime validation result."""

        _ = configuration
        return self.runtime_valid

    def runtime_python_exists(self, configuration: RuntimeConfiguration) -> bool:
        """Return the configured runtime-python existence result."""

        _ = configuration
        return self.runtime_python_present

    def is_target_configuration_valid(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return the configured target validation result."""

        _ = configuration
        return self.target_valid

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return the configured attached-workspace existence result."""

        _ = workspace
        return self.attached_workspace_present

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return the configured endpoint reachability result."""

        if self.endpoint_reachability_calls is not None:
            self.endpoint_reachability_calls.append(configuration)
        return self.endpoint_reachable

    def is_managed_workspace_installed(self, workspace: Path) -> bool:
        """Return the configured managed-install result."""

        _ = workspace
        return self.managed_workspace_installed

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return the configured managed-launchability result."""

        _ = workspace
        return self.managed_workspace_launchable

    def has_required_managed_nodepacks(self, workspace: Path) -> bool:
        """Return the configured managed-nodepack result."""

        _ = workspace
        return self.managed_nodepacks_present

    def probe_managed_listener(
        self,
        *,
        installation: InstallationConfiguration,
        configuration: ComfyTargetConfiguration,
    ) -> ManagedListenerProbeResult:
        """Return an absent managed-listener result for non-managed readiness tests."""

        _ = installation, configuration
        return ManagedListenerProbeResult(
            status=self.managed_listener_status,
            reason=f"Managed listener status: {self.managed_listener_status.value}.",
        )


@dataclass
class _FakeBackendCompatibility:
    """Return one configured compatibility result for readiness tests."""

    result: BackendCompatibilityResult
    assessed_targets: list[ComfyTargetConfiguration]

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Record the assessed target and return the configured result."""

        self.assessed_targets.append(target)
        return self.result


def _build_runtime_configuration(
    installation: InstallationConfiguration,
) -> RuntimeConfiguration:
    """Build a ready runtime configuration for readiness tests."""

    return RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )


def _build_file_set(installation: InstallationConfiguration) -> ConfigurationFileSet:
    """Build a present configuration-file set for one installation."""

    installation.user_settings_dir.mkdir(parents=True, exist_ok=True)
    file_set = ConfigurationFileSet(
        installation_path=installation.user_settings_dir / "installation.json",
        runtime_path=installation.user_settings_dir / "runtime.json",
        target_path=installation.user_settings_dir / "comfy_target.json",
    )
    file_set.installation_path.write_text("{}", encoding="utf-8")
    file_set.runtime_path.write_text("{}", encoding="utf-8")
    file_set.target_path.write_text("{}", encoding="utf-8")
    return file_set


def test_readiness_assess_returns_ready_for_existing_local_setup_when_stopped(
    tmp_path: Path,
) -> None:
    """Existing-local readiness should not require ComfyUI to already be running."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=Path(r"E:\ComfyUIExternalTest"),
        install_owned=False,
        launch_owned=True,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            endpoint_reachable=False,
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()


def test_readiness_assess_skips_backend_compatibility_when_attached_local_is_stopped(
    tmp_path: Path,
) -> None:
    """Stopped attached-local setups should not be forced into repair."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=Path(r"E:\ComfyUIExternalTest"),
        install_owned=False,
        launch_owned=True,
    )
    backend_compatibility = _FakeBackendCompatibility(
        result=BackendCompatibilityResult(
            status=RuntimeCompatibilityStatus.BACKEND_TOO_OLD,
            summary="Substitute BackEnd version is incompatible.",
            installed_backend_version="1.5.0",
            required_backend_version=">=1.6.2,<2.0.0",
            repairable=True,
        ),
        assessed_targets=[],
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            endpoint_reachable=False,
        ),
        backend_compatibility=backend_compatibility,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()
    assert backend_compatibility.assessed_targets == []


def test_readiness_assess_reports_existing_local_without_workspace(
    tmp_path: Path,
) -> None:
    """Existing-local readiness should require a local ComfyUI folder."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=None,
        install_owned=False,
        launch_owned=True,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(),
        ),
        checks=_FakeChecks(files=_build_file_set(installation)),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING


def test_readiness_assess_reports_missing_attached_workspace(tmp_path: Path) -> None:
    """Attached-local readiness should fail when the configured folder no longer exists."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.ATTACHED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=Path(r"E:\ComfyUIExternalTest"),
        install_owned=False,
        launch_owned=True,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            attached_workspace_present=False,
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING


def test_readiness_assess_reports_unreachable_remote_endpoint(tmp_path: Path) -> None:
    """Remote readiness should fail when the saved endpoint is offline."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            endpoint_reachable=False,
        ),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert assessment.issues[0].code is ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE


def test_readiness_assess_routes_reachable_remote_backend_incompatibility_to_repair(
    tmp_path: Path,
) -> None:
    """Reachable remote targets should fail readiness when BackEnd is incompatible."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8190),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(),
        ),
        checks=_FakeChecks(files=_build_file_set(installation)),
        backend_compatibility=_FakeBackendCompatibility(
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


def test_readiness_assess_returns_ready_for_valid_managed_setup_without_listener(
    tmp_path: Path,
) -> None:
    """Cold-start managed setups should not route to repair just because Comfy is stopped."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    managed_runtime = ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeChecks(files=_build_file_set(installation)),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()


def test_readiness_assess_repairs_when_managed_runtime_claims_other_workspace(
    tmp_path: Path,
) -> None:
    """Managed state must claim the configured workspace before normal startup."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    managed_runtime = ManagedRuntimeConfiguration(
        workspace_path=str((tmp_path / "OtherComfy").resolve()),
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeChecks(files=_build_file_set(installation)),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.REPAIR
    assert (
        assessment.issues[0].code is ReadinessIssueCode.MANAGED_WORKSPACE_NOT_INSTALLED
    )


def test_readiness_assess_skips_prelaunch_endpoint_probe_for_managed_startup(
    tmp_path: Path,
) -> None:
    """Cold managed startup should not spend readiness time probing a stopped endpoint."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    managed_runtime = ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
    endpoint_reachability_calls: list[ComfyTargetConfiguration] = []
    backend_compatibility = _FakeBackendCompatibility(
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
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            endpoint_reachability_calls=endpoint_reachability_calls,
        ),
        backend_compatibility=backend_compatibility,
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()
    assert endpoint_reachability_calls == []
    assert backend_compatibility.assessed_targets == []


def test_readiness_assess_routes_running_managed_backend_incompatibility_to_repair(
    tmp_path: Path,
) -> None:
    """Running managed targets should be compatibility-gated before main UI launch."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    managed_runtime = ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            endpoint_reachable=True,
            managed_listener_status=ManagedListenerStatus.OWNED_HEALTHY,
        ),
        backend_compatibility=_FakeBackendCompatibility(
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
    """Managed readiness should fail when Substitute's core nodepacks are missing."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    managed_runtime = ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )
    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_FakeChecks(
            files=_build_file_set(installation),
            managed_nodepacks_present=False,
        ),
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
    """Bootstrap readiness should not route to repair for stale owned listeners."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = _build_runtime_configuration(installation)
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=installation.default_managed_comfy_dir,
        install_owned=True,
        launch_owned=True,
    )
    managed_runtime = ManagedRuntimeConfiguration(
        install_target="windows_nvidia",
        backend_policy="cuda_nightly_cu130",
        validation_status=ManagedRuntimeValidationStatus.VALID,
    )

    @dataclass(frozen=True)
    class _StaleOwnedChecks(_FakeChecks):
        """Return a stale-owned probe while keeping the workspace otherwise healthy."""

        def probe_managed_listener(
            self,
            *,
            installation: InstallationConfiguration,
            configuration: ComfyTargetConfiguration,
        ) -> ManagedListenerProbeResult:
            """Report a stale owned listener that launcher startup should reap later."""

            _ = installation, configuration
            return ManagedListenerProbeResult(
                status=ManagedListenerStatus.OWNED_STALE,
                reason="Owned process exists but is no longer listening.",
            )

    service = BootstrapReadinessService(
        installation_root=installation.installation_root,
        installation_service=cast(
            InstallationService,
            _StaticInstallationService(installation),
        ),
        runtime_service=cast(RuntimeService, _StaticRuntimeService(runtime)),
        comfy_target_service=cast(
            ComfyTargetService,
            _StaticTargetService(target),
        ),
        managed_runtime_service=cast(
            ManagedRuntimeService,
            _StaticManagedRuntimeService(managed_runtime),
        ),
        checks=_StaleOwnedChecks(files=_build_file_set(installation)),
    )

    assessment = service.assess()

    assert assessment.route is BootstrapRoute.READY
    assert assessment.issues == ()
