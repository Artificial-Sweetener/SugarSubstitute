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

"""Render and coordinate the editor-panel view for workflow cube stacks."""

from __future__ import annotations


from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid as _qt_is_valid

from substitute.application.node_behavior import (
    NodeBehaviorService,
)
from substitute.application.localization import NodePresentationService
from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.workflows import (
    WorkflowIssueState,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.features.profile import (
    PromptFeatureProfileService,
)
from substitute.application.prompt_editor.lora.effective_provider import (
    ScheduledLoraProvider,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLoraService,
)
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ModelMetadataRefreshEvent,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.application.model_metadata.ultralytics_thumbnail_associations import (
    UltralyticsThumbnailAssociationService,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.model_discovery import EmptyModelPickerAction
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.application.user_presets import UserPresetService
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
)
from substitute.shared.logging.logger import (
    get_logger,
)
from .composition import compose_editor_panel
from .composition_models import EditorPanelCompositionInputs
from .runtime_access import (
    cube_reveal_controller_for_panel as _cube_reveal_controller_for_panel,
    lora_metadata_refresh_controller_for_panel as _lora_metadata_refresh_controller_for_panel,
)
from .service_bundle import (
    EditorPanelExecutionFactories,
)
from .behavior_surface_host import EditorPanelBehaviorSurfaceHost
from .behavior_context_host import EditorPanelBehaviorContextHost
from .projection_host import EditorPanelProjectionHost
from .node_card.body_contribution import NodeCardBodyContributor
from .node_definition_runtime import EditorPanelNodeDefinitionRuntime
from .node_card_host import EditorPanelNodeCardHost
from .navigation_search_host import EditorPanelNavigationSearchHost
from .link_synchronization import EditorPanelLinkSynchronization
from .prompt_interaction import EditorPanelPromptInteraction

_LOGGER = get_logger("presentation.editor.panel.view")


def isValid(obj: object) -> bool:  # noqa: N802
    """Return whether one Qt wrapper is valid for panel test hooks."""

    return bool(_qt_is_valid(obj))


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
    """Render one workflow editor surface and coordinate cube-section refreshes."""

    CUBE_SPACING = EDITOR_SECTION_GAP
    currentCubeVisibleChanged = Signal(str)
    inputImageChanged = Signal(str, str, str)
    inputImageClicked = Signal(str, str, str)
    inputMaskChanged = Signal(str, str, str)
    inputMaskClicked = Signal(str, str, str)
    inputMaskOpacityChanged = Signal(str, str, float)
    inputMaskOpacityCommitted = Signal(str, str, float, float)
    promptEditorLayoutChanged = Signal()
    promptSceneQueueRequested = Signal(str)

    def resizeEvent(self, event):
        """Forward resize events to the base widget implementation."""

        super().resizeEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Cancel automated cube reveal when the user scrolls the editor."""

        if self._is_user_scroll_interruption(watched, event):
            self._cancel_active_cube_reveal_scroll()
        return super().eventFilter(watched, event)

    def _is_user_scroll_interruption(self, watched: QObject, event: QEvent) -> bool:
        """Return whether one viewport event should cancel automated cube reveal."""

        event_type = event.type()
        interruption_type = None
        if event_type == QEvent.Type.Wheel:
            interruption_type = "wheel"
        elif event_type == QEvent.Type.MouseButtonPress:
            interruption_type = "mouse_press"
        return _cube_reveal_controller_for_panel(self).is_user_scroll_interruption(
            watched,
            interruption_type,
        )

    def _cancel_active_cube_reveal_scroll(self) -> None:
        """Stop active or pending cube reveal motion after deliberate user input."""

        _cube_reveal_controller_for_panel(self).cancel_active_cube_reveal_scroll()
        self._surface_motion.cancel(reason="user_scroll_interruption")

    def refresh_mask_picker(self, cube_alias: str, node_name: str, new_path: str):
        """Refresh the mask picker matching one cube and node identity."""

        self.field_presentation.refresh_mask_picker(cube_alias, node_name, new_path)

    def refresh_model_metadata(self) -> None:
        """Refresh every model picker widget from current metadata."""

        self.field_presentation.refresh_model_metadata()

    def refresh_model_metadata_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Refresh visible model picker state affected by one metadata event."""

        return self.field_presentation.refresh_model_metadata_for_event(event)

    def clear_model_thumbnail_caches_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Clear affected model picker thumbnail caches after image asset updates."""

        return self.field_presentation.clear_model_thumbnail_caches_for_event(event)

    def clear_lora_thumbnail_caches(self) -> int:
        """Clear prompt-editor LoRA thumbnail caches owned by this panel."""

        return self.field_presentation.clear_lora_thumbnail_caches()

    def set_model_field_load_progress(
        self,
        *,
        cube_alias: str,
        node_name: str,
        field_key: str,
        percent: float | None,
        active: bool,
    ) -> None:
        """Route source-enriched model-load progress to one model picker field."""

        self.field_presentation.set_model_field_load_progress(
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            percent=percent,
            active=active,
        )

    def clear_model_field_load_progress(self) -> None:
        """Clear model-load progress from all tracked model picker fields."""

        self.field_presentation.clear_model_field_load_progress()

    def mark_lora_metadata_dirty(self) -> None:
        """Mark prompt editor LoRA metadata dirty without rebuilding projections."""

        _lora_metadata_refresh_controller_for_panel(self).mark_lora_metadata_dirty()

    def refresh_visible_lora_metadata(self) -> int:
        """Refresh dirty visible prompt editors that need LoRA metadata."""

        return _lora_metadata_refresh_controller_for_panel(
            self
        ).refresh_visible_lora_metadata()

    def __init__(
        self,
        *,
        node_definition_gateway: NodeDefinitionGateway,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        node_behavior_service: NodeBehaviorService,
        node_presentation_service: NodePresentationService,
        danbooru_url_import_service: DanbooruUrlImportService | None = None,
        danbooru_wiki_service: DanbooruWikiContentService | None = None,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        scheduled_lora_provider: ScheduledLoraProvider | None = None,
        prompt_scheduled_lora_service: PromptScheduledLoraService | None = None,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        prompt_feature_profile_service: PromptFeatureProfileService | None = None,
        model_catalog_service: ModelCatalogLookup | None = None,
        model_choice_resolver: RichChoiceResolver | None = None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        ultralytics_thumbnail_associations: (
            UltralyticsThumbnailAssociationService | None
        ) = None,
        empty_model_picker_action: EmptyModelPickerAction | None = None,
        model_updates: ModelUpdatePickerBridge | None = None,
        user_preset_service: UserPresetService | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        workflow_issue_state: WorkflowIssueState | None = None,
        workflow_id: str | None = None,
        editor_panel_execution_factories: EditorPanelExecutionFactories | None = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        node_card_body_contributors: tuple[NodeCardBodyContributor, ...] = (),
    ) -> None:
        """Initialize the passive view and delegate runtime composition."""

        super().__init__()
        compose_editor_panel(
            self,
            EditorPanelCompositionInputs(
                node_definition_gateway=node_definition_gateway,
                prompt_autocomplete_gateway=prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
                node_behavior_service=node_behavior_service,
                node_presentation_service=node_presentation_service,
                danbooru_url_import_service=danbooru_url_import_service,
                danbooru_wiki_service=danbooru_wiki_service,
                danbooru_image_preview_service=danbooru_image_preview_service,
                danbooru_recent_posts_service=danbooru_recent_posts_service,
                prompt_lora_catalog_service=prompt_lora_catalog_service,
                scheduled_lora_provider=scheduled_lora_provider,
                prompt_scheduled_lora_service=prompt_scheduled_lora_service,
                prompt_spellcheck_service=prompt_spellcheck_service,
                prompt_feature_profile_service=prompt_feature_profile_service,
                model_catalog_service=model_catalog_service,
                model_choice_resolver=model_choice_resolver,
                thumbnail_asset_repository=thumbnail_asset_repository,
                model_metadata_action_handler=model_metadata_action_handler,
                ultralytics_thumbnail_associations=(ultralytics_thumbnail_associations),
                empty_model_picker_action=empty_model_picker_action,
                model_updates=model_updates,
                user_preset_service=user_preset_service,
                error_presenter=error_presenter,
                workflow_issue_state=workflow_issue_state,
                workflow_id=workflow_id,
                execution_factories=editor_panel_execution_factories,
                wheel_adjustment_mode=wheel_adjustment_mode,
                node_card_body_contributors=node_card_body_contributors,
            ),
        )

    def set_cube_stack_unavailable_progress(self, progress: float) -> None:
        """Apply the shared stack-transition progress to editor content spacing."""

        self._content_gutter_controller.apply_cube_stack_unavailable_progress(progress)

    def content_horizontal_gutters(self) -> tuple[int, int]:
        """Return live editor content gutters for shell geometry diagnostics."""

        return self._content_gutter_controller.horizontal_gutters()

    @property
    def node_definition_gateway(self) -> NodeDefinitionGateway:
        """Return the host-facing node-definition gateway."""

        return self._services.node_definition_gateway

    @property
    def node_behavior_service(self) -> NodeBehaviorService:
        """Return the host-facing node-behavior service."""

        return self._services.node_behavior_service

    @property
    def prompt_scheduled_lora_service(self) -> PromptScheduledLoraService:
        """Return the scheduled-LoRA service used by prompt field owners."""

        return self._services.prompt.runtime.scheduled_lora_service_or_default()

    @property
    def scheduled_lora_provider(self) -> ScheduledLoraProvider | None:
        """Return the optional scheduled-LoRA provider for prompt contexts."""

        return self._services.prompt.scheduled_lora_provider

    @property
    def prompt_spellcheck_service(self) -> PromptSpellcheckService | None:
        """Return the optional prompt spellcheck service for host integrations."""

        return self._services.prompt.runtime.spellcheck_service

    @property
    def prompt_feature_profile_service(self) -> PromptFeatureProfileService | None:
        """Return the optional prompt feature-profile service for prompt contexts."""

        return self._services.prompt.feature_profile_service


__all__ = ["EditorPanel"]
