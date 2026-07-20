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

"""Define semantic Danbooru wiki block and inline render models."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TypeAlias

from sugarsubstitute_shared.localization import ApplicationText


@dataclass(frozen=True, slots=True)
class DanbooruWikiTextNode:
    """Represent one plain text run inside Danbooru wiki content."""

    text: str


@dataclass(frozen=True, slots=True)
class DanbooruWikiExternalLinkNode:
    """Represent one external clickable link."""

    label: str
    href: str


@dataclass(frozen=True, slots=True)
class DanbooruWikiWikiLinkNode:
    """Represent one internal Danbooru wiki link before tag resolution."""

    target_title: str
    display_label: str


@dataclass(frozen=True, slots=True)
class DanbooruWikiSearchLinkNode:
    """Represent one Danbooru search-expression link such as ``{{tag}}``."""

    query_text: str
    href: str


@dataclass(frozen=True, slots=True)
class DanbooruWikiCodeNode:
    """Represent one inline code run."""

    text: str


@dataclass(frozen=True, slots=True)
class DanbooruWikiLineBreakNode:
    """Represent one explicit inline line break."""


@dataclass(frozen=True, slots=True)
class DanbooruWikiStyledTextNode:
    """Wrap one inline node sequence in emphasis styling."""

    children: tuple["DanbooruWikiInlineNode", ...]
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False


@dataclass(frozen=True, slots=True)
class DanbooruWikiTagChipNode:
    """Represent one confirmed-valid Danbooru tag rendered as a chip."""

    tag_name: str
    display_label: str
    category_name: str | None


DanbooruWikiInlineNode: TypeAlias = (
    DanbooruWikiTextNode
    | DanbooruWikiExternalLinkNode
    | DanbooruWikiWikiLinkNode
    | DanbooruWikiSearchLinkNode
    | DanbooruWikiCodeNode
    | DanbooruWikiLineBreakNode
    | DanbooruWikiStyledTextNode
    | DanbooruWikiTagChipNode
)


@dataclass(frozen=True, slots=True)
class DanbooruWikiParagraphBlock:
    """Represent one paragraph as semantic inline content."""

    inline_nodes: tuple[DanbooruWikiInlineNode, ...]


@dataclass(frozen=True, slots=True)
class DanbooruWikiQuoteBlock:
    """Represent one quote block as semantic inline content."""

    inline_nodes: tuple[DanbooruWikiInlineNode, ...]


@dataclass(frozen=True, slots=True)
class DanbooruWikiListItem:
    """Represent one Danbooru list item plus its nesting depth."""

    inline_nodes: tuple[DanbooruWikiInlineNode, ...]
    depth: int = 1


@dataclass(frozen=True, slots=True)
class DanbooruWikiListBlock:
    """Represent one ordered or unordered Danbooru list."""

    ordered: bool
    items: tuple[DanbooruWikiListItem, ...]


@dataclass(frozen=True, slots=True)
class DanbooruWikiImageReference:
    """Describe one Danbooru image embed and its optional semantic caption."""

    source_kind: str
    source_id: int
    caption_text: str | None = None
    caption_nodes: tuple[DanbooruWikiInlineNode, ...] = ()


@dataclass(frozen=True, slots=True)
class DanbooruWikiImageReferenceBlock:
    """Render one Danbooru image embed group as native thumbnail tiles."""

    items: tuple[DanbooruWikiImageReference, ...]


DanbooruWikiBlock: TypeAlias = (
    DanbooruWikiParagraphBlock
    | DanbooruWikiQuoteBlock
    | DanbooruWikiListBlock
    | DanbooruWikiImageReferenceBlock
)


@dataclass(frozen=True, slots=True)
class DanbooruWikiSectionContent:
    """Group semantic Danbooru blocks under one optional section heading."""

    heading: ApplicationText | None
    blocks: tuple[DanbooruWikiBlock, ...]
    anchor_id: str | None = None


def plain_text_from_inline_nodes(nodes: tuple[DanbooruWikiInlineNode, ...]) -> str:
    """Return flattened human-readable text for one inline node sequence."""

    parts: list[str] = []
    for node in nodes:
        if isinstance(node, DanbooruWikiTextNode):
            parts.append(node.text)
            continue
        if isinstance(node, DanbooruWikiExternalLinkNode):
            parts.append(node.label)
            continue
        if isinstance(node, DanbooruWikiWikiLinkNode):
            parts.append(node.display_label)
            continue
        if isinstance(node, DanbooruWikiSearchLinkNode):
            parts.append(node.query_text)
            continue
        if isinstance(node, DanbooruWikiCodeNode):
            parts.append(node.text)
            continue
        if isinstance(node, DanbooruWikiLineBreakNode):
            parts.append("\n")
            continue
        if isinstance(node, DanbooruWikiTagChipNode):
            parts.append(node.display_label)
            continue
        parts.append(plain_text_from_inline_nodes(node.children))
    return "".join(parts).strip()


def inline_nodes_contain_tag_chips(
    nodes: tuple[DanbooruWikiInlineNode, ...],
) -> bool:
    """Return whether one inline node sequence already contains chip nodes."""

    for node in nodes:
        if isinstance(node, DanbooruWikiTagChipNode):
            return True
        if isinstance(
            node, DanbooruWikiStyledTextNode
        ) and inline_nodes_contain_tag_chips(node.children):
            return True
    return False


def map_inline_nodes(
    nodes: tuple[DanbooruWikiInlineNode, ...],
    mapper: Callable[[DanbooruWikiInlineNode], DanbooruWikiInlineNode],
) -> tuple[DanbooruWikiInlineNode, ...]:
    """Return one recursively mapped inline node sequence."""

    mapped: list[DanbooruWikiInlineNode] = []
    for node in nodes:
        if isinstance(node, DanbooruWikiStyledTextNode):
            node = replace(node, children=map_inline_nodes(node.children, mapper))
        mapped.append(mapper(node))
    return tuple(mapped)


__all__ = [
    "DanbooruWikiBlock",
    "DanbooruWikiCodeNode",
    "DanbooruWikiExternalLinkNode",
    "DanbooruWikiImageReference",
    "DanbooruWikiImageReferenceBlock",
    "DanbooruWikiInlineNode",
    "DanbooruWikiLineBreakNode",
    "DanbooruWikiListItem",
    "DanbooruWikiListBlock",
    "DanbooruWikiParagraphBlock",
    "DanbooruWikiQuoteBlock",
    "DanbooruWikiSearchLinkNode",
    "DanbooruWikiSectionContent",
    "DanbooruWikiStyledTextNode",
    "DanbooruWikiTagChipNode",
    "DanbooruWikiTextNode",
    "DanbooruWikiWikiLinkNode",
    "inline_nodes_contain_tag_chips",
    "map_inline_nodes",
    "plain_text_from_inline_nodes",
]
