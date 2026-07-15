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

"""Expose Danbooru-specific native presentation helpers."""

from __future__ import annotations

from substitute.application.danbooru import (
    DanbooruWikiBlock,
    DanbooruWikiCodeNode,
    DanbooruWikiExternalLinkNode,
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiInlineNode,
    DanbooruWikiLineBreakNode,
    DanbooruWikiListItem,
    DanbooruWikiListBlock,
    DanbooruWikiParagraphBlock,
    DanbooruWikiQuoteBlock,
    DanbooruWikiSearchLinkNode,
    DanbooruWikiSectionContent,
    DanbooruWikiStyledTextNode,
    DanbooruWikiTagChipNode,
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
    inline_nodes_contain_tag_chips,
    plain_text_from_inline_nodes,
)
from .wiki_block_parser import DanbooruWikiBlockParser
from .wiki_content_view import DanbooruWikiContentView
from .wiki_image_card import DanbooruWikiImageCard
from .wiki_inline_flow import DanbooruWikiInlineFlow
from .wiki_rich_text_renderer import (
    DanbooruWikiRichTextRenderer,
    DanbooruWikiRichTextRenderResult,
)
from .wiki_section_widget import DanbooruWikiSectionWidget

__all__ = [
    "DanbooruWikiBlock",
    "DanbooruWikiBlockParser",
    "DanbooruWikiCodeNode",
    "DanbooruWikiContentView",
    "DanbooruWikiExternalLinkNode",
    "DanbooruWikiImageCard",
    "DanbooruWikiImageReference",
    "DanbooruWikiImageReferenceBlock",
    "DanbooruWikiInlineFlow",
    "DanbooruWikiInlineNode",
    "DanbooruWikiLineBreakNode",
    "DanbooruWikiListItem",
    "DanbooruWikiListBlock",
    "DanbooruWikiParagraphBlock",
    "DanbooruWikiQuoteBlock",
    "DanbooruWikiRichTextRenderer",
    "DanbooruWikiRichTextRenderResult",
    "DanbooruWikiSearchLinkNode",
    "DanbooruWikiSectionContent",
    "DanbooruWikiSectionWidget",
    "DanbooruWikiStyledTextNode",
    "DanbooruWikiTagChipNode",
    "DanbooruWikiTextNode",
    "DanbooruWikiWikiLinkNode",
    "inline_nodes_contain_tag_chips",
    "plain_text_from_inline_nodes",
]
