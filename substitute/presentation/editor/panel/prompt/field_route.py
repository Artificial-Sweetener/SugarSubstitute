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

"""Route prompt-box field behavior into the focused prompt editor factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.conditioning import PromptConditioningContext
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.prompt.factory import (
    PromptEditorFieldBuildRequest,
    PromptEditorFieldFactory,
)
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptProfilePolicy,
)
from substitute.presentation.editor.panel.service_bundle import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorTaskExecutorFactory,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)

_PROMPT_EDITOR_FIELD_FACTORY = PromptEditorFieldFactory()
_PROMPT_PROFILE_POLICY = PanelPromptProfilePolicy()


@dataclass(frozen=True, slots=True)
class PromptFieldRouteRequest:
    """Carry generic-pipeline inputs needed only by prompt-box construction."""

    parent: Any
    field_behavior: FieldBehavior
    node_name: str
    key: str
    value: object
    field_meta: dict[str, object]
    node_type: object
    prompt_autocomplete_gateway: PromptAutocompleteGateway
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway
    prompt_feature_profile: PromptEditorFeatureProfile | None
    prompt_syntax_profile: PromptSyntaxProfile | None
    prompt_conditioning_context: PromptConditioningContext | None
    danbooru_url_import_service: DanbooruUrlImportService | None = None
    danbooru_wiki_service: DanbooruWikiContentService | None = None
    danbooru_image_preview_service: DanbooruImagePreviewService | None = None
    danbooru_recent_posts_service: DanbooruRecentPostsService | None = None
    prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None
    prompt_scheduled_lora_service: PromptScheduledLoraService | None = None
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]] | None = (
        None
    )
    prompt_segment_preset_source: PromptSegmentPresetSource | None = None
    prompt_spellcheck_service: PromptSpellcheckService | None = None
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None
    danbooru_lookup_dispatcher_factory: DanbooruWikiLookupDispatcherFactory | None = (
        None
    )


def build_prompt_field_widget(request: PromptFieldRouteRequest) -> object | None:
    """Build a prompt editor when the resolved presentation is a prompt box."""

    if request.field_behavior.presentation != FieldPresentation.PROMPT_BOX:
        return None
    profile = _PROMPT_PROFILE_POLICY.prepare_prompt_field_profile(
        field_style=request.field_behavior.style,
        feature_profile=request.prompt_feature_profile,
        syntax_profile=request.prompt_syntax_profile,
    )
    return _PROMPT_EDITOR_FIELD_FACTORY.build_field_widget(
        PromptEditorFieldBuildRequest(
            parent=request.parent,
            field_behavior=request.field_behavior,
            node_name=request.node_name,
            key=request.key,
            value=request.value,
            field_meta=request.field_meta,
            node_type=request.node_type,
            prompt_autocomplete_gateway=request.prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=request.prompt_wildcard_catalog_gateway,
            danbooru_url_import_service=request.danbooru_url_import_service,
            danbooru_wiki_service=request.danbooru_wiki_service,
            danbooru_image_preview_service=request.danbooru_image_preview_service,
            danbooru_recent_posts_service=request.danbooru_recent_posts_service,
            prompt_lora_catalog_service=request.prompt_lora_catalog_service,
            prompt_scheduled_lora_service=request.prompt_scheduled_lora_service,
            scheduled_lora_resolver=request.scheduled_lora_resolver,
            prompt_feature_profile=profile.feature_profile,
            prompt_syntax_profile=profile.syntax_profile,
            prompt_conditioning_context=request.prompt_conditioning_context,
            prompt_segment_preset_source=request.prompt_segment_preset_source,
            prompt_spellcheck_service=request.prompt_spellcheck_service,
            thumbnail_asset_repository=request.thumbnail_asset_repository,
            model_metadata_action_handler=request.model_metadata_action_handler,
            prompt_task_executor_factory=request.prompt_task_executor_factory,
            danbooru_lookup_dispatcher_factory=request.danbooru_lookup_dispatcher_factory,
        )
    )


__all__ = ["PromptFieldRouteRequest", "build_prompt_field_widget"]
