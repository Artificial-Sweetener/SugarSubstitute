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

"""Render semantic Danbooru inline nodes back into safe HTML when chips are absent."""

from __future__ import annotations

import html
from urllib.parse import quote

from substitute.application.danbooru import (
    DanbooruWikiCodeNode,
    DanbooruWikiExternalLinkNode,
    DanbooruWikiInlineNode,
    DanbooruWikiLineBreakNode,
    DanbooruWikiSearchLinkNode,
    DanbooruWikiStyledTextNode,
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
)

_DANBOORU_WIKI_SCHEME = "danbooru-wiki:"
_CATEGORY_CHIP_STYLES = {
    "general": ("#ff4f9a", "#55223a"),
    "artist": ("#f5a623", "#4b3a19"),
    "copyright": ("#5aa9ff", "#1f3e59"),
    "character": ("#52d6a1", "#1f4a39"),
    "meta": ("#c78cff", "#4a335f"),
}


def render_inline_nodes_to_html(nodes: tuple[DanbooruWikiInlineNode, ...]) -> str:
    """Return safe Qt rich-text HTML for one semantic inline node sequence."""

    return "".join(_render_inline_node(node) for node in nodes)


def _render_inline_node(node: DanbooruWikiInlineNode) -> str:
    """Return one semantic inline node as Qt rich-text HTML."""

    if isinstance(node, DanbooruWikiTextNode):
        return html.escape(node.text)
    if isinstance(node, DanbooruWikiExternalLinkNode):
        return _anchor_html(label=node.label, href=node.href)
    if isinstance(node, DanbooruWikiWikiLinkNode):
        return _anchor_html(
            label=node.display_label,
            href=f"{_DANBOORU_WIKI_SCHEME}{quote(node.target_title)}",
        )
    if isinstance(node, DanbooruWikiSearchLinkNode):
        return _anchor_html(label=node.query_text, href=node.href)
    if isinstance(node, DanbooruWikiCodeNode):
        return f"<code>{html.escape(node.text)}</code>"
    if isinstance(node, DanbooruWikiLineBreakNode):
        return "<br/>"
    if isinstance(node, DanbooruWikiStyledTextNode):
        content = render_inline_nodes_to_html(node.children)
        if node.bold:
            content = f"<strong>{content}</strong>"
        if node.italic:
            content = f"<em>{content}</em>"
        if node.underline:
            content = f"<u>{content}</u>"
        if node.strikethrough:
            content = f"<s>{content}</s>"
        return content
    return _chip_anchor_html(
        label=node.display_label,
        href=f"{_DANBOORU_WIKI_SCHEME}{quote(node.tag_name)}",
        category_name=node.category_name,
    )


def _anchor_html(*, label: str, href: str) -> str:
    """Return one escaped rich-text anchor."""

    return f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'


def _chip_anchor_html(*, label: str, href: str, category_name: str | None) -> str:
    """Return one chip-styled wiki anchor for prose-safe rich-text rendering."""

    border_color, background_color = _CATEGORY_CHIP_STYLES.get(
        category_name or "",
        ("#ff4f9a", "rgba(255, 79, 154, 0.18)"),
    )
    style = (
        f"background-color:{background_color};"
        f"border:1px solid {border_color};"
        "white-space:nowrap;"
        "text-decoration:none;"
        "color:#f8f8f8;"
    )
    return (
        f'<a href="{html.escape(href, quote=True)}" style="{style}">'
        f"&nbsp;{html.escape(label)}&nbsp;"
        "</a>"
    )


__all__ = ["render_inline_nodes_to_html"]
