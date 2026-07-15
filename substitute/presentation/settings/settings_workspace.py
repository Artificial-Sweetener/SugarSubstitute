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

"""Compose the integrated Settings workspace for the main shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from substitute.application.about import AboutInfoService
from substitute.application.appearance import AppearanceRestartCoordinator
from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.application.cube_library import CubeLibraryManagementService
from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.civitai import (
    CivitaiCacheService,
    CivitaiCredentialService,
    CivitaiPreferenceService,
)
from substitute.application.onboarding import ComfyConnectionSettingsService
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.application.prompt_editor import PromptEditorPreferenceService
from substitute.application.prompt_wildcards import (
    PromptWildcardFileManagementService,
    PromptWildcardPreferenceService,
)
from substitute.presentation.settings.appearance_runtime_protocol import (
    AppearanceRuntimeProtocol,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.comfy_environment_page import (
    ComfyEnvironmentPage,
)
from substitute.presentation.settings.cube_library_page import CubeLibrarySettingsPage
from substitute.presentation.settings.settings_catalog import SettingsPageEntry
from substitute.presentation.settings.settings_catalog_builders import (
    AppearanceSettingsContext,
    ComfyUiSettingsContext,
    GenerationSettingsContext,
    ModelSourcesSettingsContext,
    PromptEditingSettingsContext,
    build_appearance_settings_page,
    build_comfyui_search_catalog_page,
    build_generation_settings_page,
    build_model_sources_settings_page,
    build_prompt_editing_settings_page,
)
from substitute.presentation.settings.settings_composite_pages import (
    ComfyUiSettingsPage,
)
from substitute.presentation.settings.settings_page_renderer import CatalogSettingsPage
from substitute.presentation.settings.settings_search import search_settings_catalog
from substitute.presentation.settings.settings_search_page import SettingsSearchPage
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunnerFactory,
)
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputOrganizationPreferenceService,
)
from substitute.presentation.settings.about_page import AboutSettingsPage
from substitute.presentation.settings.settings_navigation import (
    SettingsNavigationDescriptor,
    SettingsNavigationPane,
)
from substitute.presentation.settings.settings_workspace_panel import (
    SettingsPageDescriptor,
    SettingsWorkspacePanel,
)

ABOUT_SECTION_ID = "about"
APPEARANCE_SECTION_ID = "appearance"
COMFYUI_SECTION_ID = "comfyui"
LIBRARY_SECTION_ID = "library"
GENERATION_SECTION_ID = "generation"
PROMPT_EDITING_SECTION_ID = "prompt_editing"
MODEL_SOURCES_SECTION_ID = "model_sources"


@dataclass(frozen=True)
class SettingsWorkspaceWidgets:
    """Return the two widgets projected into the main workspace columns."""

    navigation_pane: SettingsNavigationPane
    panel: SettingsWorkspacePanel


def create_settings_workspace(
    *,
    comfy_environment_service: ComfyEnvironmentService,
    cube_library_management_service: CubeLibraryManagementService,
    cube_library_catalog_invalidated: Callable[[], None] | None = None,
    cube_library_restart_required_changed: Callable[[bool], None] | None = None,
    cube_library_post_restart_refresh: Callable[[], None] | None = None,
    about_info_service: AboutInfoService,
    comfy_connection_settings_service: ComfyConnectionSettingsService,
    appearance_runtime: AppearanceRuntimeProtocol,
    appearance_restart_coordinator: AppearanceRestartCoordinator,
    prompt_editor_preference_service: PromptEditorPreferenceService,
    danbooru_preference_service: DanbooruPreferenceService,
    danbooru_cache_repository: DanbooruCacheRepository,
    civitai_preference_service: CivitaiPreferenceService,
    civitai_credential_service: CivitaiCredentialService,
    civitai_cache_service: CivitaiCacheService,
    generation_preview_preference_service: GenerationPreviewPreferenceService,
    output_organization_preference_service: OutputOrganizationPreferenceService,
    open_reconfigure_window: Callable[[], object],
    show_restart_requirements: Callable[[], None] | None = None,
    prompt_editor_preferences_changed: Callable[[], None] | None = None,
    prompt_wildcard_preference_service: PromptWildcardPreferenceService | None = None,
    prompt_wildcard_file_management_service: (
        PromptWildcardFileManagementService | None
    ) = None,
    open_wildcard_management_modal: Callable[[QWidget | None], None] | None = None,
    error_presenter: ErrorReportPresenterProtocol | None = None,
    task_runner_factory: SettingsAsyncTaskRunnerFactory,
    parent: QWidget | None = None,
) -> SettingsWorkspaceWidgets:
    """Create the integrated Settings workspace from application services."""

    navigation_pane = SettingsNavigationPane(parent)
    panel = SettingsWorkspacePanel(parent)

    generation_entry = build_generation_settings_page(
        GenerationSettingsContext(
            generation_preview_service=generation_preview_preference_service,
            output_organization_service=output_organization_preference_service,
            civitai_preference_service=civitai_preference_service,
            task_runner_factory=task_runner_factory,
        )
    )
    prompt_entry = build_prompt_editing_settings_page(
        PromptEditingSettingsContext(
            preference_service=prompt_editor_preference_service,
            danbooru_preference_service=danbooru_preference_service,
            danbooru_cache_repository=danbooru_cache_repository,
            wildcard_preference_service=prompt_wildcard_preference_service,
            wildcard_file_management_service=prompt_wildcard_file_management_service,
            open_wildcard_management_modal=open_wildcard_management_modal,
            preferences_changed=prompt_editor_preferences_changed,
        )
    )
    model_sources_context = ModelSourcesSettingsContext(
        civitai_preference_service=civitai_preference_service,
        civitai_credential_service=civitai_credential_service,
        civitai_cache_service=civitai_cache_service,
    )
    model_sources_entry = build_model_sources_settings_page(model_sources_context)
    comfy_context = ComfyUiSettingsContext(
        connection_service=comfy_connection_settings_service,
        open_reconfigure_window=open_reconfigure_window,
        task_runner_factory=task_runner_factory,
    )
    comfy_search_entry = build_comfyui_search_catalog_page(comfy_context)
    appearance_entry = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=appearance_runtime,
            appearance_restart_coordinator=appearance_restart_coordinator,
            show_restart_requirements=show_restart_requirements,
        )
    )
    catalog_search_pages = (
        generation_entry,
        prompt_entry,
        model_sources_entry,
        comfy_search_entry,
        appearance_entry,
    )
    navigation_descriptors = _navigation_descriptors(
        SettingsNavigationDescriptor(
            page_id=ABOUT_SECTION_ID,
            title="About",
            subtitle="Version, project, and acknowledgements",
            icon=AppIcon.CUBE_20_FILLED,
        ),
        generation_entry,
        prompt_entry,
        model_sources_entry,
        SettingsNavigationDescriptor(
            page_id=LIBRARY_SECTION_ID,
            title="Library",
            subtitle="Cube Packs and readiness",
            icon=AppIcon.LIBRARY_20_REGULAR,
        ),
        SettingsNavigationDescriptor(
            page_id=COMFYUI_SECTION_ID,
            title="ComfyUI",
            subtitle="Connection, setup, and Python environment",
            icon=AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
        ),
        appearance_entry,
    )
    pages = (
        SettingsPageDescriptor(
            page_id=ABOUT_SECTION_ID,
            title="About",
            subtitle="Version, project, and acknowledgements.",
            icon=AppIcon.CUBE_20_FILLED,
            create_widget=lambda parent: AboutSettingsPage(
                about_info_service,
                parent=parent,
                task_runner_factory=task_runner_factory,
            ),
        ),
        SettingsPageDescriptor(
            page_id=generation_entry.page_id,
            title=generation_entry.title,
            subtitle=generation_entry.subtitle,
            icon=generation_entry.icon,
            create_widget=lambda parent: CatalogSettingsPage(
                generation_entry,
                parent=parent,
            ),
        ),
        SettingsPageDescriptor(
            page_id=prompt_entry.page_id,
            title=prompt_entry.title,
            subtitle=prompt_entry.subtitle,
            icon=prompt_entry.icon,
            create_widget=lambda parent: CatalogSettingsPage(
                prompt_entry,
                parent=parent,
            ),
        ),
        SettingsPageDescriptor(
            page_id=model_sources_entry.page_id,
            title=model_sources_entry.title,
            subtitle=model_sources_entry.subtitle,
            icon=model_sources_entry.icon,
            create_widget=lambda parent: CatalogSettingsPage(
                model_sources_entry,
                parent=parent,
            ),
        ),
        SettingsPageDescriptor(
            page_id=LIBRARY_SECTION_ID,
            title="Library",
            subtitle="Manage Cube Packs tracked by the active Comfy target.",
            icon=AppIcon.LIBRARY_20_REGULAR,
            create_widget=lambda parent: CubeLibrarySettingsPage(
                cube_library_management_service,
                restart_service=comfy_environment_service,
                restart_required_changed=cube_library_restart_required_changed,
                post_restart_refresh=cube_library_post_restart_refresh,
                catalog_invalidated=cube_library_catalog_invalidated,
                error_presenter=error_presenter,
                task_runner_factory=task_runner_factory,
                parent=parent,
            ),
        ),
        SettingsPageDescriptor(
            page_id=COMFYUI_SECTION_ID,
            title="ComfyUI",
            subtitle="Manage ComfyUI connection, setup, and Python environment.",
            icon=AppIcon.PLUG_CONNECTED_SETTINGS_20_REGULAR,
            create_widget=lambda parent: _comfyui_settings_page(
                comfy_environment_service=comfy_environment_service,
                comfy_connection_settings_service=comfy_connection_settings_service,
                open_reconfigure_window=open_reconfigure_window,
                show_restart_requirements=show_restart_requirements,
                error_presenter=error_presenter,
                task_runner_factory=task_runner_factory,
                parent=parent,
            ),
        ),
        SettingsPageDescriptor(
            page_id=appearance_entry.page_id,
            title=appearance_entry.title,
            subtitle=appearance_entry.subtitle,
            icon=appearance_entry.icon,
            create_widget=lambda parent: CatalogSettingsPage(
                appearance_entry,
                parent=parent,
            ),
        ),
    )

    navigation_pane.set_pages(navigation_descriptors)
    panel.set_pages(pages)
    navigation_pane.pageSelected.connect(
        lambda page_id: _select_settings_page(panel=panel, page_id=page_id)
    )
    panel.currentPageChanged.connect(
        lambda page_id: navigation_pane.select_page(page_id, animated=True)
    )
    panel.searchQueryChanged.connect(
        lambda query: _apply_settings_search(
            panel=panel,
            catalog_pages=catalog_search_pages,
            query=query,
        )
    )
    panel.select_page(ABOUT_SECTION_ID, animated=False)
    navigation_pane.select_page(ABOUT_SECTION_ID, animated=False)
    return SettingsWorkspaceWidgets(navigation_pane=navigation_pane, panel=panel)


def _navigation_descriptors(
    *items: SettingsPageEntry | SettingsNavigationDescriptor,
) -> tuple[SettingsNavigationDescriptor, ...]:
    """Return navigation descriptors from catalog and explicit dynamic entries."""

    descriptors: list[SettingsNavigationDescriptor] = []
    for item in items:
        if isinstance(item, SettingsNavigationDescriptor):
            descriptors.append(item)
            continue
        descriptors.append(
            SettingsNavigationDescriptor(
                page_id=item.page_id,
                title=item.title,
                subtitle=item.subtitle,
                icon=item.icon,
            )
        )
    return tuple(descriptors)


def _comfyui_settings_page(
    *,
    comfy_environment_service: ComfyEnvironmentService,
    comfy_connection_settings_service: ComfyConnectionSettingsService,
    open_reconfigure_window: Callable[[], object],
    show_restart_requirements: Callable[[], None] | None,
    error_presenter: ErrorReportPresenterProtocol | None,
    task_runner_factory: SettingsAsyncTaskRunnerFactory,
    parent: QWidget,
) -> ComfyUiSettingsPage:
    """Create the composite ComfyUI Settings page and its embedded children."""

    connection_page = ComfyConnectionSettingsPage(
        service=comfy_connection_settings_service,
        open_reconfigure_window=open_reconfigure_window,
        show_restart_requirements=show_restart_requirements,
        task_runner_factory=task_runner_factory,
        parent=parent,
    )
    environment_page = ComfyEnvironmentPage(
        comfy_environment_service,
        open_reconfigure_window=open_reconfigure_window,
        error_presenter=error_presenter,
        task_runner_factory=task_runner_factory,
        parent=parent,
    )
    environment_page.setMinimumHeight(720)
    return ComfyUiSettingsPage(
        connection_page=connection_page,
        environment_page=environment_page,
        parent=parent,
    )


def _select_settings_page(*, panel: SettingsWorkspacePanel, page_id: str) -> None:
    """Select a normal Settings page and clear synthetic search state."""

    panel.set_search_query("")
    panel.select_page(page_id, animated=True)


def _apply_settings_search(
    *,
    panel: SettingsWorkspacePanel,
    catalog_pages: tuple[SettingsPageEntry, ...],
    query: str,
) -> None:
    """Render or clear the synthetic Settings search page."""

    if not query.strip():
        panel.clear_search_page(animated=False)
        return
    results = search_settings_catalog(catalog_pages, query)
    panel.show_search_page(
        SettingsSearchPage(
            results,
            on_result_activated=lambda result: panel.reveal_setting(
                result.page_id,
                result.setting_id,
                animated=False,
            ),
            parent=panel,
        ),
        animated=False,
    )


__all__ = [
    "ABOUT_SECTION_ID",
    "APPEARANCE_SECTION_ID",
    "COMFYUI_SECTION_ID",
    "GENERATION_SECTION_ID",
    "LIBRARY_SECTION_ID",
    "MODEL_SOURCES_SECTION_ID",
    "PROMPT_EDITING_SECTION_ID",
    "SettingsWorkspaceWidgets",
    "create_settings_workspace",
]
