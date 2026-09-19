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

"""Apply onboarding preferences and prepare the post-setup runtime launch."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.onboarding.preference_setup_service import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
    OnboardingPreferenceSetupFailure,
)
from substitute.domain.onboarding import RuntimeConfiguration
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.onboarding.setup_application")


class SetupPreferenceSelection(Protocol):
    """Describe the non-secret onboarding selections persisted before setup."""

    @property
    def output_root(self) -> Path | None:
        """Return the selected output root."""

    @property
    def output_root_uses_default(self) -> bool:
        """Return whether the default output root remains selected."""

    @property
    def danbooru_tag_help_enabled(self) -> bool:
        """Return whether Danbooru tag help is enabled."""

    @property
    def danbooru_safe_previews_enabled(self) -> bool:
        """Return whether safe Danbooru previews are enabled."""

    @property
    def danbooru_image_rating_policy(self) -> str:
        """Return the selected Danbooru image policy."""

    @property
    def civitai_model_help_enabled(self) -> bool:
        """Return whether CivitAI model help is enabled."""

    @property
    def civitai_downloads_enabled(self) -> bool:
        """Return whether CivitAI downloads are enabled."""

    @property
    def civitai_safe_thumbnails_enabled(self) -> bool:
        """Return whether CivitAI thumbnails are enabled."""

    @property
    def civitai_thumbnail_safety_policy(self) -> str:
        """Return the selected CivitAI thumbnail policy."""


class PreferenceSetupService(Protocol):
    """Persist onboarding preferences and optional credentials."""

    def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
        """Persist non-secret onboarding preferences."""

    def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
        """Persist explicitly supplied onboarding credentials."""


class RuntimeLaunchCommandBuilder(Protocol):
    """Build the application launch command for a prepared runtime."""

    def build_launch_command(
        self,
        runtime: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> Sequence[str]:
        """Return the command that starts the prepared application."""


class OnboardingPreferenceApplication:
    """Own persistence of onboarding preferences and optional credentials."""

    def save_setup(
        self,
        *,
        service: PreferenceSetupService,
        selection: SetupPreferenceSelection,
    ) -> None:
        """Persist non-secret setup choices with onboarding-friendly failures."""

        try:
            service.save_preferences(
                OnboardingPreferenceSetupDraft(
                    output_root=(
                        None
                        if selection.output_root_uses_default
                        else selection.output_root
                    ),
                    danbooru_tag_help_enabled=selection.danbooru_tag_help_enabled,
                    danbooru_safe_previews_enabled=(
                        selection.danbooru_safe_previews_enabled
                    ),
                    danbooru_image_rating_policy=(
                        selection.danbooru_image_rating_policy
                    ),
                    civitai_model_help_enabled=selection.civitai_model_help_enabled,
                    civitai_downloads_enabled=selection.civitai_downloads_enabled,
                    civitai_safe_thumbnails_enabled=(
                        selection.civitai_safe_thumbnails_enabled
                    ),
                    civitai_thumbnail_safety_policy=(
                        selection.civitai_thumbnail_safety_policy
                    ),
                )
            )
        except OnboardingPreferenceSetupFailure as error:
            from substitute.application.onboarding.flow_contracts import (
                OnboardingProvisioningFailure,
            )

            raise OnboardingProvisioningFailure(
                headline=app_text("Substitute couldn't save these setup choices"),
                user_message=app_text(
                    "Substitute couldn't save one of the folder or helper settings."
                ),
                technical_detail=str(error).strip() or type(error).__name__,
                remediation_steps=(
                    app_text("Review the folder choices and try again."),
                    app_text(
                        "You can also finish setup with the defaults and adjust Settings later."
                    ),
                ),
            ) from error

    def save_optional_credentials(
        self,
        *,
        service: PreferenceSetupService,
        credential_draft: OnboardingCredentialDraft | None,
        on_log: Callable[[ApplicationText], None],
    ) -> None:
        """Save optional credentials without failing completed core setup."""

        if credential_draft is None:
            return
        try:
            service.save_credentials(credential_draft)
        except OnboardingPreferenceSetupFailure as error:
            log_warning(
                _LOGGER,
                "Optional CivitAI API key could not be saved during onboarding.",
                error=error,
            )
            on_log(
                app_text(
                    "CivitAI API key could not be saved. You can add it later in Settings."
                )
            )


class OnboardingRuntimeLaunchPlanner:
    """Own construction of the launch command after successful provisioning."""

    def build(
        self,
        *,
        runtime_service: RuntimeLaunchCommandBuilder,
        runtime: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> tuple[str, ...]:
        """Return an immutable application launch command."""

        return tuple(runtime_service.build_launch_command(runtime, entrypoint_path))


__all__ = [
    "OnboardingPreferenceApplication",
    "OnboardingRuntimeLaunchPlanner",
    "PreferenceSetupService",
    "RuntimeLaunchCommandBuilder",
    "SetupPreferenceSelection",
]
