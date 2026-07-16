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

"""Adapt exact Comfy model options into presentation-ready catalog choices."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace

from substitute.application.model_metadata import (
    ModelCatalogItem,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.model_choice_resolution_adapter")


def catalog_resolution(
    *,
    options: Sequence[str],
    catalog_items: Sequence[ModelCatalogItem],
    matched_kind: str,
    reason: str,
) -> RichChoiceResolution:
    """Resolve exact option values against prepared catalog rows."""

    items_by_value = _catalog_items_by_value(catalog_items)
    rendered_items: list[RichChoiceItem] = []
    enriched_count = 0
    ambiguous_count = 0
    unmatched_count = 0
    for option in options:
        candidates = items_by_value.get(str(option), ())
        if not candidates:
            unmatched_count += 1
            rendered_items.append(_literal_model_choice_item(str(option)))
            continue
        is_ambiguous = len(candidates) > 1
        if is_ambiguous:
            ambiguous_count += 1
        else:
            enriched_count += 1
        rendered_items.append(
            _rich_choice_item(str(option), candidates[0], is_ambiguous)
        )

    should_use_rich_picker = bool(options) and (
        enriched_count > 0 or ambiguous_count > 0
    )
    return RichChoiceResolution(
        items=tuple(rendered_items),
        should_use_rich_picker=should_use_rich_picker,
        matched_kinds=(matched_kind,),
        option_count=len(options),
        enriched_count=enriched_count,
        ambiguous_count=ambiguous_count,
        unmatched_count=unmatched_count,
        reason=reason,
    )


def literal_model_choice_resolution(
    *,
    options: Sequence[str],
    matched_kind: str | None,
) -> RichChoiceResolution:
    """Return a picker-forcing resolution from exact Comfy options only."""

    items = tuple(_literal_model_choice_item(str(option)) for option in options)
    matched_kinds = (matched_kind,) if matched_kind else ()
    return RichChoiceResolution(
        items=items,
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=len(items),
        enriched_count=0,
        ambiguous_count=0,
        unmatched_count=len(items),
        reason="model-backed field rendered before metadata enrichment",
    )


def _catalog_items_by_value(
    catalog_items: Sequence[ModelCatalogItem],
) -> Mapping[str, tuple[ModelCatalogItem, ...]]:
    """Return catalog items grouped by exact Comfy backend value."""

    counter = Counter(item.backend_value for item in catalog_items)
    grouped: dict[str, list[ModelCatalogItem]] = {}
    for item in catalog_items:
        grouped.setdefault(item.backend_value, []).append(item)
    return {
        value: tuple(
            _with_collision_metadata(item, collision_count=counter[value])
            for item in items
        )
        for value, items in grouped.items()
    }


def _with_collision_metadata(
    item: ModelCatalogItem,
    *,
    collision_count: int,
) -> ModelCatalogItem:
    """Return item collision metadata without mutating cached catalog rows."""

    if item.collision_count == collision_count and item.has_collision == (
        collision_count > 1
    ):
        return item
    try:
        return replace(
            item,
            collision_count=collision_count,
            has_collision=collision_count > 1,
        )
    except TypeError as error:
        log_warning(
            _LOGGER,
            "Failed to patch model catalog collision metadata",
            model_kind=item.kind,
            backend_value=item.backend_value,
            error_type=type(error).__name__,
        )
        return item


def _rich_choice_item(
    value: str,
    catalog_item: ModelCatalogItem,
    is_ambiguous: bool,
) -> RichChoiceItem:
    """Return one model-enriched choice item from cached catalog metadata."""

    title = catalog_item.display_name or _literal_model_choice_title(value)
    search_parts = (
        catalog_item.search_text,
        title,
        value.replace("\\", "/"),
        catalog_item.display_subtitle or "",
    )
    return RichChoiceItem(
        value=value,
        title=title,
        subtitle=catalog_item.display_subtitle,
        search_text=" ".join(part for part in search_parts if part).casefold(),
        model_kind=catalog_item.kind,
        catalog_item=catalog_item,
        thumbnail_variants=catalog_item.thumbnail_variants,
        is_enriched=not is_ambiguous,
        is_ambiguous=is_ambiguous,
    )


def _literal_model_choice_item(value: str) -> RichChoiceItem:
    """Return one selectable model choice without metadata enrichment."""

    title = _literal_model_choice_title(value)
    return RichChoiceItem(
        value=value,
        title=title,
        subtitle=None,
        search_text=f"{title} {value}".replace("\\", "/").casefold(),
        model_kind=None,
        catalog_item=None,
        thumbnail_variants=(),
        is_enriched=False,
        is_ambiguous=False,
    )


def _literal_model_choice_title(value: str) -> str:
    """Return a readable title for a literal model backend value."""

    normalized = str(value).replace("\\", "/").strip()
    if not normalized:
        return ""
    title = normalized.rsplit("/", 1)[-1]
    for suffix in (".safetensors", ".ckpt", ".pt"):
        if title.casefold().endswith(suffix):
            return title[: -len(suffix)] or title
    return title


__all__ = ["catalog_resolution", "literal_model_choice_resolution"]
