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

"""Define typed construction data for prompt-editor composition wiring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    QtDanbooruWikiLookupDispatcher,
)
from ..async_work import PromptEditorTaskExecutor

if TYPE_CHECKING:
    from substitute.application.danbooru import (
        DanbooruImagePreviewService,
        DanbooruRecentPostsService,
        DanbooruUrlImportService,
        DanbooruWikiContentService,
    )
    from substitute.application.model_metadata import ThumbnailAssetRepository
    from substitute.presentation.widgets.model_metadata_context_menu import (
        ModelMetadataContextActionHandler,
    )
    from substitute.application.ports import (
        PromptAutocompleteGateway,
        PromptWildcardCatalogGateway,
    )
    from substitute.application.prompt_editor import (
        PromptDocumentService,
        PromptEditorFeatureProfile,
        PromptLoraCatalogLookup,
        PromptLoraScheduleService,
        PromptMutationService,
        PromptScheduledLora,
        PromptScheduledLoraService,
        PromptSpellcheckService,
        PromptSyntaxProfile,
        PromptSyntaxService,
    )
    from substitute.application.prompt_editor.prompt_document_semantics import (
        PromptDocumentSemanticsController,
    )
    from ..async_work import (
        PromptLoraThumbnailPreloader,
        PromptScheduledLoraContextProvider,
    )
    from ..editing_session.edit_controller import PromptEditController
    from ..features import (
        PromptDanbooruActionController,
        PromptFeatureProfileController,
        PromptSegmentPresetController,
        PromptSegmentPresetSource,
        PromptSceneFeatureController,
        PromptSearchFeatureController,
        PromptWildcardFeatureController,
    )
    from ..interactions import (
        PromptAutocompleteController,
        PromptExternalUrlOpener,
        PromptInlineLoraContextMenuPresenter,
        PromptInteractionController,
        PromptWheelController,
    )
    from ..lora_thumbnail_cache import PromptLoraThumbnailCache
    from ..projection.surface import PromptProjectionUndoPayload
    from ..projection.surface import PromptProjectionSurface
    from ..syntax_renderers import PromptSyntaxRendererCoordinator
    from ..overlays import PromptTokenWeightControls
PromptEditorTaskExecutorFactory = Callable[[QWidget, str], PromptEditorTaskExecutor]
DanbooruWikiLookupDispatcherFactory = Callable[
    [QWidget], QtDanbooruWikiLookupDispatcher
]


@dataclass(frozen=True, slots=True)
class PromptEditorConstructionInputs:
    """Mirror public constructor inputs before composition starts owning behavior."""

    parent: QWidget | None
    prompt_autocomplete_gateway: PromptAutocompleteGateway
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway
    prompt_document_semantics: PromptDocumentSemanticsController
    danbooru_url_import_service: DanbooruUrlImportService | None
    danbooru_wiki_service: DanbooruWikiContentService | None
    danbooru_image_preview_service: DanbooruImagePreviewService | None
    danbooru_recent_posts_service: DanbooruRecentPostsService | None
    prompt_feature_profile: PromptEditorFeatureProfile | None
    prompt_syntax_profile: PromptSyntaxProfile | None
    maximum_visible_lines: int | None
    prompt_lora_catalog_service: PromptLoraCatalogLookup | None
    thumbnail_asset_repository: ThumbnailAssetRepository | None
    prompt_scheduled_lora_service: PromptScheduledLoraService | None
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]] | None
    prompt_segment_preset_source: PromptSegmentPresetSource | None
    prompt_spellcheck_service: PromptSpellcheckService | None
    open_url: PromptExternalUrlOpener | None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None
    danbooru_lookup_dispatcher_factory: DanbooruWikiLookupDispatcherFactory | None = (
        None
    )


@dataclass(frozen=True, slots=True)
class PromptEditorCollaborators:
    """Name the collaborators that composition will construct in later Phase 1 steps."""

    lora_thumbnail_cache: PromptLoraThumbnailCache
    lora_thumbnail_preloader: PromptLoraThumbnailPreloader
    surface: PromptProjectionSurface
    edit_controller: PromptEditController[PromptProjectionUndoPayload]
    shell_padding_fill_plane: QWidget
    fill_plane: QWidget
    lora_schedule_service: PromptLoraScheduleService
    prompt_scheduled_lora_service: PromptScheduledLoraService
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    scheduled_lora_context_provider: PromptScheduledLoraContextProvider
    feature_profile_controller: PromptFeatureProfileController
    scene_feature_controller: PromptSceneFeatureController
    search_feature_controller: PromptSearchFeatureController
    wildcard_feature_controller: PromptWildcardFeatureController
    segment_preset_controller: PromptSegmentPresetController
    danbooru_action_controller: PromptDanbooruActionController
    autocomplete: PromptAutocompleteController
    document_service: PromptDocumentService
    mutation_service: PromptMutationService
    syntax_profile: PromptSyntaxProfile
    syntax_service: PromptSyntaxService
    token_weight_controls: PromptTokenWeightControls
    wheel_controller: PromptWheelController
    syntax_renderer_coordinator: PromptSyntaxRendererCoordinator
    interaction_controller: PromptInteractionController
    inline_lora_menu_presenter: PromptInlineLoraContextMenuPresenter
    resize_handle: QWidget
