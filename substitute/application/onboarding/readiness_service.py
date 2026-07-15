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

"""Assess bootstrap readiness and select the correct startup route."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.installation_service import InstallationService
from substitute.application.onboarding.managed_runtime_service import (
    ManagedRuntimeService,
)
from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.application.ports.setup_transaction_repository import (
    SetupTransactionRepository,
    SetupTransactionRepositoryError,
)
from substitute.domain.onboarding import (
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    ManagedRuntimeConfiguration,
    ManagedRuntimeValidationStatus,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.onboarding.readiness_models import (
    BootstrapRoute,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
)
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionStatus,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.onboarding.readiness_service")


class ConfigurationFileSet(Protocol):
    """Describe persisted onboarding configuration file locations."""

    @property
    def installation_path(self) -> Path:
        """Return the persisted installation configuration path."""

    @property
    def runtime_path(self) -> Path:
        """Return the persisted runtime configuration path."""

    @property
    def target_path(self) -> Path:
        """Return the persisted target configuration path."""


class ReadinessChecks(Protocol):
    """Describe filesystem-backed readiness checks used by the service."""

    def configuration_files(self, installation_root: Path) -> ConfigurationFileSet:
        """Return persisted onboarding config files for one install root."""

    def is_installation_configuration_valid(
        self,
        configuration: InstallationConfiguration,
    ) -> bool:
        """Return whether installation configuration remains valid."""

    def is_runtime_configuration_valid(
        self,
        configuration: RuntimeConfiguration,
    ) -> bool:
        """Return whether runtime configuration remains valid."""

    def runtime_python_exists(self, configuration: RuntimeConfiguration) -> bool:
        """Return whether runtime python executable exists."""

    def is_target_configuration_valid(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether target configuration remains valid."""

    def attached_workspace_exists(self, workspace: Path) -> bool:
        """Return whether an attached-local workspace path exists on disk."""

    def is_target_endpoint_reachable(
        self,
        configuration: ComfyTargetConfiguration,
    ) -> bool:
        """Return whether the configured Comfy endpoint can be reached."""

    def is_managed_workspace_installed(self, workspace: Path) -> bool:
        """Return whether managed workspace install artifacts exist."""

    def is_managed_workspace_launchable(self, workspace: Path) -> bool:
        """Return whether managed workspace can launch immediately."""

    def has_required_managed_nodepacks(self, workspace: Path) -> bool:
        """Return whether required Substitute nodepacks are present."""

    def probe_managed_listener(
        self,
        *,
        installation: InstallationConfiguration,
        configuration: ComfyTargetConfiguration,
    ) -> object:
        """Return the managed listener ownership probe result for one target."""


class BackendCompatibilityChecker(Protocol):
    """Assess runtime compatibility for one configured Comfy target."""

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Return Backend/SugarCubes compatibility for the target endpoint."""


@dataclass
class BootstrapReadinessService:
    """Assess persisted onboarding state and choose bootstrap routing."""

    installation_root: Path
    installation_service: InstallationService
    runtime_service: RuntimeService
    comfy_target_service: ComfyTargetService
    managed_runtime_service: ManagedRuntimeService
    checks: ReadinessChecks
    setup_transaction_repository: SetupTransactionRepository | None = None
    backend_compatibility: BackendCompatibilityChecker | None = None

    def assess(self) -> ReadinessAssessment:
        """Return the current bootstrap route with explicit readiness issues."""

        issues: list[ReadinessIssue] = []
        files = self.checks.configuration_files(self.installation_root)
        installation = self.installation_service.load_persisted()
        runtime = self.runtime_service.load_persisted()
        target = self.comfy_target_service.load_persisted()
        managed_runtime = self.managed_runtime_service.load_persisted()

        self._assess_installation(files, installation, issues)
        self._assess_runtime(files, runtime, issues)
        self._assess_target(files, target, issues)

        managed_listener_status: str | None = None
        if target is not None and target.mode is ComfyTargetMode.MANAGED_LOCAL:
            managed_listener_status = self._assess_managed_workspace(
                installation=installation,
                target=target,
                managed_runtime=managed_runtime,
                issues=issues,
            )

        if target is not None:
            self._assess_backend_compatibility(
                target=target,
                issues=issues,
                managed_listener_status=managed_listener_status,
            )
        self._assess_pending_transaction(issues)
        route = self._route_for(issues)
        return ReadinessAssessment(route=route, issues=tuple(issues))

    def assess_candidate(
        self,
        *,
        installation: InstallationConfiguration,
        runtime: RuntimeConfiguration,
        target: ComfyTargetConfiguration,
        managed_runtime: ManagedRuntimeConfiguration | None = None,
    ) -> ReadinessAssessment:
        """Assess pending configuration before it is committed as active state."""

        issues: list[ReadinessIssue] = []
        self._assess_installation_configuration(installation, issues)
        self._assess_runtime_configuration(runtime, issues)
        self._assess_target_configuration(target, issues)
        if target.mode is ComfyTargetMode.MANAGED_LOCAL:
            self._assess_managed_workspace(
                installation=installation,
                target=target,
                managed_runtime=managed_runtime,
                issues=issues,
            )
        self._assess_backend_compatibility(
            target=target,
            issues=issues,
            managed_listener_status=None,
        )
        route = self._route_for(issues)
        return ReadinessAssessment(route=route, issues=tuple(issues))

    def _assess_pending_transaction(self, issues: list[ReadinessIssue]) -> None:
        """Append pending transaction recovery issues only when active state is blocked."""

        if self.setup_transaction_repository is None:
            return
        try:
            transaction = self.setup_transaction_repository.load()
        except SetupTransactionRepositoryError as error:
            if not issues:
                log_warning(
                    _LOGGER,
                    "Ignoring corrupt pending setup transaction because active state is ready.",
                    error=error,
                )
                return
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.SETUP_TRANSACTION_CORRUPT,
                    summary="Setup state could not be read.",
                    detail="Pending setup state is unreadable and setup must be started again.",
                )
            )
            return
        if transaction is None:
            return
        if not issues:
            log_info(
                _LOGGER,
                "Ignoring pending setup transaction because active state is ready.",
                transaction_id=transaction.transaction_id,
                mode=transaction.mode.value,
                status=transaction.status.value,
            )
            return
        issues.append(self._issue_for_pending_transaction(transaction))

    @staticmethod
    def _issue_for_pending_transaction(
        transaction: SetupTransaction,
    ) -> ReadinessIssue:
        """Describe one pending setup transaction in readiness terms."""

        if transaction.status is SetupTransactionStatus.FAILED:
            detail = (
                transaction.failure.message
                if transaction.failure is not None
                else "The previous setup attempt failed before it could be committed."
            )
            return ReadinessIssue(
                code=ReadinessIssueCode.SETUP_TRANSACTION_FAILED,
                summary="Setup did not finish.",
                detail=detail,
            )
        return ReadinessIssue(
            code=ReadinessIssueCode.SETUP_TRANSACTION_INTERRUPTED,
            summary="Setup was interrupted.",
            detail="Continue setup to finish validating the selected ComfyUI runtime.",
        )

    def _assess_installation(
        self,
        files: ConfigurationFileSet,
        installation: InstallationConfiguration | None,
        issues: list[ReadinessIssue],
    ) -> None:
        """Append installation configuration issues."""

        if not files.installation_path.exists() or installation is None:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.INSTALLATION_CONFIG_MISSING,
                    summary="Installation setup has not been saved yet.",
                    detail="Create installation configuration through onboarding.",
                )
            )
            return
        self._assess_installation_configuration(installation, issues)

    def _assess_installation_configuration(
        self,
        installation: InstallationConfiguration,
        issues: list[ReadinessIssue],
    ) -> None:
        """Append installation configuration validity issues."""

        if not self.checks.is_installation_configuration_valid(installation):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.INSTALLATION_CONFIG_INVALID,
                    summary="Installation configuration is invalid.",
                    detail="Installation paths no longer match the selected install root.",
                )
            )

    def _assess_runtime(
        self,
        files: ConfigurationFileSet,
        runtime: RuntimeConfiguration | None,
        issues: list[ReadinessIssue],
    ) -> None:
        """Append runtime configuration issues."""

        if not files.runtime_path.exists() or runtime is None:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_CONFIG_MISSING,
                    summary="Substitute runtime has not been configured yet.",
                    detail="Provision the visible runtime through onboarding.",
                )
            )
            return
        self._assess_runtime_configuration(runtime, issues)

    def _assess_runtime_configuration(
        self,
        runtime: RuntimeConfiguration,
        issues: list[ReadinessIssue],
    ) -> None:
        """Append runtime configuration validity and provisioning issues."""

        if not self.checks.is_runtime_configuration_valid(runtime):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_CONFIG_INVALID,
                    summary="Runtime configuration is invalid.",
                    detail="Runtime paths do not match the expected visible runtime layout.",
                )
            )
        if runtime.bootstrap_status is RuntimeBootstrapStatus.MISSING:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_NOT_PROVISIONED,
                    summary="Substitute runtime has not been provisioned yet.",
                    detail="Run onboarding to create the visible runtime environment.",
                )
            )
        elif runtime.bootstrap_status in {
            RuntimeBootstrapStatus.PROVISIONING,
            RuntimeBootstrapStatus.FAILED,
        }:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_PROVISIONING_INCOMPLETE,
                    summary="Substitute runtime is incomplete.",
                    detail="Repair the visible runtime before normal launch.",
                )
            )
        elif (
            runtime.bootstrap_status is RuntimeBootstrapStatus.READY
            and not self.checks.runtime_python_exists(runtime)
        ):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_PYTHON_MISSING,
                    summary="Runtime Python executable is missing.",
                    detail="Repair the visible runtime before normal launch.",
                )
            )

    def _assess_target(
        self,
        files: ConfigurationFileSet,
        target: ComfyTargetConfiguration | None,
        issues: list[ReadinessIssue],
    ) -> None:
        """Append Comfy target configuration issues."""

        if not files.target_path.exists() or target is None:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.TARGET_CONFIG_MISSING,
                    summary="Comfy target has not been configured yet.",
                    detail="Choose managed local, attached local, or remote in onboarding.",
                )
            )
            return
        self._assess_target_configuration(target, issues)

    def _assess_target_configuration(
        self,
        target: ComfyTargetConfiguration,
        issues: list[ReadinessIssue],
    ) -> None:
        """Append Comfy target validity and reachability issues."""

        if not self.checks.is_target_configuration_valid(target):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.TARGET_CONFIG_INVALID,
                    summary="Comfy target configuration is invalid.",
                    detail="The selected target is missing required endpoint or workspace details.",
                )
            )
            return
        if target.mode is ComfyTargetMode.ATTACHED_LOCAL and (
            target.workspace_path is None
            or not self.checks.attached_workspace_exists(target.workspace_path)
        ):
            detail = (
                "Existing local ComfyUI setup requires a folder path."
                if target.workspace_path is None
                else f"Attached ComfyUI folder does not exist: {target.workspace_path}"
            )
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.ATTACHED_WORKSPACE_MISSING,
                    summary="The saved ComfyUI folder could not be found.",
                    detail=detail,
                )
            )
        if (
            target.mode is ComfyTargetMode.REMOTE
            and not self.checks.is_target_endpoint_reachable(target)
        ):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.TARGET_ENDPOINT_UNREACHABLE,
                    summary="Substitute could not reach the saved ComfyUI address.",
                    detail=(
                        f"ComfyUI did not respond at "
                        f"{target.endpoint.host}:{target.endpoint.port}."
                    ),
                )
            )

    def _assess_backend_compatibility(
        self,
        *,
        target: ComfyTargetConfiguration,
        issues: list[ReadinessIssue],
        managed_listener_status: str | None,
    ) -> None:
        """Append Backend/SugarCubes compatibility issues for reachable targets."""

        if self.backend_compatibility is None or issues:
            return
        if not self._should_probe_backend_compatibility(
            target,
            managed_listener_status=managed_listener_status,
        ):
            return
        result = self.backend_compatibility.assess_target(target)
        if result.compatible:
            return
        issues.append(
            ReadinessIssue(
                code=ReadinessIssueCode.BACKEND_COMPATIBILITY_FAILED,
                summary=result.summary,
                detail=_backend_compatibility_detail(result),
            )
        )

    def _should_probe_backend_compatibility(
        self,
        target: ComfyTargetConfiguration,
        *,
        managed_listener_status: str | None,
    ) -> bool:
        """Return whether runtime compatibility can be checked without forcing launch."""

        if target.mode is ComfyTargetMode.REMOTE:
            return True
        if target.mode is ComfyTargetMode.MANAGED_LOCAL and target.launch_owned:
            return managed_listener_status == "owned_healthy"
        return self.checks.is_target_endpoint_reachable(target)

    def _assess_managed_workspace(
        self,
        *,
        installation: InstallationConfiguration | None,
        target: ComfyTargetConfiguration,
        managed_runtime: ManagedRuntimeConfiguration | None,
        issues: list[ReadinessIssue],
    ) -> str | None:
        """Append managed-local workspace readiness issues."""

        workspace_path = target.workspace_path
        if workspace_path is None:
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_NOT_CONFIGURED,
                    summary="Managed Comfy workspace is not configured.",
                    detail="Managed local mode requires a workspace path.",
                )
            )
            return None
        if managed_runtime is None or (
            managed_runtime.validation_status is ManagedRuntimeValidationStatus.UNKNOWN
        ):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_NOT_VALIDATED,
                    summary="Managed Comfy workspace has not been validated yet.",
                    detail=(
                        "Substitute has not confirmed that the installed backend and "
                        "workspace match this machine."
                    ),
                )
            )
        elif (
            managed_runtime.validation_status
            is ManagedRuntimeValidationStatus.INVALID_BACKEND
        ):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_BACKEND_INVALID,
                    summary="Managed Comfy workspace backend is invalid for this hardware.",
                    detail=managed_runtime.validation_detail
                    or "The installed managed backend does not match the detected hardware.",
                )
            )
        elif not _managed_runtime_claims_workspace(managed_runtime, workspace_path):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_NOT_INSTALLED,
                    summary="Managed Comfy workspace is not installed.",
                    detail=(
                        "Active managed runtime state does not match the configured "
                        "ComfyUI workspace."
                    ),
                )
            )
            return None
        if not self.checks.is_managed_workspace_installed(workspace_path):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_NOT_INSTALLED,
                    summary="Managed Comfy workspace is not installed.",
                    detail="Provision the managed Comfy workspace before launching.",
                )
            )
            return None
        if not self.checks.is_managed_workspace_launchable(workspace_path):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_NOT_LAUNCHABLE,
                    summary="Managed Comfy workspace is not launchable.",
                    detail="Repair the managed workspace before normal launch.",
                )
            )
        if not self.checks.has_required_managed_nodepacks(workspace_path):
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_NODEPACKS_MISSING,
                    summary="Managed Comfy workspace is missing required nodepacks.",
                    detail=(
                        "Repair the managed workspace so Substitute BackEnd and "
                        "SugarCubes are installed before launch."
                    ),
                )
            )
        if installation is None:
            return None
        listener_probe = self.checks.probe_managed_listener(
            installation=installation,
            configuration=target,
        )
        listener_status = getattr(listener_probe, "status", None)
        listener_status_value = getattr(listener_status, "value", None)
        if listener_status_value == "foreign":
            issues.append(
                ReadinessIssue(
                    code=ReadinessIssueCode.MANAGED_WORKSPACE_FOREIGN_LISTENER_BLOCKED,
                    summary="Another process is already using the managed ComfyUI address.",
                    detail=getattr(
                        listener_probe,
                        "reason",
                        "A foreign process is blocking the configured managed address.",
                    ),
                )
            )
        return listener_status_value if isinstance(listener_status_value, str) else None

    @staticmethod
    def _route_for(issues: list[ReadinessIssue]) -> BootstrapRoute:
        """Map the discovered issue set to one final bootstrap route."""

        if not issues:
            return BootstrapRoute.READY
        onboarding_codes = {
            ReadinessIssueCode.INSTALLATION_CONFIG_MISSING,
            ReadinessIssueCode.RUNTIME_CONFIG_MISSING,
            ReadinessIssueCode.TARGET_CONFIG_MISSING,
            ReadinessIssueCode.RUNTIME_NOT_PROVISIONED,
        }
        if all(issue.code in onboarding_codes for issue in issues):
            return BootstrapRoute.ONBOARDING
        return BootstrapRoute.REPAIR


def _backend_compatibility_detail(result: BackendCompatibilityResult) -> str:
    """Return concise technical detail for one compatibility failure."""

    parts = [f"Status: {result.status.value}."]
    if result.installed_backend_version:
        parts.append(f"BackEnd: {result.installed_backend_version}.")
    if result.required_backend_version:
        parts.append(f"Required BackEnd: {result.required_backend_version}.")
    if result.installed_sugarcubes_version:
        parts.append(f"SugarCubes: {result.installed_sugarcubes_version}.")
    if result.required_sugarcubes_version:
        parts.append(f"Required SugarCubes: {result.required_sugarcubes_version}.")
    if result.repairable:
        parts.append("Repair can update the managed runtime when Substitute owns it.")
    return " ".join(parts)


def _managed_runtime_claims_workspace(
    configuration: ManagedRuntimeConfiguration,
    workspace: Path,
) -> bool:
    """Return whether active managed state claims the configured workspace."""

    if configuration.workspace_path is None:
        return configuration.validation_status is ManagedRuntimeValidationStatus.VALID
    try:
        claimed_workspace = Path(configuration.workspace_path).resolve()
        configured_workspace = workspace.resolve()
    except OSError:
        claimed_workspace = Path(configuration.workspace_path)
        configured_workspace = workspace
    return claimed_workspace == configured_workspace
