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

"""Compose deterministic services for integrated Settings workspace tests."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QWidget

from substitute.application.about import (
    AboutInfoService,
    AboutInfoSnapshot,
    AboutVersionRow,
    AboutVersionStatus,
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
from substitute.application.onboarding import (
    ComfyConnectionSettingsService,
    ComfyConnectionSettingsSnapshot,
)
from substitute.application.prompt_editor.features.definitions import (
    default_prompt_feature_preferences,
)
from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.domain.prompt.preferences.models import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorPreferences,
)
from substitute.infrastructure.persistence import (
    FileCivitaiPreferenceRepository,
    FileDanbooruPreferenceRepository,
)
from substitute.presentation.settings.settings_workspace import (
    SettingsWorkspaceWidgets,
    create_settings_workspace,
)
from tests.support.localization import stub_translation_manager
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
    immediate_task_runner,
)
from tests.support.danbooru_cache_repository import build_danbooru_cache_repository
from tests.support.qt.semantic_wait import wait_for_qt_signal


class RefreshableWidget(QWidget):
    """Record integrated Settings page refresh calls."""

    def __init__(self) -> None:
        """Create a refresh-counting widget."""

        super().__init__()
        self.refresh_count = 0

    def refresh(self) -> None:
        """Record a refresh call."""

        self.refresh_count += 1


class PromptPreferenceService:
    """Expose stable default prompt preferences."""

    def __init__(self) -> None:
        """Initialize registry-default preferences."""

        self._preferences = PromptEditorPreferences(
            schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
            user_allowed_features=default_prompt_feature_preferences(),
        )

    def load_preferences(self) -> PromptEditorPreferences:
        """Return prompt feature preferences."""

        return self._preferences

    def set_feature_allowed(
        self,
        feature: object,
        allowed: bool,
    ) -> PromptEditorPreferences:
        """Accept a feature policy change while retaining defaults."""

        _ = (feature, allowed)
        return self._preferences


class ConnectionSettingsService:
    """Return a stable managed-local connection snapshot."""

    def load_snapshot(self) -> ComfyConnectionSettingsSnapshot:
        """Return a configured managed ComfyUI target."""

        return ComfyConnectionSettingsSnapshot(
            target=ComfyTargetConfiguration(
                mode=ComfyTargetMode.MANAGED_LOCAL,
                endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
                workspace_path=None,
                install_owned=True,
                launch_owned=True,
            ),
            persisted_exists=True,
            status_message="Substitute is configured to use managed ComfyUI.",
            can_test_endpoint=True,
        )


class StaticAboutInfoService:
    """Return deterministic About snapshots."""

    def __init__(self) -> None:
        """Initialize without snapshot refreshes."""

        self.snapshot_calls = 0

    def placeholder_snapshot(self) -> AboutInfoSnapshot:
        """Return a placeholder snapshot."""

        return about_snapshot("placeholder")

    def snapshot(self) -> AboutInfoSnapshot:
        """Record and return a refreshed snapshot."""

        self.snapshot_calls += 1
        return about_snapshot("refreshed")


def about_snapshot(version_value: str) -> AboutInfoSnapshot:
    """Build one deterministic About snapshot."""

    return AboutInfoSnapshot(
        versions=(
            AboutVersionRow(
                component_key="SugarSubstitute",
                label="SugarSubstitute",
                value=version_value,
                status=AboutVersionStatus.AVAILABLE,
            ),
        ),
        project_summary="About-only project copy",
        supporters=("About-only patron",),
        special_thanks=("About-only special thanks",),
    )


def build_settings_workspace(tmp_path: Path) -> SettingsWorkspaceWidgets:
    """Build the integrated workspace with isolated deterministic services."""

    return create_settings_workspace(
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
            FileDanbooruPreferenceRepository(tmp_path / "danbooru-settings")
        ),
        danbooru_cache_repository=build_danbooru_cache_repository(
            tmp_path / "danbooru-cache"
        ),
        civitai_preference_service=CivitaiPreferenceService(
            FileCivitaiPreferenceRepository(tmp_path / "civitai-settings")
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


def close_and_delete_widget(widget: QWidget) -> None:
    """Close one Settings widget and prove deferred Qt destruction completed."""

    destroyed = QSignalSpy(widget.destroyed)
    widget.close()
    widget.deleteLater()
    wait_for_qt_signal(destroyed)


def close_settings_workspace(workspace: SettingsWorkspaceWidgets) -> None:
    """Release both independently mounted Settings workspace widgets."""

    close_and_delete_widget(workspace.navigation_pane)
    close_and_delete_widget(workspace.panel)


def tall_widget(text: str) -> QWidget:
    """Return a deterministic tall page body."""

    widget = QLabel(text)
    widget.setMinimumHeight(360)
    return widget


def label_texts(widget: QWidget) -> tuple[str, ...]:
    """Return all non-empty labels below one widget."""

    return tuple(
        text for label in widget.findChildren(QLabel) if (text := label.text().strip())
    )
