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

"""Reconcile ComfyUI dependencies according to workspace ownership."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.localization import app_text, render_source_application_text

from substitute.infrastructure.comfy.comfy_checkout_contract import (
    ComfyCheckoutContract,
    ComfyCheckoutSnapshot,
)
from substitute.infrastructure.comfy.managed_install_commands import (
    install_workspace_requirements,
)
from substitute.infrastructure.comfy.python_requirements_probe import (
    PythonRequirementsAssessment,
    PythonRequirementsProbe,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.workspace_dependency_reconciler")


class AttachedComfyRequirementsError(RuntimeError):
    """Report user-owned ComfyUI dependencies that require external repair."""


class RequirementsProbe(Protocol):
    """Assess one requirements file in its target Python."""

    def assess(
        self,
        *,
        requirements_path: Path,
        python_executable: Path,
        workspace: Path,
        env: Mapping[str, str] | None = None,
    ) -> PythonRequirementsAssessment:
        """Return live requirement satisfaction evidence."""


class WorkspaceRequirementsInstaller(Protocol):
    """Mutate dependencies in an app-owned ComfyUI environment."""

    def install(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Install the checkout-owned ComfyUI requirements."""


class ComfyRequirementsInstaller:
    """Adapt the managed requirements command to reconciliation ownership."""

    def install(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Install ComfyUI requirements into its app-owned Python."""

        install_workspace_requirements(
            python_executable,
            workspace=workspace,
            on_log=on_log,
            env=dict(env) if env is not None else None,
        )


@dataclass(frozen=True, slots=True)
class DependencyReconciliationResult:
    """Describe the validated checkout and whether dependencies changed."""

    snapshot: ComfyCheckoutSnapshot
    changed: bool


@dataclass(slots=True)
class ComfyWorkspaceDependencyReconciler:
    """Converge app-owned dependencies and validate user-owned dependencies."""

    requirements_probe: RequirementsProbe
    installer: WorkspaceRequirementsInstaller

    @classmethod
    def create_default(cls) -> ComfyWorkspaceDependencyReconciler:
        """Build the production dependency reconciliation composition."""

        return cls(
            requirements_probe=PythonRequirementsProbe(),
            installer=ComfyRequirementsInstaller(),
        )

    def reconcile_managed(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        on_log: LogCallback | None = None,
        env: Mapping[str, str] | None = None,
    ) -> DependencyReconciliationResult:
        """Repair managed requirements and validate the resulting environment."""

        contract = ComfyCheckoutContract(workspace)
        snapshot = contract.capture()
        assessment = self._assess(
            contract=contract,
            python_executable=python_executable,
            env=env,
        )
        if assessment.satisfied:
            log_info(
                _LOGGER,
                "Managed ComfyUI requirements are current",
                comfy_version=snapshot.version,
                requirements_digest=snapshot.comfy_requirements_digest,
            )
            return DependencyReconciliationResult(snapshot, changed=False)
        log_info(
            _LOGGER,
            "Reconciling managed ComfyUI requirements",
            comfy_version=snapshot.version,
            requirements_digest=snapshot.comfy_requirements_digest,
            mismatch=assessment.summary,
        )
        self.installer.install(
            workspace=workspace,
            python_executable=python_executable,
            on_log=on_log,
            env=env,
        )
        validated = self._assess(
            contract=contract,
            python_executable=python_executable,
            env=env,
        )
        if not validated.satisfied:
            raise RuntimeError(
                "Managed ComfyUI requirements remain unsatisfied after repair. "
                + validated.summary
            )
        return DependencyReconciliationResult(snapshot, changed=True)

    def validate_attached(
        self,
        *,
        workspace: Path,
        python_executable: Path,
        env: Mapping[str, str] | None = None,
    ) -> DependencyReconciliationResult:
        """Validate user-owned ComfyUI dependencies without mutating them."""

        contract = ComfyCheckoutContract(workspace)
        snapshot = contract.capture()
        assessment = self._assess(
            contract=contract,
            python_executable=python_executable,
            env=env,
        )
        if assessment.satisfied:
            return DependencyReconciliationResult(snapshot, changed=False)
        log_warning(
            _LOGGER,
            "Attached ComfyUI requirements require user repair",
            comfy_version=snapshot.version,
            requirements_digest=snapshot.comfy_requirements_digest,
            mismatch=assessment.summary,
        )
        raise AttachedComfyRequirementsError(
            render_source_application_text(
                app_text(
                    "The attached ComfyUI environment does not satisfy its updated "
                    "requirements. Repair that environment before continuing. %1",
                    assessment.summary,
                )
            )
        )

    def _assess(
        self,
        *,
        contract: ComfyCheckoutContract,
        python_executable: Path,
        env: Mapping[str, str] | None,
    ) -> PythonRequirementsAssessment:
        """Assess the live environment against the checkout-owned requirements."""

        return self.requirements_probe.assess(
            requirements_path=contract.requirements_path,
            python_executable=python_executable,
            workspace=contract.workspace,
            env=env,
        )


def reconcile_managed_workspace_dependencies(
    *,
    workspace: Path,
    python_executable: Path,
    on_log: LogCallback | None = None,
    env: Mapping[str, str] | None = None,
) -> DependencyReconciliationResult:
    """Reconcile one managed workspace through the production composition."""

    return ComfyWorkspaceDependencyReconciler.create_default().reconcile_managed(
        workspace=workspace,
        python_executable=python_executable,
        on_log=on_log,
        env=env,
    )


def validate_attached_workspace_dependencies(
    *,
    workspace: Path,
    python_executable: Path,
    env: Mapping[str, str] | None = None,
) -> DependencyReconciliationResult:
    """Validate one attached workspace through the production composition."""

    return ComfyWorkspaceDependencyReconciler.create_default().validate_attached(
        workspace=workspace,
        python_executable=python_executable,
        env=env,
    )


__all__ = [
    "AttachedComfyRequirementsError",
    "ComfyRequirementsInstaller",
    "ComfyWorkspaceDependencyReconciler",
    "DependencyReconciliationResult",
    "RequirementsProbe",
    "WorkspaceRequirementsInstaller",
    "reconcile_managed_workspace_dependencies",
    "validate_attached_workspace_dependencies",
]
