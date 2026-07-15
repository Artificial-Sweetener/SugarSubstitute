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

"""Lazily export onboarding application services."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from substitute.application.onboarding.comfy_connection_settings_service import (
        ComfyConnectionReadinessChecks,
        ComfyConnectionSaveResult,
        ComfyConnectionSettingsDraft,
        ComfyConnectionSettingsService,
        ComfyConnectionSettingsSnapshot,
    )
    from substitute.application.onboarding.comfy_target_service import (
        ComfyTargetService,
    )
    from substitute.application.onboarding.flow_service import (
        OnboardingCompletionResult,
        OnboardingDraftState,
        OnboardingFlowService,
        OnboardingProvisioningFailure,
    )
    from substitute.application.onboarding.installation_service import (
        InstallationService,
    )
    from substitute.application.onboarding.managed_runtime_service import (
        ManagedRuntimeService,
    )
    from substitute.application.onboarding.managed_runtime_state_recorder import (
        ActiveSafeManagedRuntimeStateRecorder,
        ManagedRuntimeStateRecorder,
        NoOpManagedRuntimeStateRecorder,
        PendingManagedRuntimeStateRecorder,
    )
    from substitute.application.onboarding.onboarding_service import (
        OnboardingService,
    )
    from substitute.application.onboarding.preference_setup_service import (
        OnboardingCredentialDraft,
        OnboardingPreferenceSetupDraft,
        OnboardingPreferenceSetupFailure,
        OnboardingPreferenceSetupService,
    )
    from substitute.application.onboarding.readiness_service import (
        BootstrapReadinessService,
    )
    from substitute.application.onboarding.runtime_service import RuntimeService
    from substitute.application.onboarding.setup_transaction_service import (
        SetupTransactionOptions,
        SetupTransactionService,
    )
    from substitute.domain.onboarding import ComfyTargetMode

_LAZY_EXPORTS = {
    "BootstrapReadinessService": (
        "substitute.application.onboarding.readiness_service",
        "BootstrapReadinessService",
    ),
    "ComfyConnectionReadinessChecks": (
        "substitute.application.onboarding.comfy_connection_settings_service",
        "ComfyConnectionReadinessChecks",
    ),
    "ComfyConnectionSaveResult": (
        "substitute.application.onboarding.comfy_connection_settings_service",
        "ComfyConnectionSaveResult",
    ),
    "ComfyConnectionSettingsDraft": (
        "substitute.application.onboarding.comfy_connection_settings_service",
        "ComfyConnectionSettingsDraft",
    ),
    "ComfyConnectionSettingsService": (
        "substitute.application.onboarding.comfy_connection_settings_service",
        "ComfyConnectionSettingsService",
    ),
    "ComfyConnectionSettingsSnapshot": (
        "substitute.application.onboarding.comfy_connection_settings_service",
        "ComfyConnectionSettingsSnapshot",
    ),
    "ComfyTargetMode": ("substitute.domain.onboarding", "ComfyTargetMode"),
    "ComfyTargetService": (
        "substitute.application.onboarding.comfy_target_service",
        "ComfyTargetService",
    ),
    "InstallationService": (
        "substitute.application.onboarding.installation_service",
        "InstallationService",
    ),
    "ActiveSafeManagedRuntimeStateRecorder": (
        "substitute.application.onboarding.managed_runtime_state_recorder",
        "ActiveSafeManagedRuntimeStateRecorder",
    ),
    "ManagedRuntimeStateRecorder": (
        "substitute.application.onboarding.managed_runtime_state_recorder",
        "ManagedRuntimeStateRecorder",
    ),
    "ManagedRuntimeService": (
        "substitute.application.onboarding.managed_runtime_service",
        "ManagedRuntimeService",
    ),
    "NoOpManagedRuntimeStateRecorder": (
        "substitute.application.onboarding.managed_runtime_state_recorder",
        "NoOpManagedRuntimeStateRecorder",
    ),
    "OnboardingCompletionResult": (
        "substitute.application.onboarding.flow_service",
        "OnboardingCompletionResult",
    ),
    "OnboardingCredentialDraft": (
        "substitute.application.onboarding.preference_setup_service",
        "OnboardingCredentialDraft",
    ),
    "OnboardingDraftState": (
        "substitute.application.onboarding.flow_service",
        "OnboardingDraftState",
    ),
    "OnboardingFlowService": (
        "substitute.application.onboarding.flow_service",
        "OnboardingFlowService",
    ),
    "OnboardingPreferenceSetupDraft": (
        "substitute.application.onboarding.preference_setup_service",
        "OnboardingPreferenceSetupDraft",
    ),
    "OnboardingPreferenceSetupFailure": (
        "substitute.application.onboarding.preference_setup_service",
        "OnboardingPreferenceSetupFailure",
    ),
    "OnboardingPreferenceSetupService": (
        "substitute.application.onboarding.preference_setup_service",
        "OnboardingPreferenceSetupService",
    ),
    "OnboardingProvisioningFailure": (
        "substitute.application.onboarding.flow_service",
        "OnboardingProvisioningFailure",
    ),
    "OnboardingService": (
        "substitute.application.onboarding.onboarding_service",
        "OnboardingService",
    ),
    "RuntimeService": (
        "substitute.application.onboarding.runtime_service",
        "RuntimeService",
    ),
    "PendingManagedRuntimeStateRecorder": (
        "substitute.application.onboarding.managed_runtime_state_recorder",
        "PendingManagedRuntimeStateRecorder",
    ),
    "SetupTransactionOptions": (
        "substitute.application.onboarding.setup_transaction_service",
        "SetupTransactionOptions",
    ),
    "SetupTransactionService": (
        "substitute.application.onboarding.setup_transaction_service",
        "SetupTransactionService",
    ),
}

__all__ = [
    "BootstrapReadinessService",
    "ComfyConnectionReadinessChecks",
    "ComfyConnectionSaveResult",
    "ComfyConnectionSettingsDraft",
    "ComfyConnectionSettingsService",
    "ComfyConnectionSettingsSnapshot",
    "ComfyTargetMode",
    "ComfyTargetService",
    "InstallationService",
    "ActiveSafeManagedRuntimeStateRecorder",
    "ManagedRuntimeStateRecorder",
    "ManagedRuntimeService",
    "NoOpManagedRuntimeStateRecorder",
    "OnboardingCompletionResult",
    "OnboardingCredentialDraft",
    "OnboardingDraftState",
    "OnboardingFlowService",
    "OnboardingPreferenceSetupDraft",
    "OnboardingPreferenceSetupFailure",
    "OnboardingPreferenceSetupService",
    "OnboardingProvisioningFailure",
    "OnboardingService",
    "RuntimeService",
    "PendingManagedRuntimeStateRecorder",
    "SetupTransactionOptions",
    "SetupTransactionService",
]


def __getattr__(name: str) -> Any:
    """Resolve onboarding exports without importing unrelated services."""

    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as error:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from error
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
