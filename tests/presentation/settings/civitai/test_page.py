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

"""Verify CivitAI Settings page behavior."""

from __future__ import annotations
from pathlib import Path
from typing import Any, cast
from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.ports.civitai_credential_store import (
    CredentialStoreStatus,
)
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.presentation.settings.civitai_page import CivitaiSettingsPage
from substitute.infrastructure.persistence import (
    FileCivitaiPreferenceRepository,
)
from tests.presentation.settings.appearance.support import (
    label_texts,
)
from tests.presentation.settings.civitai.support import (
    MemoryCivitaiCredentialStore,
    RecordingCivitaiCacheRepository,
)
from tests.presentation.settings.generation.support import (
    application,
)


def test_civitai_settings_page_persists_policy_credentials_and_cache(
    tmp_path: Path,
) -> None:
    """CivitAI Settings should own preferences, credentials, and cache actions."""

    application()
    preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings")
    )
    credential_store = MemoryCivitaiCredentialStore()
    credential_service = CivitaiCredentialService(credential_store)
    cache_repository = RecordingCivitaiCacheRepository()
    scheduled_refreshes: list[str] = []
    page = CivitaiSettingsPage(
        preference_service=preference_service,
        credential_service=credential_service,
        cache_service=CivitaiCacheService(
            cache_repository,
            schedule_metadata_refresh=lambda: scheduled_refreshes.append("refresh"),
        ),
    )

    cast(Any, page)._set_metadata_lookup_enabled(False)
    cast(Any, page)._set_missing_model_lookup_enabled(False)
    cast(Any, page)._set_thumbnail_downloads_enabled(False)
    combo = cast(Any, page)._thumbnail_policy_combo
    combo.setCurrentIndex(2)
    cast(Any, page)._set_thumbnail_safety_policy(2)
    cast(Any, page)._set_downloads_enabled(False)
    cast(Any, page)._api_key_edit.setText("secret-token")
    cast(Any, page)._set_api_key()
    cast(Any, page)._clear_thumbnails()
    cast(Any, page)._clear_metadata()
    cast(Any, page)._refresh_metadata()

    preferences = preference_service.load_preferences()
    assert preferences.metadata_lookup_enabled is False
    assert preferences.missing_model_lookup_enabled is False
    assert preferences.thumbnail_downloads_enabled is False
    assert (
        preferences.thumbnail_safety_policy is CivitaiThumbnailSafetyPolicy.ALLOW_SOFT
    )
    assert preferences.downloads_enabled is False
    assert credential_store.saved_key == "secret-token"
    assert "4 bytes" in page.cache_summary_text()
    assert cache_repository.actions == ["clear-thumbnails", "clear-metadata"]
    assert scheduled_refreshes == ["refresh"]


def test_civitai_settings_page_download_organization_preview_and_autocomplete(
    tmp_path: Path,
) -> None:
    """CivitAI Settings should expose download organization pattern controls."""

    app = application()
    preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings"),
        preview_comfy_root=tmp_path / "diffusion_models",
    )
    page = CivitaiSettingsPage(
        preference_service=preference_service,
        credential_service=CivitaiCredentialService(MemoryCivitaiCredentialStore()),
        cache_service=CivitaiCacheService(RecordingCivitaiCacheRepository()),
    )
    page.show()
    app.processEvents()

    labels = label_texts(page)
    assert "Model folder pattern" in labels
    assert "Download path preview" in labels
    assert page.download_path_preview_text() == str(
        tmp_path / "diffusion_models" / "Anima" / "anima_baseV10.safetensors"
    )

    page.download_path_pattern_edit.setFocus()
    page.set_download_path_pattern("{base")
    page.download_path_pattern_edit.setCursorPosition(len("{base"))
    assert page.download_token_autocomplete is not None
    page.download_token_autocomplete.refresh()
    app.processEvents()

    assert page.download_token_autocomplete.is_visible() is True
    assert page.download_token_autocomplete.visible_tokens() == ("{base_model}",)
    assert page.download_token_autocomplete.accept_current() is True
    assert page.download_path_pattern_edit.text() == "{base_model}"

    page.set_download_path_pattern("{creator}\\{file_name}")
    page.download_path_pattern_edit.editingFinished.emit()
    app.processEvents()

    assert (
        preference_service.load_preferences().download_path_pattern
        == "{creator}\\{file_name}"
    )
    page.close()


def test_civitai_settings_page_reports_unavailable_linux_credentials(
    tmp_path: Path,
) -> None:
    """CivitAI Settings should explain Linux secure-storage remediation."""

    application()
    preference_service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings")
    )
    credential_store = MemoryCivitaiCredentialStore(
        status=CredentialStoreStatus(
            available=False,
            backend_name="Linux Secret Service/KWallet",
            reason="No compatible operating-system credential store is available.",
            remediation=(
                "Install and enable GNOME Keyring, KWallet, or another "
                "Secret Service-compatible keyring through your distribution's "
                "package manager, then sign in or unlock it and restart Substitute."
            ),
        )
    )
    page = CivitaiSettingsPage(
        preference_service=preference_service,
        credential_service=CivitaiCredentialService(credential_store),
        cache_service=CivitaiCacheService(RecordingCivitaiCacheRepository()),
    )

    cast(Any, page)._api_key_edit.setText("secret-token")
    cast(Any, page)._set_api_key()

    assert "Secure credential storage is unavailable" in page.api_key_status_text()
    assert "GNOME Keyring" in page.api_key_status_text()
    assert "package manager" in page.api_key_status_text()
    assert credential_store.saved_key is None
