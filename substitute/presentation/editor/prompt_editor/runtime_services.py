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

"""Group caller-neutral runtime services consumed by prompt editors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptLoraCatalogLookup,
    PromptScheduledLoraService,
    PromptSpellcheckService,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)

from .composition import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorTaskExecutorFactory,
)
from .features import PromptSegmentPresetSource


@dataclass(frozen=True, slots=True)
class PromptEditorRuntimeServices:
    """Collect runtime collaborators shared by every prompt-editor surface."""

    autocomplete_gateway: PromptAutocompleteGateway
    wildcard_catalog_gateway: PromptWildcardCatalogGateway
    danbooru_url_import_service: DanbooruUrlImportService | None = None
    danbooru_wiki_service: DanbooruWikiContentService | None = None
    danbooru_image_preview_service: DanbooruImagePreviewService | None = None
    danbooru_recent_posts_service: DanbooruRecentPostsService | None = None
    lora_catalog_service: PromptLoraCatalogLookup | None = None
    scheduled_lora_service: PromptScheduledLoraService | None = None
    spellcheck_service: PromptSpellcheckService | None = None
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None
    segment_preset_source: PromptSegmentPresetSource | None = None
    open_url: Callable[[str], bool] | None = None
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None
    danbooru_lookup_dispatcher_factory: DanbooruWikiLookupDispatcherFactory | None = (
        None
    )

    def scheduled_lora_service_or_default(self) -> PromptScheduledLoraService:
        """Return the configured scheduled-LoRA service or an editor default."""

        return self.scheduled_lora_service or PromptScheduledLoraService()


__all__ = ["PromptEditorRuntimeServices"]
