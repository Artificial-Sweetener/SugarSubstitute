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

"""Define typed dependency bundle injected into MainWindow composition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from substitute.application.ports import (
    CubeLibraryClient,
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
    SessionSnapshotRepository,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from substitute.application.about import AboutInfoService
    from substitute.application.appearance import AppearanceRestartCoordinator
    from substitute.application.civitai import (
        CivitaiCacheService,
        CivitaiCredentialService,
        CivitaiPreferenceService,
    )
    from substitute.application.comfy_environment import ComfyEnvironmentService
    from substitute.application.cube_library import CubeLibraryManagementService
    from substitute.application.cubes import CubeLoadService, CubeMaskBindingService
    from substitute.application.danbooru import (
        DanbooruImagePreviewService,
        DanbooruPreferenceService,
        DanbooruRecentPostsService,
        DanbooruUrlImportService,
        DanbooruWikiContentService,
    )
    from substitute.application.generation import (
        GenerationPreviewPreferenceService,
        GenerationResultSnapshotService,
        GenerationService,
        OutputOrganizationPreferenceService,
        ProgressService,
        RecipeOutputSiblingDiscoveryService,
    )
    from substitute.application.generation import GenerationJobQueueService
    from substitute.application.model_metadata import (
        ModelCatalogService,
        ModelMetadataUpdateSink,
        RichChoiceResolver,
        ScopedMetadataRefreshService,
        ThumbnailAssetRepository,
    )
    from substitute.application.node_behavior import NodeBehaviorService
    from substitute.application.onboarding import ComfyConnectionSettingsService
    from substitute.application.overrides import PinnedOverrideService
    from substitute.application.ports import DanbooruCacheRepository
    from substitute.application.prompt_editor import (
        PromptEditorPreferenceService,
        PromptFeatureProfileService,
        PromptLoraCatalogService,
        PromptScheduledLoraService,
        PromptSpellcheckService,
        ScheduledLoraProvider,
    )
    from substitute.application.prompt_wildcards import (
        PromptWildcardFileManagementService,
        PromptWildcardPreferenceService,
        PromptWildcardPreprocessingService,
    )
    from substitute.application.recipes import (
        RecipeIoService,
        RecipeModelDownloadResolutionService,
        RecipeModelLoadResolver,
        WorkflowExportService,
    )
    from substitute.application.restart_requirements import RestartRequirementService
    from substitute.application.user_presets import UserPresetService
    from substitute.application.workflows import (
        AssetRevealService,
        CanvasIoService,
        WorkflowAssetService,
    )
    from substitute.application.workflows.canvas_image_registry import (
        CanvasImageRegistry,
    )
    from substitute.application.workflows.output_canvas_projection import (
        OutputCanvasProjection,
    )
    from substitute.presentation.shell.workspace_generation_controller import (
        WorkspaceGenerationController,
    )
    from substitute.presentation.shell.shell_resource_lifecycle import (
        ShellResourceLifecycle,
    )
    from substitute.application.workspace_state import SessionAutosaveService
    from substitute.application.workspace_state.restore_projection_cache import (
        RestoreProjectionCacheRepository,
    )
    from substitute.presentation.editor.panel.service_bundle import (
        EditorPanelExecutionFactories,
    )
    from substitute.presentation.resources.cube_icon_factory import CubeIconFactory
    from substitute.presentation.settings.settings_async import (
        SettingsAsyncTaskRunnerFactory,
    )
    from substitute.presentation.widgets.model_metadata_context_menu import (
        ModelMetadataContextActionHandler,
    )
    from sugarsubstitute_shared.presentation.terminal.output_stream import (
        TerminalOutputStream,
    )


@dataclass(frozen=True)
class InstallationPathBundle:
    """Bundle install-root paths supplied by bootstrap composition."""

    install_root: Path
    user_dir: Path
    projects_dir: Path
    outputs_dir: Path
    sugar_scripts_dir: Path
    wildcards_dir: Path
    managed_comfy_dir: Path


CubeLibraryUpdateCallback = Callable[[object], None]


class CubeLibraryEventListenerLifecycle(Protocol):
    """Describe listener lifecycle owned by the shell."""

    def start(self) -> None:
        """Start receiving Cube Library update notifications."""

    def stop(self) -> None:
        """Stop receiving Cube Library update notifications."""


CubeLibraryEventListenerFactory = Callable[
    [CubeLibraryUpdateCallback],
    CubeLibraryEventListenerLifecycle,
]
ModelCatalogUpdateCallback = Callable[[object], None]


class ModelCatalogEventListenerLifecycle(Protocol):
    """Describe listener lifecycle owned by the shell."""

    def start(self) -> None:
        """Start receiving model catalog update notifications."""

    def stop(self) -> None:
        """Stop receiving model catalog update notifications."""


ModelCatalogEventListenerFactory = Callable[
    [ModelCatalogUpdateCallback],
    ModelCatalogEventListenerLifecycle,
]
ScopedMetadataRefreshServiceFactory = Callable[
    ["ModelMetadataUpdateSink"],
    "ScopedMetadataRefreshService",
]


@dataclass(frozen=True)
class MainWindowDependencies:
    """Bundle services/controllers composed by bootstrap and consumed by MainWindow."""

    cube_load_service: CubeLoadService
    cube_library_client: CubeLibraryClient
    create_cube_library_event_listener: CubeLibraryEventListenerFactory
    create_model_catalog_event_listener: ModelCatalogEventListenerFactory
    create_scoped_metadata_refresh_service: ScopedMetadataRefreshServiceFactory
    cube_icon_factory: CubeIconFactory
    invalidate_cube_catalog_cache: Callable[[], None]
    cube_mask_binding_service: CubeMaskBindingService
    recipe_io_service: RecipeIoService
    workflow_export_service: WorkflowExportService
    progress_service: ProgressService
    generation_service: GenerationService
    generation_job_queue_service: GenerationJobQueueService
    asset_reveal_service: AssetRevealService
    canvas_io_service: CanvasIoService
    workflow_asset_service: WorkflowAssetService
    workspace_generation_controller: WorkspaceGenerationController
    shell_resource_lifecycle: ShellResourceLifecycle
    comfy_output_stream: TerminalOutputStream
    node_definition_gateway: NodeDefinitionGateway
    prompt_autocomplete_gateway: PromptAutocompleteGateway
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway
    danbooru_url_import_service: DanbooruUrlImportService
    danbooru_wiki_service: DanbooruWikiContentService
    danbooru_image_preview_service: DanbooruImagePreviewService
    danbooru_recent_posts_service: DanbooruRecentPostsService
    danbooru_preference_service: DanbooruPreferenceService
    danbooru_cache_repository: DanbooruCacheRepository
    civitai_preference_service: CivitaiPreferenceService
    civitai_credential_service: CivitaiCredentialService
    civitai_cache_service: CivitaiCacheService
    prompt_wildcard_file_management_service: PromptWildcardFileManagementService
    open_wildcard_management_modal: Callable[[QWidget | None], None]
    prompt_wildcard_preference_service: PromptWildcardPreferenceService
    prompt_wildcard_preprocessing_service: PromptWildcardPreprocessingService
    prompt_lora_catalog_service: PromptLoraCatalogService
    prompt_scheduled_lora_service: PromptScheduledLoraService
    prompt_spellcheck_service: PromptSpellcheckService
    scheduled_lora_provider: ScheduledLoraProvider
    prompt_feature_profile_service: PromptFeatureProfileService
    user_preset_service: UserPresetService
    model_catalog_service: ModelCatalogService
    model_choice_resolver: RichChoiceResolver
    thumbnail_asset_repository: ThumbnailAssetRepository | None
    node_behavior_service: NodeBehaviorService
    pinned_override_service: PinnedOverrideService
    open_reconfigure_window: Callable[[], object]
    appearance_runtime: Any
    appearance_restart_coordinator: AppearanceRestartCoordinator
    about_info_service: AboutInfoService
    comfy_connection_settings_service: ComfyConnectionSettingsService
    restart_requirement_service: RestartRequirementService
    comfy_environment_service: ComfyEnvironmentService
    cube_library_management_service: CubeLibraryManagementService
    generation_preview_preference_service: GenerationPreviewPreferenceService
    output_organization_preference_service: OutputOrganizationPreferenceService
    prompt_editor_preference_service: PromptEditorPreferenceService
    session_snapshot_repository: SessionSnapshotRepository
    session_autosave_service: SessionAutosaveService
    execution_runtime: Any
    settings_task_runner_factory: SettingsAsyncTaskRunnerFactory
    editor_panel_execution_factories: EditorPanelExecutionFactories
    generation_result_snapshot_service: GenerationResultSnapshotService
    recipe_output_sibling_discovery_service: RecipeOutputSiblingDiscoveryService
    path_bundle: InstallationPathBundle
    create_recipe_model_load_resolver: Callable[[], RecipeModelLoadResolver] | None = (
        None
    )
    recipe_model_download_resolution_service: (
        RecipeModelDownloadResolutionService | None
    ) = None
    restore_projection_cache_repository: RestoreProjectionCacheRepository | None = None
    restore_projection_target_key: str = ""
    model_metadata_context_action_handler: ModelMetadataContextActionHandler | None = (
        None
    )
    manual_model_metadata_update_sink: ModelMetadataUpdateSink | None = None
    configure_output_thumbnail_context: (
        Callable[
            [
                "CanvasImageRegistry",
                Callable[[], "OutputCanvasProjection | None"],
            ],
            None,
        ]
        | None
    ) = None


__all__ = ["InstallationPathBundle", "MainWindowDependencies"]
