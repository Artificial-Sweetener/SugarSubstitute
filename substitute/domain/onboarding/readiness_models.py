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

"""Define typed bootstrap readiness results used by startup routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BootstrapRoute(str, Enum):
    """Describe the top-level startup route selected after readiness assessment."""

    ONBOARDING = "onboarding"
    READY = "ready"
    REPAIR = "repair"


class ReadinessIssueCode(str, Enum):
    """Identify concrete readiness failures that bootstrap can explain to users."""

    INSTALLATION_CONFIG_MISSING = "installation_config_missing"
    INSTALLATION_CONFIG_INVALID = "installation_config_invalid"
    RUNTIME_CONFIG_MISSING = "runtime_config_missing"
    RUNTIME_CONFIG_INVALID = "runtime_config_invalid"
    RUNTIME_NOT_PROVISIONED = "runtime_not_provisioned"
    RUNTIME_PROVISIONING_INCOMPLETE = "runtime_provisioning_incomplete"
    RUNTIME_PYTHON_MISSING = "runtime_python_missing"
    TARGET_CONFIG_MISSING = "target_config_missing"
    TARGET_CONFIG_INVALID = "target_config_invalid"
    MANAGED_WORKSPACE_NOT_CONFIGURED = "managed_workspace_not_configured"
    MANAGED_WORKSPACE_NOT_INSTALLED = "managed_workspace_not_installed"
    MANAGED_WORKSPACE_NOT_LAUNCHABLE = "managed_workspace_not_launchable"
    MANAGED_WORKSPACE_NODEPACKS_MISSING = "managed_workspace_nodepacks_missing"
    MANAGED_WORKSPACE_NOT_VALIDATED = "managed_workspace_not_validated"
    MANAGED_WORKSPACE_FOREIGN_LISTENER_BLOCKED = (
        "managed_workspace_foreign_listener_blocked"
    )
    MANAGED_WORKSPACE_BACKEND_INVALID = "managed_workspace_backend_invalid"
    ATTACHED_WORKSPACE_MISSING = "attached_workspace_missing"
    TARGET_ENDPOINT_INVALID = "target_endpoint_invalid"
    TARGET_ENDPOINT_UNREACHABLE = "target_endpoint_unreachable"
    BACKEND_COMPATIBILITY_FAILED = "backend_compatibility_failed"
    SETUP_TRANSACTION_INTERRUPTED = "setup_transaction_interrupted"
    SETUP_TRANSACTION_FAILED = "setup_transaction_failed"
    SETUP_TRANSACTION_CORRUPT = "setup_transaction_corrupt"


@dataclass(frozen=True)
class ReadinessIssue:
    """Describe one explicit readiness problem and the route it implies."""

    code: ReadinessIssueCode
    summary: str
    detail: str


@dataclass(frozen=True)
class ReadinessAssessment:
    """Capture the selected bootstrap route and all discovered readiness issues."""

    route: BootstrapRoute
    issues: tuple[ReadinessIssue, ...]

    @property
    def is_ready(self) -> bool:
        """Return whether bootstrap can continue to the main shell."""

        return self.route is BootstrapRoute.READY
