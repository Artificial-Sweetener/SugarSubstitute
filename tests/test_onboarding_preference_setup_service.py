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

"""Tests for onboarding preference setup persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.civitai import (
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.generation import (
    OutputPreferenceService,
)
from substitute.application.onboarding import (
    OnboardingCredentialDraft,
    OnboardingPreferenceSetupDraft,
    OnboardingPreferenceSetupFailure,
    OnboardingPreferenceSetupService,
)
from substitute.application.prompt_editor import PromptEditorPreferenceService
from substitute.domain.civitai import (
    CivitaiPreferences,
    CivitaiThumbnailSafetyPolicy,
    default_civitai_preferences,
)
from substitute.domain.danbooru.preferences import (
    DanbooruImageRatingPolicy,
    DanbooruPreferences,
    default_danbooru_preferences,
)
from substitute.domain.prompt import PromptEditorFeature, PromptEditorPreferences
from substitute.domain.generation import OutputOrganizationSettings, OutputPreferences
from substitute.infrastructure.persistence.file_prompt_editor_preference_repository import (
    _default_preferences,
)
from substitute.application.ports.civitai_credential_store import CredentialStoreStatus


def test_onboarding_preference_setup_saves_non_secret_choices(
    tmp_path: Path,
) -> None:
    """Onboarding choices should persist through the existing settings services."""

    output_repository = _OutputPreferenceRepository()
    danbooru_repository = _DanbooruPreferenceRepository()
    prompt_repository = _PromptEditorPreferenceRepository()
    civitai_repository = _CivitaiPreferenceRepository()
    service = _setup_service(
        output_repository=output_repository,
        danbooru_repository=danbooru_repository,
        prompt_repository=prompt_repository,
        civitai_repository=civitai_repository,
        default_output_root=tmp_path / "user" / "outputs",
    )
    custom_output_root = tmp_path / "Images"

    service.save_preferences(
        OnboardingPreferenceSetupDraft(
            output_root=custom_output_root,
            danbooru_tag_help_enabled=False,
            danbooru_safe_previews_enabled=False,
            danbooru_image_rating_policy=DanbooruImageRatingPolicy.ALL_RATINGS.value,
            civitai_model_help_enabled=False,
            civitai_downloads_enabled=False,
            civitai_safe_thumbnails_enabled=False,
            civitai_thumbnail_safety_policy=CivitaiThumbnailSafetyPolicy.ALLOW_ALL.value,
        )
    )

    assert output_repository.preferences.organization.output_root == custom_output_root
    assert (
        output_repository.preferences.organization.path_pattern
        == "{workflow}\\{source}"
    )
    assert (
        prompt_repository.preferences.user_allows(
            PromptEditorFeature.DANBOORU_URL_IMPORT
        )
        is False
    )
    assert (
        prompt_repository.preferences.user_allows(
            PromptEditorFeature.DANBOORU_WIKI_LOOKUP
        )
        is False
    )
    assert danbooru_repository.preferences.show_wiki_images is False
    assert (
        danbooru_repository.preferences.allowed_image_ratings
        is DanbooruImageRatingPolicy.ALL_RATINGS
    )
    assert civitai_repository.preferences.metadata_lookup_enabled is False
    assert civitai_repository.preferences.missing_model_lookup_enabled is False
    assert civitai_repository.preferences.downloads_enabled is False
    assert civitai_repository.preferences.thumbnail_downloads_enabled is False
    assert (
        civitai_repository.preferences.thumbnail_safety_policy
        is CivitaiThumbnailSafetyPolicy.DISABLED
    )
    assert (
        civitai_repository.preferences.download_path_pattern == "{creator}\\{file_name}"
    )


def test_onboarding_preference_setup_keeps_safe_preview_defaults(
    tmp_path: Path,
) -> None:
    """Enabled preview choices should force the safe CivitAI and Danbooru policies."""

    danbooru_repository = _DanbooruPreferenceRepository(
        DanbooruPreferences(
            schema_version="1",
            show_wiki_images=True,
            allowed_image_ratings=DanbooruImageRatingPolicy.ALL_RATINGS,
            background_refresh_enabled=False,
        )
    )
    civitai_repository = _CivitaiPreferenceRepository(
        default_civitai_preferences().with_thumbnail_safety_policy(
            CivitaiThumbnailSafetyPolicy.ALLOW_ALL
        )
    )
    service = _setup_service(
        danbooru_repository=danbooru_repository,
        civitai_repository=civitai_repository,
        default_output_root=tmp_path,
    )

    service.save_preferences(
        OnboardingPreferenceSetupDraft(
            output_root=None,
            danbooru_tag_help_enabled=True,
            danbooru_safe_previews_enabled=True,
            danbooru_image_rating_policy=(
                DanbooruImageRatingPolicy.SAFE_AND_QUESTIONABLE.value
            ),
            civitai_model_help_enabled=True,
            civitai_downloads_enabled=True,
            civitai_safe_thumbnails_enabled=True,
            civitai_thumbnail_safety_policy=(
                CivitaiThumbnailSafetyPolicy.ALLOW_SOFT.value
            ),
        )
    )

    assert danbooru_repository.preferences.show_wiki_images is True
    assert (
        danbooru_repository.preferences.allowed_image_ratings
        is DanbooruImageRatingPolicy.SAFE_AND_QUESTIONABLE
    )
    assert danbooru_repository.preferences.background_refresh_enabled is False
    assert (
        civitai_repository.preferences.thumbnail_safety_policy
        is CivitaiThumbnailSafetyPolicy.ALLOW_SOFT
    )


def test_onboarding_credential_save_uses_secure_store_only(tmp_path: Path) -> None:
    """CivitAI API keys should be saved through the credential service."""

    credential_store = _CredentialStore()
    service = _setup_service(
        credential_store=credential_store,
        default_output_root=tmp_path,
    )

    service.save_credentials(OnboardingCredentialDraft(" secret-token "))

    assert credential_store.saved_key == "secret-token"


def test_onboarding_credential_save_wraps_storage_failures(tmp_path: Path) -> None:
    """Credential storage failures should become onboarding-facing failures."""

    service = _setup_service(
        credential_store=_CredentialStore(raises=True),
        default_output_root=tmp_path,
    )

    with pytest.raises(OnboardingPreferenceSetupFailure):
        service.save_credentials(OnboardingCredentialDraft("secret-token"))


def _setup_service(
    *,
    output_repository: "_OutputPreferenceRepository | None" = None,
    danbooru_repository: "_DanbooruPreferenceRepository | None" = None,
    prompt_repository: "_PromptEditorPreferenceRepository | None" = None,
    civitai_repository: "_CivitaiPreferenceRepository | None" = None,
    credential_store: "_CredentialStore | None" = None,
    default_output_root: Path,
) -> OnboardingPreferenceSetupService:
    """Build a preference setup service from in-memory collaborators."""

    return OnboardingPreferenceSetupService(
        output_preference_service=OutputPreferenceService(
            output_repository or _OutputPreferenceRepository(),
            default_output_root=default_output_root,
        ),
        danbooru_preference_service=DanbooruPreferenceService(
            danbooru_repository or _DanbooruPreferenceRepository()
        ),
        prompt_editor_preference_service=PromptEditorPreferenceService(
            prompt_repository or _PromptEditorPreferenceRepository()
        ),
        civitai_preference_service=CivitaiPreferenceService(
            civitai_repository or _CivitaiPreferenceRepository()
        ),
        civitai_credential_service=CivitaiCredentialService(
            credential_store or _CredentialStore()
        ),
    )


class _OutputPreferenceRepository:
    """Store output organization preferences in memory."""

    def __init__(self) -> None:
        """Initialize with a non-default pattern to verify preservation."""

        self.preferences = OutputPreferences(
            organization=OutputOrganizationSettings(
                path_pattern="{workflow}\\{source}",
            )
        )

    def load(self) -> OutputPreferences:
        """Return the current output preferences."""

        return self.preferences

    def save(self, preferences: OutputPreferences) -> None:
        """Persist output preferences in memory."""

        self.preferences = preferences


class _DanbooruPreferenceRepository:
    """Store Danbooru preferences in memory."""

    def __init__(self, preferences: DanbooruPreferences | None = None) -> None:
        """Initialize with defaults unless a snapshot is supplied."""

        self.preferences = preferences or default_danbooru_preferences()

    def load(self) -> DanbooruPreferences:
        """Return the current Danbooru preferences."""

        return self.preferences

    def save(self, preferences: DanbooruPreferences) -> None:
        """Persist Danbooru preferences in memory."""

        self.preferences = preferences


class _PromptEditorPreferenceRepository:
    """Store prompt editor preferences in memory."""

    def __init__(self) -> None:
        """Initialize with registry defaults."""

        self.preferences = _default_preferences()

    def load(self) -> PromptEditorPreferences:
        """Return the current prompt editor preferences."""

        return self.preferences

    def save(self, preferences: PromptEditorPreferences) -> None:
        """Persist prompt editor preferences in memory."""

        self.preferences = preferences


class _CivitaiPreferenceRepository:
    """Store CivitAI preferences in memory."""

    def __init__(self, preferences: CivitaiPreferences | None = None) -> None:
        """Initialize with a non-default pattern to verify preservation."""

        self.preferences = (
            preferences
            or default_civitai_preferences().with_download_path_pattern(
                "{creator}\\{file_name}"
            )
        )

    def load(self) -> CivitaiPreferences:
        """Return the current CivitAI preferences."""

        return self.preferences

    def save(self, preferences: CivitaiPreferences) -> None:
        """Persist CivitAI preferences in memory."""

        self.preferences = preferences


class _CredentialStore:
    """Store a CivitAI API key in memory for tests."""

    def __init__(self, *, raises: bool = False) -> None:
        """Configure whether saving should fail."""

        self.raises = raises
        self.saved_key: str | None = None

    def status(self) -> CredentialStoreStatus:
        """Return a minimal available status object."""

        return CredentialStoreStatus(available=True, backend_name="test")

    def has_api_key(self) -> bool:
        """Return whether an API key was saved."""

        return self.saved_key is not None

    def load_api_key(self) -> str | None:
        """Return the saved API key."""

        return self.saved_key

    def save_api_key(self, api_key: str) -> None:
        """Save or reject one API key."""

        if self.raises:
            raise RuntimeError("secure storage unavailable")
        self.saved_key = api_key

    def clear_api_key(self) -> None:
        """Clear the saved API key."""

        self.saved_key = None
