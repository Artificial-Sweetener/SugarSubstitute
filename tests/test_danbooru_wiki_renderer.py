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

"""Unit tests for the Danbooru wiki rich-text renderer."""

from __future__ import annotations

from substitute.application.danbooru import DanbooruWikiPageView
from substitute.presentation.danbooru import DanbooruWikiRichTextRenderer


def test_danbooru_wiki_renderer_supports_core_dtext_subset() -> None:
    """Renderer should cover headings, lists, links, emphasis, and inline code."""

    renderer = DanbooruWikiRichTextRenderer()
    page = DanbooruWikiPageView(
        title="long_hair",
        display_title="long hair",
        category_name="general",
        post_count=100,
        other_names=(),
        body_dtext=(
            "h4. Definition\n\n"
            "Hair that extends below the shoulders. See [[short_hair]] or "
            "https://example.com/reference.\n\n"
            "* ''examples''\n"
            "* '''gallery'''\n"
            "* `tag_token`\n"
        ),
        canonical_url="https://danbooru.donmai.us/wiki_pages/long_hair",
        exists=True,
    )

    result = renderer.render(page)

    assert "<h4>Definition</h4>" in result.html
    assert 'href="danbooru-wiki:short_hair"' in result.html
    assert 'href="https://example.com/reference"' in result.html
    assert "<em>examples</em>" in result.html
    assert "<strong>gallery</strong>" in result.html
    assert "<code>tag_token</code>" in result.html
    assert "<ul>" in result.html
