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

"""Unit tests for Danbooru inline rich-text HTML rendering."""

from __future__ import annotations

from substitute.application.danbooru import (
    DanbooruWikiStyledTextNode,
    DanbooruWikiTextNode,
)
from substitute.presentation.danbooru.wiki_inline_html_renderer import (
    render_inline_nodes_to_html,
)


def test_render_inline_nodes_to_html_supports_html_style_semantic_formatting() -> None:
    """Styled semantic nodes should render to matching rich-text tags."""

    html = render_inline_nodes_to_html(
        (
            DanbooruWikiStyledTextNode(
                children=(DanbooruWikiTextNode(text="bold"),),
                bold=True,
            ),
            DanbooruWikiTextNode(text=" "),
            DanbooruWikiStyledTextNode(
                children=(DanbooruWikiTextNode(text="italic"),),
                italic=True,
            ),
            DanbooruWikiTextNode(text=" "),
            DanbooruWikiStyledTextNode(
                children=(DanbooruWikiTextNode(text="underline"),),
                underline=True,
            ),
            DanbooruWikiTextNode(text=" "),
            DanbooruWikiStyledTextNode(
                children=(DanbooruWikiTextNode(text="strike"),),
                strikethrough=True,
            ),
        )
    )

    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<u>underline</u>" in html
    assert "<s>strike</s>" in html
