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

"""Project canonical model records into prompt-editor LoRA catalog items."""

from __future__ import annotations

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelThumbnailVariant,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.lora.ranking import strip_lora_extension


def project_lora_catalog_items(
    models: tuple[ModelCatalogItem, ...],
) -> tuple[PromptLoraCatalogItem, ...]:
    """Return deterministically ordered prompt LoRA items for canonical models."""

    items = tuple(_project_lora_catalog_item(model) for model in models)
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.display_name.casefold(),
                item.relative_path.casefold(),
            ),
        )
    )


def _project_lora_catalog_item(model: ModelCatalogItem) -> PromptLoraCatalogItem:
    """Project one canonical model record into a prompt-editor catalog item."""

    return PromptLoraCatalogItem(
        display_name=model.display_name,
        display_subtitle=model.display_subtitle,
        prompt_name=strip_lora_extension(model.backend_value),
        backend_value=model.backend_value,
        relative_path=model.relative_path,
        folder=model.folder,
        basename=model.basename,
        extension=model.extension,
        thumbnail_variants=tuple(
            _project_thumbnail_variant(variant) for variant in model.thumbnail_variants
        ),
        base_model=model.base_model,
        trained_words=model.trained_words,
        tags=model.tags,
        model_page_url=model.model_page_url,
        collision_key=model.collision_key,
        collision_count=model.collision_count,
        has_collision=model.has_collision,
        search_text=_search_text(model),
    )


def _project_thumbnail_variant(
    variant: ModelThumbnailVariant,
) -> PromptLoraThumbnailVariant:
    """Project one canonical thumbnail reference for prompt presentation."""

    return PromptLoraThumbnailVariant(
        size=variant.size,
        storage_key=variant.storage_key,
        width=variant.width,
        height=variant.height,
        content_format=variant.content_format,
        byte_size=variant.byte_size,
        role=variant.role,
    )


def _search_text(model: ModelCatalogItem) -> str:
    """Return normalized search text for one projected LoRA item."""

    return (
        " ".join(
            (
                model.display_name,
                model.display_subtitle or "",
                model.backend_value,
                model.relative_path,
                model.folder,
                model.basename,
                model.base_model or "",
                " ".join(model.trained_words),
                " ".join(model.tags),
            )
        )
        .replace("\\", "/")
        .casefold()
    )


__all__ = ["project_lora_catalog_items"]
