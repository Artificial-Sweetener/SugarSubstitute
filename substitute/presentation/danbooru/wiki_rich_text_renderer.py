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

"""Render a safe native rich-text subset for Danbooru wiki pages."""

from __future__ import annotations

from dataclasses import dataclass
import html
import re
from urllib.parse import quote

from substitute.application.danbooru import DanbooruWikiPageView

_HEADING_PATTERN = re.compile(r"^h(?P<level>[1-6])\.\s+(?P<content>.+)$")
_ORDERED_LIST_PATTERN = re.compile(r"^(?:#|\d+\.)\s+(?P<content>.+)$")
_UNORDERED_LIST_PATTERN = re.compile(r"^(?:\*|-)\s+(?P<content>.+)$")
_INLINE_TOKEN_PATTERN = re.compile(
    r"(\[\[[^\]]+\]\]|https?://[^\s<]+|'''[^']+'''|''[^']+''|`[^`]+`)"
)
_DANBOORU_WIKI_SCHEME = "danbooru-wiki:"
_TRAILING_URL_PUNCTUATION = ".,;:!?)"


@dataclass(frozen=True, slots=True)
class DanbooruWikiRichTextRenderResult:
    """Capture the rendered HTML returned for one Danbooru wiki page."""

    html: str


class DanbooruWikiRichTextRenderer:
    """Render Danbooru DText into the app-supported rich-text subset."""

    def render(
        self,
        page_view: DanbooruWikiPageView,
    ) -> DanbooruWikiRichTextRenderResult:
        """Return HTML for one Danbooru wiki page body."""

        body_html = _render_block_html(page_view.body_dtext)
        html_text = (
            "<html><head><style>"
            "body { font-family: 'Segoe UI'; font-size: 10pt; line-height: 1.45; }"
            "h1,h2,h3,h4,h5,h6 { margin: 16px 0 8px 0; font-weight: 700; }"
            "p { margin: 0 0 10px 0; }"
            "ul,ol { margin: 0 0 10px 20px; }"
            "li { margin: 0 0 4px 0; }"
            "a { text-decoration: none; }"
            "code { font-family: 'Cascadia Mono'; background: rgba(127,127,127,0.12);"
            " padding: 1px 3px; border-radius: 3px; }"
            "blockquote { margin: 0 0 10px 12px; padding-left: 10px;"
            " border-left: 3px solid rgba(127,127,127,0.35); }"
            "</style></head><body>"
            f"{body_html}</body></html>"
        )
        return DanbooruWikiRichTextRenderResult(html=html_text)


def _render_block_html(body_dtext: str) -> str:
    """Render block-level DText constructs into safe HTML."""

    html_parts: list[str] = []
    lines = body_dtext.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        heading_match = _HEADING_PATTERN.match(line)
        if heading_match is not None:
            level = min(6, max(1, int(heading_match.group("level"))))
            html_parts.append(
                f"<h{level}>{_render_inline_html(heading_match.group('content'))}</h{level}>"
            )
            index += 1
            continue

        ordered_match = _ORDERED_LIST_PATTERN.match(line)
        unordered_match = _UNORDERED_LIST_PATTERN.match(line)
        if ordered_match is not None or unordered_match is not None:
            list_tag = "ol" if ordered_match is not None else "ul"
            list_items: list[str] = []
            while index < len(lines):
                current_line = lines[index].strip()
                if not current_line:
                    index += 1
                    break
                item_match = (
                    _ORDERED_LIST_PATTERN.match(current_line)
                    if list_tag == "ol"
                    else _UNORDERED_LIST_PATTERN.match(current_line)
                )
                if item_match is None:
                    break
                list_items.append(
                    f"<li>{_render_inline_html(item_match.group('content'))}</li>"
                )
                index += 1
            html_parts.append(f"<{list_tag}>{''.join(list_items)}</{list_tag}>")
            continue

        paragraph_lines = [line]
        index += 1
        while index < len(lines):
            current_line = lines[index].strip()
            if not current_line:
                index += 1
                break
            if _HEADING_PATTERN.match(current_line) is not None:
                break
            if (
                _ORDERED_LIST_PATTERN.match(current_line) is not None
                or _UNORDERED_LIST_PATTERN.match(current_line) is not None
            ):
                break
            paragraph_lines.append(current_line)
            index += 1
        html_parts.append(f"<p>{_render_inline_html(' '.join(paragraph_lines))}</p>")

    return "".join(html_parts)


def _render_inline_html(text: str) -> str:
    """Render inline DText constructs into safe HTML."""

    parts: list[str] = []
    last_end = 0
    for match in _INLINE_TOKEN_PATTERN.finditer(text):
        parts.append(html.escape(text[last_end : match.start()]))
        parts.append(_render_inline_token(match.group(0)))
        last_end = match.end()
    parts.append(html.escape(text[last_end:]))
    return "".join(parts)


def _render_inline_token(token: str) -> str:
    """Render one matched inline token into HTML."""

    if token.startswith("[[") and token.endswith("]]"):
        inner = token[2:-2]
        target, separator, label = inner.partition("|")
        wiki_target = target.strip()
        display_label = label.strip() if separator else wiki_target.replace("_", " ")
        href = f"{_DANBOORU_WIKI_SCHEME}{quote(wiki_target)}"
        return (
            f'<a href="{html.escape(href, quote=True)}">'
            f"{html.escape(display_label)}</a>"
        )
    if token.startswith("http://") or token.startswith("https://"):
        stripped_url = token.rstrip(_TRAILING_URL_PUNCTUATION)
        trailing_text = token[len(stripped_url) :]
        escaped_url = html.escape(stripped_url, quote=True)
        return (
            f'<a href="{escaped_url}">{html.escape(stripped_url)}</a>'
            f"{html.escape(trailing_text)}"
        )
    if token.startswith("'''") and token.endswith("'''"):
        return f"<strong>{html.escape(token[3:-3])}</strong>"
    if token.startswith("''") and token.endswith("''"):
        return f"<em>{html.escape(token[2:-2])}</em>"
    if token.startswith("`") and token.endswith("`"):
        return f"<code>{html.escape(token[1:-1])}</code>"
    return html.escape(token)


__all__ = [
    "DanbooruWikiRichTextRenderer",
    "DanbooruWikiRichTextRenderResult",
]
