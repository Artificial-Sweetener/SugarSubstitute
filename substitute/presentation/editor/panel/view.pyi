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

"""Type surface for the canonical editor-panel view."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QWidget

from substitute.application.node_behavior import (
    NodeBehaviorService,
)
from substitute.application.localization import NodePresentationService
from substitute.application.workflows import (
    WorkflowIssueState,
)
from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.features.profile import (
    PromptFeatureProfileService,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.lora.effective_provider import (
    ScheduledLoraProvider,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLoraService,
)
from substitute.domain.prompt.preferences.models import (
    PromptWheelAdjustmentMode,
)
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ModelMetadataRefreshEvent,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.model_discovery import EmptyModelPickerAction
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.application.user_presets import UserPresetService
from substitute.presentation.errors import ErrorReportPresenterProtocol
from .context.active_model_context import PanelActiveModelContextController
from .context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)
from .dimension_presets import EditorDimensionPresetCatalogSource
from .model_choice_snapshot_controller import PanelModelChoiceSnapshotController
from .prompt.context import EditorPanelPromptContextController
from .prompt.scene_diagnostics import EditorPanelPromptSceneDiagnosticsController
from .service_bundle import EditorPanelExecutionFactories
from .node_card.body_contribution import NodeCardBodyContributor
from .behavior_context_host import EditorPanelBehaviorContextHost
from .behavior_surface_host import EditorPanelBehaviorSurfaceHost
from .field_presentation_controller import EditorPanelFieldPresentationController
from .link_synchronization import EditorPanelLinkSynchronization
from .navigation_search_host import EditorPanelNavigationSearchHost
from .node_card_host import EditorPanelNodeCardHost
from .node_definition_runtime import EditorPanelNodeDefinitionRuntime
from .projection_host import EditorPanelProjectionHost
from .prompt_interaction import EditorPanelPromptInteraction
from .surface_motion import EditorSurfaceMotionController

class EditorPanel(
    EditorPanelPromptInteraction,
    EditorPanelNodeDefinitionRuntime,
    EditorPanelLinkSynchronization,
    EditorPanelBehaviorContextHost,
    EditorPanelProjectionHost,
    EditorPanelBehaviorSurfaceHost,
    EditorPanelNodeCardHost,
    EditorPanelNavigationSearchHost,
    QWidget,
):
    CUBE_SPACING: int
    currentCubeVisibleChanged: Any
    inputImageChanged: Any
    inputImageClicked: Any
    inputMaskChanged: Any
    inputMaskClicked: Any
    inputMaskOpacityChanged: Any
    inputMaskOpacityCommitted: Any
    mainwindow: Any
    scheduled_lora_provider: ScheduledLoraProvider | None
    prompt_feature_profile_service: PromptFeatureProfileService | None
    model_choice_snapshot_controller: PanelModelChoiceSnapshotController
    active_model_context_controller: PanelActiveModelContextController
    active_model_snapshot_controller: PanelActiveModelSnapshotController
    dimension_preset_source: EditorDimensionPresetCatalogSource | None
    _cube_states: Mapping[str, Any] | None
    _stack_order: list[str] | None
    _prompt_context_controller: EditorPanelPromptContextController
    _prompt_scene_diagnostics_controller: EditorPanelPromptSceneDiagnosticsController
    field_presentation: EditorPanelFieldPresentationController
    _surface_motion: EditorSurfaceMotionController

    def __init__(
        self,
        *,
        node_definition_gateway: NodeDefinitionGateway,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        node_behavior_service: NodeBehaviorService,
        node_presentation_service: NodePresentationService,
        danbooru_url_import_service: DanbooruUrlImportService | None = ...,
        danbooru_wiki_service: DanbooruWikiContentService | None = ...,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = ...,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = ...,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = ...,
        scheduled_lora_provider: ScheduledLoraProvider | None = ...,
        prompt_scheduled_lora_service: PromptScheduledLoraService | None = ...,
        prompt_spellcheck_service: PromptSpellcheckService | None = ...,
        prompt_feature_profile_service: PromptFeatureProfileService | None = ...,
        model_catalog_service: ModelCatalogLookup | None = ...,
        model_choice_resolver: RichChoiceResolver | None = ...,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = ...,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = ...,
        empty_model_picker_action: EmptyModelPickerAction | None = ...,
        model_updates: ModelUpdatePickerBridge | None = ...,
        user_preset_service: UserPresetService | None = ...,
        error_presenter: ErrorReportPresenterProtocol | None = ...,
        workflow_issue_state: WorkflowIssueState | None = ...,
        workflow_id: str | None = ...,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = ...,
        editor_panel_execution_factories: EditorPanelExecutionFactories | None = ...,
        node_card_body_contributors: tuple[NodeCardBodyContributor, ...] = ...,
    ) -> None: ...
    def set_cube_stack_unavailable_progress(self, progress: float) -> None: ...
    def content_horizontal_gutters(self) -> tuple[int, int]: ...
    def refresh_mask_picker(
        self,
        cube_alias: str,
        node_name: str,
        new_path: str,
    ) -> None: ...
    def refresh_model_metadata(self) -> None: ...
    def refresh_model_metadata_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int: ...
    def set_model_field_load_progress(
        self,
        *,
        cube_alias: str,
        node_name: str,
        field_key: str,
        percent: float | None,
        active: bool,
    ) -> None: ...
    def clear_model_field_load_progress(self) -> None: ...
    def mark_lora_metadata_dirty(self) -> None: ...
    def refresh_visible_lora_metadata(self) -> int: ...
