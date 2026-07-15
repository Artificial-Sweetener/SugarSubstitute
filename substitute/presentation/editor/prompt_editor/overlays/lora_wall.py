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

"""Render prompt LoRA wall and picker popup overlays."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPoint, QRect, QSize, Signal
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.widgets.media_wall import (
    MediaWallItem,
    ThumbnailVariantReference,
)
from substitute.presentation.widgets.model_picker import (
    MODEL_PICKER_WALL_PROFILE,
    ModelPickerItem,
    ModelPickerPopup,
    ModelPickerWallView,
    model_picker_item_aspect_ratio,
    wall_items_for_model_picker_items,
)

from ..lora_thumbnail_cache import PromptLoraThumbnailCache

_STANDARD_THUMBNAIL_ROLE = "standard"

LORA_WALL_PROFILE = MODEL_PICKER_WALL_PROFILE


@dataclass(frozen=True, slots=True)
class PromptLoraWallItemRenderState:
    """Describe one prepared LoRA item for media-wall rendering."""

    item_id: str
    title: str
    subtitle: str | None = None
    relative_path: str | None = None
    thumbnail_references: tuple[object, ...] = ()
    aspect_ratio: float = 1.0
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class PromptLoraWallRenderState:
    """Describe prepared LoRA wall render state."""

    items: tuple[PromptLoraWallItemRenderState, ...]
    current_index: int = -1
    visible: bool = True


@dataclass(frozen=True, slots=True)
class PromptLoraActivationIntent:
    """Describe a prepared LoRA activation emitted by the overlay."""

    item_id: str
    payload: object | None = None


class PromptLoraWallOverlay(Protocol):
    """Render prepared LoRA items and relay activation intent."""

    def set_render_state(self, state: PromptLoraWallRenderState) -> None:
        """Replace the prepared LoRA wall state rendered by this overlay."""

    def set_activation_handler(
        self,
        handler: Callable[[PromptLoraActivationIntent], None] | None,
    ) -> None:
        """Set the callback used when a prepared LoRA item is activated."""

    def current_index(self) -> int:
        """Return the highlighted prepared LoRA item index."""

    def set_current_index(self, index: int) -> None:
        """Highlight one prepared LoRA item without accepting it."""

    def preferred_size(self) -> QSize:
        """Return the wall's preferred size for the current render state."""


class PromptLoraWallView(ModelPickerWallView):
    """Render LoRA catalog items through the generic model picker media wall."""

    loraActivated = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        thumbnail_cache: PromptLoraThumbnailCache,
        open_url: UrlOpener | None = None,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    ) -> None:
        """Initialize the LoRA media wall with the shared picker profile."""

        super().__init__(
            parent,
            asset_repository=thumbnail_cache.asset_repository,
            open_url=open_url,
            metadata_action_handler=metadata_action_handler,
        )
        self._catalog_items: tuple[PromptLoraCatalogItem, ...] = ()
        self.modelActivated.connect(self._activate_lora)

    def set_loras(self, items: Iterable[PromptLoraCatalogItem]) -> None:
        """Replace the LoRA catalog items rendered by this wall."""

        catalog_items = tuple(items)
        if catalog_items == self._catalog_items:
            return

        self._catalog_items = catalog_items
        self.set_picker_items(model_picker_items_for_loras(self._catalog_items))

    def loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return the catalog items currently rendered by this wall."""

        return self._catalog_items

    def _activate_lora(self, item: object) -> None:
        """Emit strongly named LoRA activation for catalog payloads."""

        if isinstance(item, ModelPickerItem) and isinstance(
            item.payload,
            PromptLoraCatalogItem,
        ):
            self.loraActivated.emit(item.payload)


class PromptLoraPickerPopup(ModelPickerPopup):
    """Show a floating LoRA picker attached to the prompt editor host."""

    loraActivated = Signal(object)

    def __init__(
        self,
        items: Iterable[PromptLoraCatalogItem],
        *,
        thumbnail_cache: PromptLoraThumbnailCache,
        open_url: UrlOpener | None = None,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build a LoRA picker using the shared model picker popup."""

        materialized_items = tuple(items)
        super().__init__(
            model_picker_items_for_loras(materialized_items),
            asset_repository=thumbnail_cache.asset_repository,
            search_placeholder="Search LoRA",
            open_url=open_url,
            metadata_action_handler=metadata_action_handler,
            parent=parent,
        )
        self.setObjectName("promptLoraPickerPopup")
        self.modelActivated.connect(self._emit_lora)

    def set_loras(self, items: Iterable[PromptLoraCatalogItem]) -> None:
        """Replace LoRA rows while preserving picker filter state."""

        materialized_items = tuple(items)
        self.set_items(model_picker_items_for_loras(materialized_items))

    def _emit_lora(self, item: object) -> None:
        """Emit strongly named LoRA activation for catalog payloads."""

        if isinstance(item, PromptLoraCatalogItem):
            self.loraActivated.emit(item)


def show_lora_picker_popup(
    editor: QWidget,
    items: Iterable[PromptLoraCatalogItem],
    *,
    thumbnail_cache: PromptLoraThumbnailCache,
    global_position: QPoint,
    open_url: UrlOpener | None = None,
    metadata_action_handler: ModelMetadataContextActionHandler | None = None,
) -> PromptLoraPickerPopup:
    """Create and show an editor-attached LoRA picker popup."""

    popup = PromptLoraPickerPopup(
        items,
        thumbnail_cache=thumbnail_cache,
        open_url=open_url,
        metadata_action_handler=metadata_action_handler,
        parent=editor,
    )
    popup.show_attached_to(QRect(global_position, QSize(1, 1)))
    return popup


def wall_items_for_loras(
    items: tuple[PromptLoraCatalogItem, ...],
) -> tuple[MediaWallItem, ...]:
    """Convert LoRA catalog items into generic media wall items."""

    return wall_items_for_model_picker_items(model_picker_items_for_loras(items))


def model_picker_items_for_loras(
    items: tuple[PromptLoraCatalogItem, ...],
) -> tuple[ModelPickerItem, ...]:
    """Convert LoRA catalog items into reusable model picker items."""

    return tuple(
        ModelPickerItem(
            item_id=item.backend_value,
            title=item.display_name or item.basename,
            subtitle=item.display_subtitle,
            backend_value=item.backend_value,
            relative_path=item.relative_path,
            folder=item.folder,
            search_text=item.search_text,
            thumbnail_variants=tuple(
                ThumbnailVariantReference(
                    storage_key=variant.storage_key,
                    size=variant.size,
                    width=variant.width,
                    height=variant.height,
                    content_format=variant.content_format,
                    byte_size=variant.byte_size,
                    role=variant.role,
                )
                for variant in _standard_variants(item)
            ),
            aspect_ratio=lora_item_aspect_ratio(item),
            model_page_url=item.model_page_url,
            payload=item,
            model_kind="loras",
        )
        for item in items
    )


def lora_item_aspect_ratio(item: PromptLoraCatalogItem) -> float:
    """Return the best available thumbnail aspect ratio for one LoRA."""

    return model_picker_item_aspect_ratio(
        tuple(
            ThumbnailVariantReference(
                storage_key=variant.storage_key,
                size=variant.size,
                width=variant.width,
                height=variant.height,
                content_format=variant.content_format,
                byte_size=variant.byte_size,
                role=variant.role,
            )
            for variant in _standard_variants(item)
        )
    )


def _standard_variants(
    item: PromptLoraCatalogItem,
) -> tuple[PromptLoraThumbnailVariant, ...]:
    """Return variants suitable for regular media-wall thumbnail rendering."""

    return tuple(
        variant
        for variant in item.thumbnail_variants
        if variant.role == _STANDARD_THUMBNAIL_ROLE
    )


__all__ = [
    "LORA_WALL_PROFILE",
    "PromptLoraActivationIntent",
    "PromptLoraPickerPopup",
    "PromptLoraWallItemRenderState",
    "PromptLoraWallOverlay",
    "PromptLoraWallRenderState",
    "PromptLoraWallView",
    "lora_item_aspect_ratio",
    "model_picker_items_for_loras",
    "show_lora_picker_popup",
    "wall_items_for_loras",
]
