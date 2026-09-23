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

"""Own prompt-editor reactions to externally refreshed catalog state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .async_work import PromptEditorMainThreadDispatcher
from .features import (
    PromptLoraMetadataPresentation,
    PromptLoraMetadataRefreshBindings,
    PromptLoraMetadataRefreshLifecycle,
    PromptSegmentPresetController,
)
from .interactions import PromptInteractionController
from .lora_thumbnail_cache import PromptLoraThumbnailCache
from .projection.surface import PromptProjectionSurface


@dataclass(frozen=True, slots=True)
class PromptEditorCatalogRefreshBindings:
    """Declare catalog-dependent cache and presentation operations."""

    mark_lora_metadata_dirty: Callable[[], None]
    refresh_lora_metadata_if_visible: Callable[[], bool]
    schedule_lora_metadata_catchup: Callable[[], None]
    clear_thumbnail_cache: Callable[[], None]
    refresh_thumbnail_paint: Callable[[str], None]
    update_host: Callable[[], None]
    refresh_segment_presets: Callable[[str], object]


@dataclass(frozen=True, slots=True)
class PromptEditorCatalogRefreshFacade:
    """Publish external catalog changes through their mounted feature owners."""

    bindings: PromptEditorCatalogRefreshBindings

    def mark_lora_metadata_dirty(self) -> None:
        """Mark catalog-backed LoRA metadata stale."""

        self.bindings.mark_lora_metadata_dirty()

    def refresh_lora_metadata_if_visible(self) -> bool:
        """Refresh stale LoRA metadata for a visible editor."""

        return self.bindings.refresh_lora_metadata_if_visible()

    def schedule_lora_metadata_catchup_if_needed(self) -> None:
        """Queue at most one catchup for stale LoRA metadata."""

        self.bindings.schedule_lora_metadata_catchup()

    def clear_lora_thumbnail_cache(self) -> None:
        """Invalidate decoded thumbnails and repaint every dependent surface."""

        self.bindings.clear_thumbnail_cache()
        self.bindings.refresh_thumbnail_paint("lora_thumbnail_cache_clear")
        self.bindings.update_host()

    def refresh_prompt_segment_presets(self, *, reason: str) -> None:
        """Refresh saved prompt-segment state from its prepared source."""

        self.bindings.refresh_segment_presets(reason)


def build_prompt_editor_catalog_refresh_facade(
    *,
    is_visible: Callable[[], bool],
    interaction: PromptInteractionController,
    lora_presentation: PromptLoraMetadataPresentation,
    dispatcher: PromptEditorMainThreadDispatcher,
    thumbnail_cache: PromptLoraThumbnailCache,
    surface: PromptProjectionSurface,
    segment_presets: PromptSegmentPresetController,
    update_host: Callable[[], None],
) -> PromptEditorCatalogRefreshFacade:
    """Bind mounted catalog consumers to one refresh publication facade."""

    lora_metadata = PromptLoraMetadataRefreshLifecycle(
        bindings=PromptLoraMetadataRefreshBindings(
            is_visible=is_visible,
            has_lora_spans=interaction.has_lora_spans,
            refresh_render_metadata=(
                lambda reason: interaction.refresh_lora_render_metadata(reason=reason)
            ),
        ),
        presentation=lora_presentation,
        dispatcher=dispatcher,
    )
    return PromptEditorCatalogRefreshFacade(
        bindings=PromptEditorCatalogRefreshBindings(
            mark_lora_metadata_dirty=lora_metadata.mark_dirty,
            refresh_lora_metadata_if_visible=lora_metadata.refresh_if_visible,
            schedule_lora_metadata_catchup=(lora_metadata.schedule_catchup_if_needed),
            clear_thumbnail_cache=thumbnail_cache.clear,
            refresh_thumbnail_paint=(
                lambda reason: surface.refresh_lora_thumbnail_paint(reason=reason)
            ),
            update_host=update_host,
            refresh_segment_presets=(
                lambda reason: segment_presets.refresh_menu_model(reason=reason)
            ),
        ),
    )


__all__ = [
    "PromptEditorCatalogRefreshBindings",
    "PromptEditorCatalogRefreshFacade",
    "build_prompt_editor_catalog_refresh_facade",
]
