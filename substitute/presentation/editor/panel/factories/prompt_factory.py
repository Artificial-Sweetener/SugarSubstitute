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

"""Build prompt-editor field widgets from prepared prompt field inputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from PySide6.QtWidgets import QWidget

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
from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSpellcheckService,
    PromptSyntaxProfile,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.presentation.editor.panel.service_bundle import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorTaskExecutorFactory,
)
from substitute.shared.logging.logger import get_logger, log_timing

_LOGGER = get_logger("presentation.editor.panel.factories.prompt")


@dataclass(frozen=True, slots=True)
class PromptEditorFieldBuildRequest:
    """Carry prepared prompt field data and injected prompt-editor services."""

    parent: QWidget | None
    field_behavior: FieldBehavior
    node_name: str
    key: str
    value: object
    field_meta: dict[str, object]
    prompt_autocomplete_gateway: PromptAutocompleteGateway
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway
    prompt_feature_profile: PromptEditorFeatureProfile
    prompt_syntax_profile: PromptSyntaxProfile
    node_type: object = ""
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


class PromptEditorFieldFactory:
    """Build prompt editor widgets for prompt-box field presentations."""

    def build_field_widget(
        self, request: PromptEditorFieldBuildRequest
    ) -> object | None:
        """Return a prompt editor widget, or None when this field is not prompt text."""

        if request.field_behavior.presentation != FieldPresentation.PROMPT_BOX:
            return None
        if not isinstance(request.value, str):
            return None

        return build_prompt_editor_widget(
            request.parent,
            request.value,
            cube_alias=str(request.field_meta.get("cube_alias", "")),
            node_name=request.node_name,
            field_key=request.key,
            node_class=str(request.node_type if request.node_type is not None else ""),
            prompt_autocomplete_gateway=request.prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=request.prompt_wildcard_catalog_gateway,
            danbooru_url_import_service=request.danbooru_url_import_service,
            danbooru_wiki_service=request.danbooru_wiki_service,
            danbooru_image_preview_service=request.danbooru_image_preview_service,
            danbooru_recent_posts_service=request.danbooru_recent_posts_service,
            prompt_lora_catalog_service=request.prompt_lora_catalog_service,
            prompt_scheduled_lora_service=request.prompt_scheduled_lora_service,
            scheduled_lora_resolver=request.scheduled_lora_resolver,
            prompt_segment_preset_source=request.prompt_segment_preset_source,
            prompt_spellcheck_service=request.prompt_spellcheck_service,
            thumbnail_asset_repository=request.thumbnail_asset_repository,
            model_metadata_action_handler=request.model_metadata_action_handler,
            prompt_task_executor_factory=request.prompt_task_executor_factory,
            danbooru_lookup_dispatcher_factory=(
                request.danbooru_lookup_dispatcher_factory
            ),
            prompt_syntax_profile=request.prompt_syntax_profile,
            prompt_feature_profile=request.prompt_feature_profile,
        )


def build_prompt_editor_widget(
    parent: QWidget | None,
    value: str,
    *,
    cube_alias: str | None = None,
    node_name: str = "",
    field_key: str = "",
    node_class: str = "",
    prompt_autocomplete_gateway: PromptAutocompleteGateway,
    prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
    prompt_syntax_profile: PromptSyntaxProfile,
    danbooru_url_import_service: DanbooruUrlImportService | None = None,
    danbooru_wiki_service: DanbooruWikiContentService | None = None,
    danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
    danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
    prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
    prompt_scheduled_lora_service: PromptScheduledLoraService | None = None,
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    | None = None,
    prompt_feature_profile: PromptEditorFeatureProfile,
    prompt_segment_preset_source: PromptSegmentPresetSource | None = None,
    prompt_spellcheck_service: PromptSpellcheckService | None = None,
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None,
    danbooru_lookup_dispatcher_factory: (
        DanbooruWikiLookupDispatcherFactory | None
    ) = None,
) -> object:
    """Create one prompt editor with its initial source text value."""

    trace_context = {
        "cube_alias": cube_alias or "",
        "node_name": node_name,
        "field_key": field_key,
        "node_class": node_class,
        "text_length": len(value),
        "projection_mode": "live",
    }
    widget_started_at = perf_counter()
    construction_started_at = panel_projection_observability_started_at()
    prompt_editor_kwargs: dict[str, object] = {
        "prompt_autocomplete_gateway": prompt_autocomplete_gateway,
        "prompt_wildcard_catalog_gateway": prompt_wildcard_catalog_gateway,
        "danbooru_url_import_service": danbooru_url_import_service,
        "danbooru_wiki_service": danbooru_wiki_service,
        "danbooru_image_preview_service": danbooru_image_preview_service,
        "danbooru_recent_posts_service": danbooru_recent_posts_service,
        "prompt_feature_profile": prompt_feature_profile,
        "prompt_syntax_profile": prompt_syntax_profile,
        "prompt_lora_catalog_service": prompt_lora_catalog_service,
        "prompt_scheduled_lora_service": prompt_scheduled_lora_service,
        "scheduled_lora_resolver": scheduled_lora_resolver,
        "prompt_segment_preset_source": prompt_segment_preset_source,
        "prompt_spellcheck_service": prompt_spellcheck_service,
        "thumbnail_asset_repository": thumbnail_asset_repository,
        "model_metadata_action_handler": model_metadata_action_handler,
        "prompt_task_executor_factory": prompt_task_executor_factory,
        "danbooru_lookup_dispatcher_factory": danbooru_lookup_dispatcher_factory,
    }
    field = cast(Any, PromptEditor)(parent, **prompt_editor_kwargs)
    log_panel_projection_timing(
        "prompt_factory.editor_construct",
        started_at=construction_started_at,
        cube_alias=trace_context["cube_alias"],
        node_name=trace_context["node_name"],
        field_key=trace_context["field_key"],
        node_class=trace_context["node_class"],
        text_length=trace_context["text_length"],
        projection_mode=trace_context["projection_mode"],
        has_lora_catalog=prompt_lora_catalog_service is not None,
        has_spellcheck_service=prompt_spellcheck_service is not None,
        has_segment_presets=prompt_segment_preset_source is not None,
    )
    log_timing(
        _LOGGER,
        "Constructed prompt editor shell",
        started_at=construction_started_at,
        text_length=len(value),
        has_lora_catalog=prompt_lora_catalog_service is not None,
        has_spellcheck_service=prompt_spellcheck_service is not None,
        has_segment_presets=prompt_segment_preset_source is not None,
    )
    text_started_at = panel_projection_observability_started_at()
    replace_baseline_source_text = getattr(field, "replaceBaselineSourceText", None)
    if callable(replace_baseline_source_text):
        replace_baseline_source_text(value)
    else:
        field.setPlainText(value)
    log_panel_projection_timing(
        "prompt_factory.initial_text_assigned",
        started_at=text_started_at,
        cube_alias=trace_context["cube_alias"],
        node_name=trace_context["node_name"],
        field_key=trace_context["field_key"],
        node_class=trace_context["node_class"],
        text_length=trace_context["text_length"],
        projection_mode=trace_context["projection_mode"],
    )
    log_timing(
        _LOGGER,
        "Assigned prompt editor initial text",
        started_at=text_started_at,
        text_length=len(value),
    )
    log_timing(
        _LOGGER,
        "Built prompt editor widget",
        started_at=widget_started_at,
        text_length=len(value),
    )
    return field
