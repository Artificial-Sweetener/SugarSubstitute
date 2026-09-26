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

"""Describe immutable dependencies for one editor-panel composition pass."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.localization import NodePresentationService
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.application.model_metadata.ultralytics_thumbnail_associations import (
    UltralyticsThumbnailAssociationService,
)
from substitute.application.node_behavior import NodeBehaviorService
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
from substitute.application.user_presets import UserPresetService
from substitute.application.workflows import WorkflowIssueState
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.model_discovery import EmptyModelPickerAction
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)

from .node_card.body_contribution import NodeCardBodyContributor
from .service_bundle import EditorPanelExecutionFactories


@dataclass(frozen=True, slots=True)
class EditorPanelCompositionInputs:
    """Collect immutable dependencies used while composing one panel instance."""

    node_definition_gateway: NodeDefinitionGateway
    prompt_autocomplete_gateway: PromptAutocompleteGateway
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway
    node_behavior_service: NodeBehaviorService
    node_presentation_service: NodePresentationService
    danbooru_url_import_service: DanbooruUrlImportService | None
    danbooru_wiki_service: DanbooruWikiContentService | None
    danbooru_image_preview_service: DanbooruImagePreviewService | None
    danbooru_recent_posts_service: DanbooruRecentPostsService | None
    prompt_lora_catalog_service: PromptLoraCatalogLookup | None
    scheduled_lora_provider: ScheduledLoraProvider | None
    prompt_scheduled_lora_service: PromptScheduledLoraService | None
    prompt_spellcheck_service: PromptSpellcheckService | None
    prompt_feature_profile_service: PromptFeatureProfileService | None
    model_catalog_service: ModelCatalogLookup | None
    model_choice_resolver: RichChoiceResolver | None
    thumbnail_asset_repository: ThumbnailAssetRepository | None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None
    ultralytics_thumbnail_associations: UltralyticsThumbnailAssociationService | None
    empty_model_picker_action: EmptyModelPickerAction | None
    model_updates: ModelUpdatePickerBridge | None
    user_preset_service: UserPresetService | None
    error_presenter: ErrorReportPresenterProtocol | None
    workflow_issue_state: WorkflowIssueState | None
    workflow_id: str | None
    execution_factories: EditorPanelExecutionFactories | None
    wheel_adjustment_mode: PromptWheelAdjustmentMode
    node_card_body_contributors: tuple[NodeCardBodyContributor, ...]


__all__ = ["EditorPanelCompositionInputs"]
