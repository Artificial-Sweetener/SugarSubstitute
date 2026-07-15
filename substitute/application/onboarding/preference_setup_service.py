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

"""Persist first-run onboarding preferences through existing settings services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.civitai import (
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.generation import (
    OutputOrganizationPreferences,
    OutputOrganizationPreferenceService,
)
from substitute.application.prompt_editor import PromptEditorPreferenceService
from substitute.domain.civitai import CivitaiPreferences, CivitaiThumbnailSafetyPolicy
from substitute.domain.danbooru.preferences import (
    DanbooruImageRatingPolicy,
    DanbooruPreferences,
)
from substitute.domain.prompt import PromptEditorFeature


@dataclass(frozen=True)
class OnboardingPreferenceSetupDraft:
    """Capture non-secret onboarding preferences selected in the wizard."""

    output_root: Path | None
    danbooru_tag_help_enabled: bool
    danbooru_safe_previews_enabled: bool
    danbooru_image_rating_policy: str
    civitai_model_help_enabled: bool
    civitai_downloads_enabled: bool
    civitai_safe_thumbnails_enabled: bool
    civitai_thumbnail_safety_policy: str


@dataclass(frozen=True)
class OnboardingCredentialDraft:
    """Capture optional in-memory onboarding credentials."""

    civitai_api_key: str = ""


class OnboardingPreferenceSetupFailure(RuntimeError):
    """Raised when onboarding preference persistence cannot complete."""


@dataclass
class OnboardingPreferenceSetupService:
    """Save onboarding choices through the existing preference owners."""

    output_organization_service: OutputOrganizationPreferenceService
    danbooru_preference_service: DanbooruPreferenceService
    prompt_editor_preference_service: PromptEditorPreferenceService
    civitai_preference_service: CivitaiPreferenceService
    civitai_credential_service: CivitaiCredentialService

    def save_preferences(self, draft: OnboardingPreferenceSetupDraft) -> None:
        """Persist non-secret onboarding choices."""

        self._save_output_preferences(draft.output_root)
        self._save_prompt_editor_preferences(draft.danbooru_tag_help_enabled)
        self._save_danbooru_preferences(
            show_wiki_images=draft.danbooru_safe_previews_enabled,
            image_rating_policy=draft.danbooru_image_rating_policy,
        )
        self._save_civitai_preferences(draft)

    def save_credentials(self, draft: OnboardingCredentialDraft) -> None:
        """Persist optional onboarding credentials through secure storage."""

        api_key = draft.civitai_api_key.strip()
        if not api_key:
            return
        try:
            self.civitai_credential_service.save_api_key(api_key)
        except Exception as error:
            raise OnboardingPreferenceSetupFailure(
                "Substitute couldn't save the CivitAI API key. You can add it later in Settings."
            ) from error

    def _save_output_preferences(self, output_root: Path | None) -> None:
        """Persist output root while preserving the user's path pattern."""

        current = self.output_organization_service.load_preferences()
        result = self.output_organization_service.save_preferences(
            OutputOrganizationPreferences(
                output_root=output_root,
                path_pattern=current.path_pattern,
            )
        )
        if not result.succeeded:
            raise OnboardingPreferenceSetupFailure(result.message)

    def _save_prompt_editor_preferences(self, tag_help_enabled: bool) -> None:
        """Persist Danbooru prompt editor feature toggles."""

        preferences = self.prompt_editor_preference_service.load_preferences()
        preferences = preferences.with_feature_allowed(
            PromptEditorFeature.DANBOORU_URL_IMPORT,
            tag_help_enabled,
        )
        preferences = preferences.with_feature_allowed(
            PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
            tag_help_enabled,
        )
        self.prompt_editor_preference_service.save_preferences(preferences)

    def _save_danbooru_preferences(
        self,
        *,
        show_wiki_images: bool,
        image_rating_policy: str,
    ) -> None:
        """Persist Danbooru viewer rating choices while preserving refresh policy."""

        current = self.danbooru_preference_service.load_preferences()
        preferences = DanbooruPreferences(
            schema_version=current.schema_version,
            show_wiki_images=show_wiki_images,
            allowed_image_ratings=DanbooruImageRatingPolicy(image_rating_policy),
            background_refresh_enabled=current.background_refresh_enabled,
        )
        self.danbooru_preference_service.save_preferences(preferences)

    def _save_civitai_preferences(
        self,
        draft: OnboardingPreferenceSetupDraft,
    ) -> None:
        """Persist CivitAI helper choices while preserving download organization."""

        current = self.civitai_preference_service.load_preferences()
        thumbnail_policy = (
            CivitaiThumbnailSafetyPolicy(draft.civitai_thumbnail_safety_policy)
            if draft.civitai_safe_thumbnails_enabled
            else CivitaiThumbnailSafetyPolicy.DISABLED
        )
        preferences = CivitaiPreferences(
            schema_version=current.schema_version,
            metadata_lookup_enabled=draft.civitai_model_help_enabled,
            missing_model_lookup_enabled=draft.civitai_model_help_enabled,
            thumbnail_downloads_enabled=draft.civitai_safe_thumbnails_enabled,
            thumbnail_safety_policy=thumbnail_policy,
            downloads_enabled=draft.civitai_downloads_enabled,
            download_path_pattern=current.download_path_pattern,
        )
        self.civitai_preference_service.save_preferences(preferences)


__all__ = [
    "OnboardingCredentialDraft",
    "OnboardingPreferenceSetupDraft",
    "OnboardingPreferenceSetupFailure",
    "OnboardingPreferenceSetupService",
]
