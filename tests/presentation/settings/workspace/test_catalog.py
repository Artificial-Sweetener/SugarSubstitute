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

"""Verify integrated Settings catalog composition."""

from __future__ import annotations
from pathlib import Path
from typing import cast
import pytest
from tests.support.localization import stub_translation_manager
from substitute.application.about import (
    AboutInfoService,
)
from substitute.application.appearance import (
    AppearanceRestartCoordinator,
)
from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.application.cube_library import CubeLibraryManagementService
from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.application.onboarding import (
    ComfyConnectionSettingsService,
)
from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.comfy_environment_page import ComfyEnvironmentPage
from substitute.presentation.settings.cube_library_page import CubeLibrarySettingsPage
from substitute.presentation.settings.generation_page import GenerationSettingsPage
from substitute.presentation.settings.settings_workspace import (
    ABOUT_SECTION_ID,
    create_settings_workspace,
)
from substitute.presentation.settings.prompt_editor_page import PromptEditorSettingsPage
from substitute.infrastructure.persistence import (
    FileCivitaiPreferenceRepository,
    FileDanbooruPreferenceRepository,
)
from tests.support.danbooru_cache_repository import (
    build_danbooru_cache_repository,
)
from tests.presentation.settings.appearance.support import (
    AppearanceRuntime,
    RecordingAppearanceRestartCoordinator,
)
from tests.presentation.settings.civitai.support import (
    MemoryCivitaiCredentialStore,
    RecordingCivitaiCacheRepository,
)
from tests.presentation.settings.generation.support import (
    MemoryOutputPreferenceRepository,
    MemoryPreviewPreferenceRepository,
    application,
    immediate_task_runner,
)
from tests.presentation.settings.workspace.support import (
    ConnectionSettingsService,
    PromptPreferenceService,
    StaticAboutInfoService,
    label_texts as workspace_label_texts,
)


def test_settings_workspace_uses_user_intent_navigation_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integrated Settings should expose user-intent pages in priority order."""

    application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)

    widgets = create_settings_workspace(
        comfy_environment_service=cast(ComfyEnvironmentService, object()),
        cube_library_management_service=cast(CubeLibraryManagementService, object()),
        about_info_service=cast(AboutInfoService, StaticAboutInfoService()),
        localization_manager=stub_translation_manager(),
        comfy_connection_settings_service=cast(
            ComfyConnectionSettingsService,
            ConnectionSettingsService(),
        ),
        appearance_runtime=AppearanceRuntime(),
        appearance_restart_coordinator=cast(
            AppearanceRestartCoordinator,
            RecordingAppearanceRestartCoordinator(),
        ),
        prompt_editor_preference_service=cast(
            PromptEditorPreferenceService,
            PromptPreferenceService(),
        ),
        danbooru_preference_service=DanbooruPreferenceService(
            FileDanbooruPreferenceRepository(tmp_path / "config")
        ),
        danbooru_cache_repository=build_danbooru_cache_repository(tmp_path / "state"),
        civitai_preference_service=CivitaiPreferenceService(
            FileCivitaiPreferenceRepository(tmp_path / "settings")
        ),
        civitai_credential_service=CivitaiCredentialService(
            MemoryCivitaiCredentialStore()
        ),
        civitai_cache_service=CivitaiCacheService(RecordingCivitaiCacheRepository()),
        generation_preview_preference_service=GenerationPreviewPreferenceService(
            MemoryPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            MemoryOutputPreferenceRepository(),
            default_output_root=tmp_path / "outputs",
        ),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=immediate_task_runner,
    )

    assert widgets.navigation_pane.page_ids() == (
        "about",
        "generation",
        "prompt_editing",
        "model_sources",
        "library",
        "comfyui",
        "appearance",
    )
    assert widgets.panel.page_ids() == widgets.navigation_pane.page_ids()
    assert widgets.panel.active_page_id() == ABOUT_SECTION_ID


def test_settings_pages_leave_section_titles_to_workspace_panel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings pages should leave section title text to the workspace panel."""

    application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    connection_page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, ConnectionSettingsService()),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=immediate_task_runner,
    )
    environment_page = ComfyEnvironmentPage(
        cast(ComfyEnvironmentService, object()),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=immediate_task_runner,
    )
    prompt_page = PromptEditorSettingsPage(
        preference_service=cast(
            PromptEditorPreferenceService,
            PromptPreferenceService(),
        ),
    )
    generation_page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(
            MemoryPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            MemoryOutputPreferenceRepository(),
            default_output_root=tmp_path / "outputs",
        ),
        task_runner_factory=immediate_task_runner,
    )

    assert "Comfy Connection" not in workspace_label_texts(connection_page)
    assert "Comfy Environment" not in workspace_label_texts(environment_page)
    assert "Generation" not in workspace_label_texts(generation_page)
    assert "Prompt Editing" not in workspace_label_texts(prompt_page)
