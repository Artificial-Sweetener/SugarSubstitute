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

"""Contract tests for expressive Settings section icon assignments."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from substitute.application.about import (
    AboutInfoService,
    AboutInfoSnapshot,
)
from substitute.application.appearance import AppearanceRestartCoordinator
from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.application.cube_library import CubeLibraryManagementService
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.application.onboarding import ComfyConnectionSettingsService
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.application.prompt_editor import PromptEditorPreferenceService
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.appearance_runtime_protocol import (
    AppearanceRuntimeProtocol,
)
from substitute.presentation.settings.settings_catalog_builders import (
    ComfyUiSettingsContext,
    GenerationSettingsContext,
    ModelSourcesSettingsContext,
    PromptEditingSettingsContext,
    build_comfyui_search_catalog_page,
    build_generation_settings_page,
    build_model_sources_settings_page,
    build_prompt_editing_settings_page,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunner,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_workspace import (
    ABOUT_SECTION_ID,
    COMFYUI_SECTION_ID,
    LIBRARY_SECTION_ID,
    create_settings_workspace,
)
from substitute.presentation.settings.settings_workspace_panel import (
    SettingsPageDescriptor,
)
from tests.execution_testing import ImmediateTaskSubmitter


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for icon tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


_TASK_RUNNER_FACTORY: SettingsAsyncTaskRunnerFactory = _task_runner_factory


def test_non_appearance_catalog_pages_use_deliberate_app_icons() -> None:
    """Settings catalog pages outside excluded areas should avoid generic fallbacks."""

    generation_page = build_generation_settings_page(
        GenerationSettingsContext(
            generation_preview_service=cast(
                GenerationPreviewPreferenceService,
                object(),
            ),
            output_preference_service=cast(
                OutputPreferenceService,
                object(),
            ),
            civitai_preference_service=cast(CivitaiPreferenceService, object()),
            task_runner_factory=_TASK_RUNNER_FACTORY,
        )
    )
    prompt_page = build_prompt_editing_settings_page(
        PromptEditingSettingsContext(
            preference_service=cast(PromptEditorPreferenceService, object()),
            danbooru_preference_service=cast(DanbooruPreferenceService, object()),
            danbooru_cache_repository=cast(DanbooruCacheRepository, object()),
            wildcard_preference_service=None,
            wildcard_file_management_service=None,
            open_wildcard_management_modal=None,
            preferences_changed=None,
        )
    )
    model_sources_page = build_model_sources_settings_page(
        ModelSourcesSettingsContext(
            civitai_preference_service=cast(CivitaiPreferenceService, object()),
            civitai_credential_service=cast(CivitaiCredentialService, object()),
            civitai_cache_service=cast(CivitaiCacheService, object()),
        )
    )
    comfy_connection_page = build_comfyui_search_catalog_page(
        ComfyUiSettingsContext(
            connection_service=cast(ComfyConnectionSettingsService, object()),
            open_reconfigure_window=lambda: object(),
            task_runner_factory=_TASK_RUNNER_FACTORY,
        )
    )

    assert generation_page.icon is AppIcon.IMAGE_SPARKLE_20_REGULAR
    assert prompt_page.icon is AppIcon.TEXT_EFFECTS_SPARKLE_20_REGULAR
    assert model_sources_page.icon is AppIcon.GLOBE_DESKTOP_20_REGULAR
    assert comfy_connection_page.icon is AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR


def test_explicit_settings_workspace_pages_use_deliberate_app_icons() -> None:
    """Dynamic workspace pages should use the same application icon system."""

    app = _app()
    _ = app
    workspace = create_settings_workspace(
        comfy_environment_service=cast(ComfyEnvironmentService, object()),
        cube_library_management_service=cast(CubeLibraryManagementService, object()),
        about_info_service=cast(AboutInfoService, _AboutInfoService()),
        comfy_connection_settings_service=cast(
            ComfyConnectionSettingsService,
            object(),
        ),
        appearance_runtime=cast(AppearanceRuntimeProtocol, object()),
        appearance_restart_coordinator=cast(
            AppearanceRestartCoordinator,
            object(),
        ),
        prompt_editor_preference_service=cast(PromptEditorPreferenceService, object()),
        danbooru_preference_service=cast(DanbooruPreferenceService, object()),
        danbooru_cache_repository=cast(DanbooruCacheRepository, object()),
        civitai_preference_service=cast(CivitaiPreferenceService, object()),
        civitai_credential_service=cast(CivitaiCredentialService, object()),
        civitai_cache_service=cast(CivitaiCacheService, object()),
        generation_preview_preference_service=cast(
            GenerationPreviewPreferenceService,
            object(),
        ),
        output_preference_service=cast(
            OutputPreferenceService,
            object(),
        ),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_TASK_RUNNER_FACTORY,
    )
    descriptors = cast(
        dict[str, SettingsPageDescriptor],
        getattr(workspace.panel, "_page_descriptors"),
    )

    assert descriptors[ABOUT_SECTION_ID].icon is AppIcon.CUBE_20_FILLED
    assert descriptors[LIBRARY_SECTION_ID].icon is AppIcon.LIBRARY_20_REGULAR
    assert (
        descriptors[COMFYUI_SECTION_ID].icon
        is AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR
    )

    workspace.navigation_pane.close()
    workspace.panel.close()


class _AboutInfoService:
    """Return an empty About snapshot for workspace icon tests."""

    def placeholder_snapshot(self) -> AboutInfoSnapshot:
        """Return the initial empty About snapshot."""

        return _about_snapshot()

    def snapshot(self) -> AboutInfoSnapshot:
        """Return a refreshed empty About snapshot."""

        return _about_snapshot()


def _about_snapshot() -> AboutInfoSnapshot:
    """Return a minimal valid About snapshot."""

    return AboutInfoSnapshot(
        versions=(),
        project_summary="",
        supporters=(),
        special_thanks=(),
    )


def _app() -> QApplication:
    """Return the active QApplication or create one for widget-backed checks."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
