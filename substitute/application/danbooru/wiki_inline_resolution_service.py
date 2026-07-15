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

"""Resolve semantic Danbooru wiki inline nodes into chip-eligible tags."""

from __future__ import annotations

from substitute.application.danbooru.wiki_render_models import (
    DanbooruWikiBlock,
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiInlineNode,
    DanbooruWikiListItem,
    DanbooruWikiListBlock,
    DanbooruWikiParagraphBlock,
    DanbooruWikiQuoteBlock,
    DanbooruWikiSectionContent,
    DanbooruWikiTagChipNode,
    DanbooruWikiWikiLinkNode,
    map_inline_nodes,
)
from substitute.application.ports.danbooru_cache_repository import (
    DanbooruCacheRepository,
)
from substitute.domain.danbooru import (
    DanbooruLookupStatus,
    DanbooruTagRecord,
)

_CATEGORY_NAMES = {
    0: "general",
    1: "artist",
    3: "copyright",
    4: "character",
    5: "meta",
}
_NON_TAG_WIKI_NAMESPACES = frozenset(
    {
        "help",
        "api",
        "howto",
        "tag group",
        "pool group",
    }
)


class DanbooruWikiInlineResolutionService:
    """Resolve semantic inline nodes into chip-eligible tag nodes by title shape."""

    def __init__(
        self,
        *,
        cache_repository: DanbooruCacheRepository,
    ) -> None:
        """Store the cache used for optional tag-category enrichment."""

        self._cache_repository = cache_repository

    def resolve_sections(
        self,
        sections: tuple[DanbooruWikiSectionContent, ...],
    ) -> tuple[DanbooruWikiSectionContent, ...]:
        """Return sections whose ordinary wiki titles have become chip nodes."""

        resolved_category_by_title: dict[str, str | None] = {}

        def resolve_inline_nodes(
            nodes: tuple[DanbooruWikiInlineNode, ...],
        ) -> tuple[DanbooruWikiInlineNode, ...]:
            """Resolve one inline node sequence through title-based chip rules."""

            return map_inline_nodes(
                nodes,
                lambda node: self._resolve_inline_node(
                    node,
                    resolved_category_by_title=resolved_category_by_title,
                ),
            )

        resolved_sections: list[DanbooruWikiSectionContent] = []
        for section in sections:
            resolved_blocks: list[DanbooruWikiBlock] = []
            for block in section.blocks:
                if isinstance(block, DanbooruWikiParagraphBlock):
                    resolved_blocks.append(
                        DanbooruWikiParagraphBlock(
                            inline_nodes=resolve_inline_nodes(block.inline_nodes)
                        )
                    )
                    continue
                if isinstance(block, DanbooruWikiQuoteBlock):
                    resolved_blocks.append(
                        DanbooruWikiQuoteBlock(
                            inline_nodes=resolve_inline_nodes(block.inline_nodes)
                        )
                    )
                    continue
                if isinstance(block, DanbooruWikiListBlock):
                    resolved_blocks.append(
                        DanbooruWikiListBlock(
                            ordered=block.ordered,
                            items=tuple(
                                DanbooruWikiListItem(
                                    inline_nodes=resolve_inline_nodes(
                                        item.inline_nodes
                                    ),
                                    depth=item.depth,
                                )
                                for item in block.items
                            ),
                        )
                    )
                    continue
                resolved_blocks.append(
                    DanbooruWikiImageReferenceBlock(
                        items=tuple(
                            _replace_caption_nodes(
                                item,
                                resolve_inline_nodes(item.caption_nodes),
                            )
                            for item in block.items
                        )
                    )
                )
            resolved_sections.append(
                DanbooruWikiSectionContent(
                    heading=section.heading,
                    blocks=tuple(resolved_blocks),
                )
            )
        return tuple(resolved_sections)

    def _resolve_inline_node(
        self,
        node: DanbooruWikiInlineNode,
        *,
        resolved_category_by_title: dict[str, str | None],
    ) -> DanbooruWikiInlineNode:
        """Return one inline node rewritten when its title looks like a tag."""

        if not isinstance(node, DanbooruWikiWikiLinkNode):
            return node
        if not _is_chip_eligible_title(node.target_title):
            return node
        if node.target_title not in resolved_category_by_title:
            resolved_category_by_title[node.target_title] = self._resolve_tag_category(
                node.target_title
            )
        return DanbooruWikiTagChipNode(
            tag_name=node.target_title,
            display_label=node.display_label,
            category_name=resolved_category_by_title[node.target_title],
        )

    def _resolve_tag_category(self, title: str) -> str | None:
        """Return cached category enrichment for one tag-like wiki target."""

        cached_entry = self._cache_repository.load_cached_tag(title)
        if cached_entry is not None:
            if cached_entry.lookup_status is DanbooruLookupStatus.FOUND:
                return _category_name_from_tag(cached_entry.tag)
        return None


def _category_name_from_tag(tag_record: DanbooruTagRecord | None) -> str | None:
    """Return the human-readable category label for one tag record."""

    if tag_record is None:
        return None
    return _CATEGORY_NAMES.get(tag_record.category)


def _is_chip_eligible_title(title: str) -> bool:
    """Return whether one wiki title should render as a tag chip by default."""

    namespace = _normalized_namespace_prefix(title)
    if namespace is None:
        return True
    return namespace not in _NON_TAG_WIKI_NAMESPACES


def _normalized_namespace_prefix(title: str) -> str | None:
    """Return the normalized namespace prefix before one leading wiki colon."""

    normalized = title.strip().casefold()
    if ":" not in normalized:
        return None
    prefix, _separator, _rest = normalized.partition(":")
    return prefix.replace("_", " ").strip() or None


def _replace_caption_nodes(
    item: DanbooruWikiImageReference,
    caption_nodes: tuple[DanbooruWikiInlineNode, ...],
) -> DanbooruWikiImageReference:
    """Return one image reference with resolved semantic caption nodes."""

    return DanbooruWikiImageReference(
        source_kind=item.source_kind,
        source_id=item.source_id,
        caption_text=item.caption_text,
        caption_nodes=caption_nodes,
    )


__all__ = [
    "DanbooruWikiInlineResolutionService",
]
