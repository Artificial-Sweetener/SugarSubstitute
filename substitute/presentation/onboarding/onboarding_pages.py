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

"""Expose onboarding pages from their focused presentation owners."""

from substitute.presentation.onboarding.onboarding_completion_pages import (
    CompletionPage,
    ProvisioningPage,
)
from substitute.presentation.onboarding.onboarding_connection_settings import (
    ManagedRuntimeSummaryPanel,
    TargetEndpointFields,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingFieldBlock,
    OnboardingHeroPanel,
    OnboardingInfoPanel,
    OnboardingPageFrame,
    OnboardingSectionPanel,
    TargetModeCard,
    TargetModePresentation,
)
from substitute.presentation.onboarding.onboarding_preference_pages import (
    FolderSetupPage,
    IntegrationsPage,
)
from substitute.presentation.onboarding.onboarding_target_pages import (
    AttachedLocalPage,
    InstallRootPage,
    ManagedLocalPage,
    RemotePage,
    TargetModePage,
)

__all__ = [
    "AttachedLocalPage",
    "CompletionPage",
    "FolderSetupPage",
    "InstallRootPage",
    "IntegrationsPage",
    "ManagedLocalPage",
    "ManagedRuntimeSummaryPanel",
    "OnboardingFieldBlock",
    "OnboardingHeroPanel",
    "OnboardingInfoPanel",
    "OnboardingPageFrame",
    "OnboardingSectionPanel",
    "ProvisioningPage",
    "RemotePage",
    "TargetEndpointFields",
    "TargetModeCard",
    "TargetModePage",
    "TargetModePresentation",
]
