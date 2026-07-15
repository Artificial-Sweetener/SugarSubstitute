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

"""Parse Danbooru DText into semantic block and inline render models."""

from __future__ import annotations

import re
from urllib.parse import quote

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
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
    plain_text_from_inline_nodes,
)

_HEADING_PATTERN = re.compile(
    r"^h(?P<level>[1-6])(?:#(?P<anchor>[A-Za-z0-9_-]+))?\.\s*(?P<content>.+?)\s*$",
    re.IGNORECASE,
)
_ORDERED_LIST_PATTERN = re.compile(r"^(?P<marker>#+|\d+\.)\s+(?P<content>.+)$")
_UNORDERED_LIST_PATTERN = re.compile(r"^(?P<marker>\*+|-+)\s+(?P<content>.+)$")
_QUOTE_PATTERN = re.compile(r"^bq\.\s+(?P<content>.+)$")
_IMAGE_PATTERN = re.compile(
    r"^!(?P<kind>post|asset)\s+#(?P<reference_id>\d+)\b(?:\s*:\s*(?P<caption>.+))?$"
)
_QUOTED_LINK_PATTERN = re.compile(
    r'^"(?P<label>[^"\n]+)":(?P<target>https?://[^\s<]+|/[^\s<]+|#[^\s<]+)$'
)
_POST_LINK_PATTERN = re.compile(r"^(?P<label>[Pp]ost\s+#(?P<post_id>\d+))$")
_INLINE_TOKEN_PATTERN = re.compile(
    r'("[^"\n]+":(?:https?://[^\s<]+|/[^\s<]+|#[^\s<]+)|\[\[[^\]]+\]\]|https?://[^\s<]+|'
    r"[Pp]ost\s+#\d+|\[br\]|'''[^']+'''|''[^']+''|`[^`]+`|\{\{[^{}\n]+\}\}|\[b\].+?\[/b\]|\[i\].+?\[/i\]|\[u\].+?\[/u\]|\[code\].+?\[/code\]|<b>.+?</b>|<i>.+?</i>|<u>.+?</u>|<s>.+?</s>)"
)
_DANBOORU_BASE_URL = "https://danbooru.donmai.us"
_TRAILING_URL_PUNCTUATION = ".,;:!?)"
_WIKI_QUALIFIER_PATTERN = re.compile(r"\s+\([^)]*\)$")
_FRAGMENT_SCHEME_PREFIX = "danbooru-fragment:"


class DanbooruWikiBlockParser:
    """Parse Danbooru DText into semantic sections and block structures."""

    def parse(self, body_dtext: str) -> tuple[DanbooruWikiSectionContent, ...]:
        """Return semantic render sections for one Danbooru wiki DText body."""

        sections: list[DanbooruWikiSectionContent] = []
        current_heading: str | None = None
        current_anchor_id: str | None = None
        current_blocks: list[DanbooruWikiBlock] = []
        lines = body_dtext.splitlines()
        index = 0

        def flush_section() -> None:
            """Append the current section when it contains renderable content."""

            nonlocal current_heading, current_anchor_id, current_blocks
            if current_heading is None and not current_blocks:
                return
            sections.append(
                DanbooruWikiSectionContent(
                    heading=current_heading,
                    blocks=tuple(current_blocks),
                    anchor_id=current_anchor_id,
                )
            )
            current_heading = None
            current_blocks = []
            current_anchor_id = None

        while index < len(lines):
            line = lines[index].strip()
            if not line:
                index += 1
                continue
            if _is_expand_macro_line(line):
                index += 1
                continue

            heading_match = _HEADING_PATTERN.match(line)
            if heading_match is not None:
                flush_section()
                current_heading = plain_text_from_inline_nodes(
                    _parse_inline_nodes(heading_match.group("content"))
                )
                current_anchor_id = heading_match.group("anchor")
                index += 1
                continue

            list_image_group = _parse_list_image_group(lines, start_index=index)
            if list_image_group is not None:
                block, consumed_lines = list_image_group
                current_blocks.append(block)
                index += consumed_lines
                continue

            image_reference = _parse_direct_image_reference(line)
            if image_reference is not None:
                current_blocks.append(
                    DanbooruWikiImageReferenceBlock(items=(image_reference,))
                )
                index += 1
                continue

            quote_match = _QUOTE_PATTERN.match(line)
            if quote_match is not None:
                quote_lines = [quote_match.group("content")]
                index += 1
                while index < len(lines):
                    current_line = lines[index].strip()
                    if not current_line:
                        index += 1
                        break
                    continued_quote_match = _QUOTE_PATTERN.match(current_line)
                    if continued_quote_match is None:
                        break
                    quote_lines.append(continued_quote_match.group("content"))
                    index += 1
                current_blocks.append(
                    DanbooruWikiQuoteBlock(
                        inline_nodes=_parse_inline_nodes(" ".join(quote_lines))
                    )
                )
                continue

            ordered_match = _ORDERED_LIST_PATTERN.match(line)
            unordered_match = _UNORDERED_LIST_PATTERN.match(line)
            if ordered_match is not None or unordered_match is not None:
                ordered = ordered_match is not None
                list_items: list[DanbooruWikiListItem] = []
                while index < len(lines):
                    current_line = lines[index].strip()
                    if not current_line:
                        next_index = _skip_blank_lines(lines, start_index=index)
                        if next_index >= len(lines):
                            index = next_index
                            break
                        next_line = lines[next_index].strip()
                        next_item_match = (
                            _ORDERED_LIST_PATTERN.match(next_line)
                            if ordered
                            else _UNORDERED_LIST_PATTERN.match(next_line)
                        )
                        if next_item_match is None:
                            index = next_index
                            break
                        index = next_index
                        continue
                    item_match = (
                        _ORDERED_LIST_PATTERN.match(current_line)
                        if ordered
                        else _UNORDERED_LIST_PATTERN.match(current_line)
                    )
                    if item_match is None:
                        break
                    list_items.append(
                        DanbooruWikiListItem(
                            inline_nodes=_parse_inline_nodes(
                                item_match.group("content")
                            ),
                            depth=_list_depth(
                                item_match.group("marker"),
                                ordered=ordered,
                            ),
                        )
                    )
                    index += 1
                current_blocks.append(
                    DanbooruWikiListBlock(ordered=ordered, items=tuple(list_items))
                )
                continue

            paragraph_lines = [_normalized_paragraph_line(line)]
            index += 1
            while index < len(lines):
                current_line = lines[index].strip()
                if not current_line:
                    index += 1
                    break
                if _is_expand_macro_line(current_line):
                    index += 1
                    continue
                if _HEADING_PATTERN.match(current_line) is not None:
                    break
                if _QUOTE_PATTERN.match(current_line) is not None:
                    break
                if _parse_direct_image_reference(current_line) is not None:
                    break
                if (
                    _ORDERED_LIST_PATTERN.match(current_line) is not None
                    or _UNORDERED_LIST_PATTERN.match(current_line) is not None
                ):
                    break
                paragraph_lines.append(_normalized_paragraph_line(current_line))
                index += 1
            current_blocks.append(
                DanbooruWikiParagraphBlock(
                    inline_nodes=_parse_inline_nodes(" ".join(paragraph_lines))
                )
            )

        flush_section()
        return tuple(sections)


def _parse_direct_image_reference(line: str) -> DanbooruWikiImageReference | None:
    """Return one direct Danbooru image embed from a non-list line."""

    image_match = _IMAGE_PATTERN.match(line.strip())
    if image_match is None:
        return None
    caption = image_match.group("caption")
    normalized_caption = (
        None if caption is None or not caption.strip() else caption.strip()
    )
    caption_nodes = (
        () if normalized_caption is None else _parse_inline_nodes(normalized_caption)
    )
    return DanbooruWikiImageReference(
        source_kind=image_match.group("kind"),
        source_id=int(image_match.group("reference_id")),
        caption_text=(
            None
            if normalized_caption is None
            else plain_text_from_inline_nodes(caption_nodes)
        ),
        caption_nodes=caption_nodes,
    )


def _parse_list_image_group(
    lines: list[str],
    *,
    start_index: int,
) -> tuple[DanbooruWikiImageReferenceBlock, int] | None:
    """Return one grouped list-image block plus the number of consumed lines."""

    items: list[DanbooruWikiImageReference] = []
    index = start_index
    while index < len(lines):
        current_line = lines[index].strip()
        if not current_line:
            next_index = _skip_blank_lines(lines, start_index=index)
            if next_index >= len(lines):
                index = next_index
                break
            current_line = lines[next_index].strip()
            index = next_index
        item_match = _ORDERED_LIST_PATTERN.match(current_line)
        if item_match is None:
            item_match = _UNORDERED_LIST_PATTERN.match(current_line)
        if item_match is None:
            break
        image_reference = _parse_direct_image_reference(
            item_match.group("content").strip()
        )
        if image_reference is None:
            break
        items.append(image_reference)
        index += 1
    if not items:
        return None
    return DanbooruWikiImageReferenceBlock(items=tuple(items)), index - start_index


def _parse_inline_nodes(text: str) -> tuple[DanbooruWikiInlineNode, ...]:
    """Parse inline Danbooru markup into semantic inline nodes."""

    parts: list[DanbooruWikiInlineNode] = []
    last_end = 0
    for match in _INLINE_TOKEN_PATTERN.finditer(text):
        if match.start() > last_end:
            parts.append(DanbooruWikiTextNode(text=text[last_end : match.start()]))
        token_nodes = _parse_inline_token(match.group(0))
        parts.extend(token_nodes)
        last_end = match.end()
    if last_end < len(text):
        parts.append(DanbooruWikiTextNode(text=text[last_end:]))
    return _normalize_line_break_spacing(_coalesce_text_nodes(tuple(parts)))


def _parse_inline_token(token: str) -> tuple[DanbooruWikiInlineNode, ...]:
    """Parse one matched inline token into semantic nodes."""

    quoted_link_match = _QUOTED_LINK_PATTERN.match(token)
    if quoted_link_match is not None:
        href, trailing_text = _normalized_danbooru_href(
            quoted_link_match.group("target")
        )
        nodes: list[DanbooruWikiInlineNode] = [
            DanbooruWikiExternalLinkNode(
                label=quoted_link_match.group("label"),
                href=href,
            )
        ]
        if trailing_text:
            nodes.append(DanbooruWikiTextNode(text=trailing_text))
        return tuple(nodes)
    if token.startswith("[[") and token.endswith("]]"):
        inner = token[2:-2]
        target, separator, label = inner.partition("|")
        wiki_target = target.strip()
        if not separator:
            display_label = wiki_target.replace("_", " ")
        elif label.strip():
            display_label = label.strip()
        else:
            display_label = _default_wiki_label_for_target(wiki_target)
        return (
            DanbooruWikiWikiLinkNode(
                target_title=wiki_target,
                display_label=display_label,
            ),
        )
    if token.startswith("http://") or token.startswith("https://"):
        stripped_url, trailing_text = _split_trailing_url_punctuation(token)
        nodes = [DanbooruWikiExternalLinkNode(label=stripped_url, href=stripped_url)]
        if trailing_text:
            nodes.append(DanbooruWikiTextNode(text=trailing_text))
        return tuple(nodes)
    post_link_match = _POST_LINK_PATTERN.match(token)
    if post_link_match is not None:
        post_id = post_link_match.group("post_id")
        return (
            DanbooruWikiExternalLinkNode(
                label=post_link_match.group("label"),
                href=f"{_DANBOORU_BASE_URL}/posts/{post_id}",
            ),
        )
    if token == "[br]":
        return (DanbooruWikiLineBreakNode(),)
    if token.startswith("{{") and token.endswith("}}"):
        search_tag = token[2:-2].strip()
        return (
            DanbooruWikiSearchLinkNode(
                query_text=search_tag,
                href=f"{_DANBOORU_BASE_URL}/posts?tags={quote(search_tag, safe='')}",
            ),
        )
    if token.startswith("'''") and token.endswith("'''"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-3]),
                bold=True,
            ),
        )
    if token.startswith("''") and token.endswith("''"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[2:-2]),
                italic=True,
            ),
        )
    if token.startswith("`") and token.endswith("`"):
        return (DanbooruWikiCodeNode(text=token[1:-1]),)
    if token.startswith("[b]") and token.endswith("[/b]"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                bold=True,
            ),
        )
    if token.startswith("[i]") and token.endswith("[/i]"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                italic=True,
            ),
        )
    if token.startswith("[u]") and token.endswith("[/u]"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                underline=True,
            ),
        )
    if token.startswith("[code]") and token.endswith("[/code]"):
        return (DanbooruWikiCodeNode(text=token[6:-7]),)
    if token.startswith("<b>") and token.endswith("</b>"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                bold=True,
            ),
        )
    if token.startswith("<i>") and token.endswith("</i>"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                italic=True,
            ),
        )
    if token.startswith("<u>") and token.endswith("</u>"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                underline=True,
            ),
        )
    if token.startswith("<s>") and token.endswith("</s>"):
        return (
            DanbooruWikiStyledTextNode(
                children=_parse_inline_nodes(token[3:-4]),
                strikethrough=True,
            ),
        )
    return (DanbooruWikiTextNode(text=token),)


def _coalesce_text_nodes(
    nodes: tuple[DanbooruWikiInlineNode, ...],
) -> tuple[DanbooruWikiInlineNode, ...]:
    """Merge adjacent plain-text nodes created during token parsing."""

    coalesced: list[DanbooruWikiInlineNode] = []
    for node in nodes:
        if (
            coalesced
            and isinstance(coalesced[-1], DanbooruWikiTextNode)
            and isinstance(node, DanbooruWikiTextNode)
        ):
            previous = coalesced.pop()
            assert isinstance(previous, DanbooruWikiTextNode)
            coalesced.append(DanbooruWikiTextNode(text=previous.text + node.text))
            continue
        coalesced.append(node)
    return tuple(coalesced)


def _normalize_line_break_spacing(
    nodes: tuple[DanbooruWikiInlineNode, ...],
) -> tuple[DanbooruWikiInlineNode, ...]:
    """Trim adjacent plain-text whitespace around semantic line-break nodes."""

    normalized: list[DanbooruWikiInlineNode] = []
    for index, node in enumerate(nodes):
        if isinstance(node, DanbooruWikiTextNode):
            text = node.text
            if index + 1 < len(nodes) and isinstance(
                nodes[index + 1], DanbooruWikiLineBreakNode
            ):
                text = text.rstrip()
            if normalized and isinstance(normalized[-1], DanbooruWikiLineBreakNode):
                text = text.lstrip()
            if text:
                normalized.append(DanbooruWikiTextNode(text=text))
            continue
        normalized.append(node)
    return tuple(normalized)


def _split_trailing_url_punctuation(token: str) -> tuple[str, str]:
    """Separate one URL token from any trailing punctuation not in the target."""

    stripped_url = token.rstrip(_TRAILING_URL_PUNCTUATION)
    trailing_text = token[len(stripped_url) :]
    return stripped_url, trailing_text


def _normalized_danbooru_href(target: str) -> tuple[str, str]:
    """Resolve one DText link target into an href plus any trailing punctuation."""

    normalized_target, trailing_text = _split_trailing_url_punctuation(target)
    if normalized_target.startswith("#"):
        return f"{_FRAGMENT_SCHEME_PREFIX}{normalized_target[1:]}", trailing_text
    if normalized_target.startswith("/"):
        return f"{_DANBOORU_BASE_URL}{normalized_target}", trailing_text
    return normalized_target, trailing_text


def _is_expand_macro_line(line: str) -> bool:
    """Return whether one DText line is an expandable macro wrapper line."""

    normalized_line = line.strip().lower()
    return normalized_line.startswith("[expand=") or normalized_line == "[/expand]"


def _normalized_paragraph_line(line: str) -> str:
    """Normalize one paragraph line that uses wrapper-only DText brackets."""

    stripped = line.strip()
    if (
        stripped.startswith("[")
        and stripped.endswith("]")
        and not stripped.startswith("[expand=")
        and stripped != "[/expand]"
        and not stripped.startswith("[[")
    ):
        inner = stripped[1:-1].strip()
        if inner:
            return inner
    return stripped


def _skip_blank_lines(lines: list[str], *, start_index: int) -> int:
    """Return the next index at or after ``start_index`` that is not blank."""

    index = start_index
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _default_wiki_label_for_target(wiki_target: str) -> str:
    """Return Danbooru's dequalified display label for one wiki target."""

    return _WIKI_QUALIFIER_PATTERN.sub("", wiki_target.replace("_", " ")).strip()


def _list_depth(marker: str, *, ordered: bool) -> int:
    """Return the semantic nesting depth for one matched DText list marker."""

    if ordered and marker.endswith("."):
        return 1
    return max(1, len(marker))


__all__ = ["DanbooruWikiBlockParser"]
