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

"""Define presentation DTOs for reusable metadata-backed model pickers."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelThumbnailVariant,
    RichChoiceItem,
)
from substitute.presentation.widgets.media_wall import ThumbnailVariantReference

_DEFAULT_ASPECT_RATIO = 0.72
_STANDARD_THUMBNAIL_ROLE = "standard"


@dataclass(frozen=True, slots=True)
class ModelPickerItem:
    """Describe one item displayed and selected by the reusable model picker."""

    item_id: str
    title: str
    subtitle: str | None
    backend_value: str
    relative_path: str
    folder: str
    search_text: str
    thumbnail_variants: tuple[ThumbnailVariantReference, ...]
    aspect_ratio: float
    model_page_url: str | None
    payload: object
    model_kind: str | None = None


def model_picker_items_from_catalog_items(
    items: tuple[ModelCatalogItem, ...],
) -> tuple[ModelPickerItem, ...]:
    """Return picker items adapted from generic application catalog rows."""

    return tuple(model_picker_item_from_catalog_item(item) for item in items)


def model_picker_items_from_rich_choice_items(
    items: tuple[RichChoiceItem, ...],
) -> tuple[ModelPickerItem, ...]:
    """Return picker items adapted from exact Comfy rich choice rows."""

    return tuple(
        model_picker_item_from_rich_choice_item(index=index, item=item)
        for index, item in enumerate(items)
    )


def model_catalog_items_to_picker_items(
    items: tuple[ModelCatalogItem, ...],
) -> tuple[ModelPickerItem, ...]:
    """Return picker items adapted from generic application catalog rows."""

    return model_picker_items_from_catalog_items(items)


def model_picker_item_from_catalog_item(item: ModelCatalogItem) -> ModelPickerItem:
    """Return one picker item adapted from a generic application catalog row."""

    thumbnail_variants = thumbnail_refs_from_model_variants(item.thumbnail_variants)
    return ModelPickerItem(
        item_id=item.backend_value,
        title=item.display_name or item.basename,
        subtitle=item.display_subtitle,
        backend_value=item.backend_value,
        relative_path=item.relative_path,
        folder=item.folder,
        search_text=item.search_text,
        thumbnail_variants=thumbnail_variants,
        aspect_ratio=model_picker_item_aspect_ratio(thumbnail_variants),
        model_page_url=item.model_page_url,
        payload=item,
        model_kind=item.kind,
    )


def model_picker_item_from_rich_choice_item(
    *,
    index: int,
    item: RichChoiceItem,
) -> ModelPickerItem:
    """Return one picker item adapted from a model-enriched Comfy choice."""

    thumbnail_variants = thumbnail_refs_from_model_variants(item.thumbnail_variants)
    relative_path = _relative_path_for_rich_choice(item)
    folder = _folder_for_rich_choice(item, relative_path)
    return ModelPickerItem(
        item_id=f"{index}:{item.value}" if item.value else f"choice:{index}",
        title=item.title,
        subtitle=item.subtitle,
        backend_value=item.value,
        relative_path=relative_path,
        folder=folder,
        search_text=item.search_text,
        thumbnail_variants=thumbnail_variants,
        aspect_ratio=model_picker_item_aspect_ratio(thumbnail_variants),
        model_page_url=(
            None if item.catalog_item is None else item.catalog_item.model_page_url
        ),
        payload=item,
        model_kind=item.model_kind,
    )


def thumbnail_refs_from_model_variants(
    variants: tuple[ModelThumbnailVariant, ...],
) -> tuple[ThumbnailVariantReference, ...]:
    """Return media-wall thumbnail references adapted from model catalog variants."""

    return tuple(
        ThumbnailVariantReference(
            storage_key=variant.storage_key,
            size=variant.size,
            width=variant.width,
            height=variant.height,
            content_format=variant.content_format,
            byte_size=variant.byte_size,
            role=variant.role,
        )
        for variant in _standard_model_variants(variants)
    )


def model_picker_item_aspect_ratio(
    variants: tuple[ThumbnailVariantReference, ...],
) -> float:
    """Return the best available thumbnail aspect ratio for a picker item."""

    if not variants:
        return _DEFAULT_ASPECT_RATIO
    largest = max(variants, key=lambda variant: variant.size)
    if largest.width <= 0 or largest.height <= 0:
        return _DEFAULT_ASPECT_RATIO
    return largest.width / largest.height


def _standard_model_variants(
    variants: tuple[ModelThumbnailVariant, ...],
) -> tuple[ModelThumbnailVariant, ...]:
    """Return variants suitable for regular media-wall thumbnail rendering."""

    return tuple(
        variant for variant in variants if variant.role == _STANDARD_THUMBNAIL_ROLE
    )


def _relative_path_for_rich_choice(item: RichChoiceItem) -> str:
    """Return the best route/search path for one rich choice item."""

    if item.catalog_item is not None:
        return item.catalog_item.relative_path
    return item.value


def _folder_for_rich_choice(item: RichChoiceItem, relative_path: str) -> str:
    """Return the folder route for a rich choice item."""

    if item.catalog_item is not None:
        return item.catalog_item.folder
    slash_index = max(relative_path.rfind("\\"), relative_path.rfind("/"))
    if slash_index < 0:
        return ""
    return relative_path[:slash_index]


__all__ = [
    "ModelPickerItem",
    "model_catalog_items_to_picker_items",
    "model_picker_item_from_rich_choice_item",
    "model_picker_item_aspect_ratio",
    "model_picker_item_from_catalog_item",
    "model_picker_items_from_catalog_items",
    "model_picker_items_from_rich_choice_items",
    "thumbnail_refs_from_model_variants",
]
