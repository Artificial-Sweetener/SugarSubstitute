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

"""Own localized onboarding window and navigation labels."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage, app_text

from substitute.presentation.onboarding.onboarding_models import (
    OnboardingFlowMode,
    OnboardingPageId,
)


def onboarding_window_title(flow_mode: OnboardingFlowMode) -> ApplicationMessage:
    """Return the onboarding window title for one entry mode."""

    if flow_mode is OnboardingFlowMode.REPAIR:
        return app_text("Substitute Repair")
    if flow_mode is OnboardingFlowMode.RECONFIGURE:
        return app_text("Substitute Reconfigure")
    return app_text("Substitute Setup")


def onboarding_rail_title(flow_mode: OnboardingFlowMode) -> ApplicationMessage:
    """Return the compact localized rail title for one entry mode."""

    if flow_mode is OnboardingFlowMode.REPAIR:
        return app_text("Repair")
    if flow_mode is OnboardingFlowMode.RECONFIGURE:
        return app_text("Reconfigure")
    return app_text("Setup")


def onboarding_primary_button_label(
    page_id: OnboardingPageId,
) -> ApplicationMessage:
    """Return the primary action text for the supplied page."""

    if page_id in {
        OnboardingPageId.WELCOME,
        OnboardingPageId.TARGET_MODE,
        OnboardingPageId.EXISTING_MODELS,
    }:
        return app_text("Continue")
    if page_id in {
        OnboardingPageId.MANAGED_LOCAL,
        OnboardingPageId.ATTACHED_LOCAL,
        OnboardingPageId.REMOTE,
        OnboardingPageId.FOLDERS,
    }:
        return app_text("Save and continue")
    if page_id is OnboardingPageId.MODEL_DOWNLOAD_REVIEW:
        return app_text("Confirm downloads")
    if page_id is OnboardingPageId.INTEGRATIONS:
        return app_text("Finish setup")
    return app_text("Continue")


__all__ = [
    "onboarding_primary_button_label",
    "onboarding_rail_title",
    "onboarding_window_title",
]
