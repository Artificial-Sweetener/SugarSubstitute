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

"""Export onboarding domain models."""

from substitute.domain.onboarding.models import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
    ManagedRuntimeLaunchStatus,
    ManagedRuntimeStability,
    ManagedRuntimeValidationStatus,
)
from substitute.domain.onboarding.readiness_models import (
    BootstrapRoute,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
)
from substitute.domain.onboarding.setup_transaction_models import (
    SetupTransaction,
    SetupTransactionFailure,
    SetupTransactionMode,
    SetupTransactionStatus,
)

__all__ = [
    "BootstrapRoute",
    "ComfyEndpoint",
    "ComfyTargetConfiguration",
    "ComfyTargetMode",
    "InstallationConfiguration",
    "InstallationContext",
    "ManagedRuntimeConfiguration",
    "ManagedRuntimeLaunchStatus",
    "ManagedRuntimeStability",
    "ManagedRuntimeValidationStatus",
    "ReadinessAssessment",
    "ReadinessIssue",
    "ReadinessIssueCode",
    "RuntimeBootstrapStatus",
    "RuntimeConfiguration",
    "SetupTransaction",
    "SetupTransactionFailure",
    "SetupTransactionMode",
    "SetupTransactionStatus",
]
