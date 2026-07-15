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

"""Unit tests for the semantic Danbooru wiki block parser."""

from __future__ import annotations

from substitute.application.danbooru import (
    DanbooruWikiCodeNode,
    DanbooruWikiExternalLinkNode,
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiLineBreakNode,
    DanbooruWikiListItem,
    DanbooruWikiListBlock,
    DanbooruWikiParagraphBlock,
    DanbooruWikiSearchLinkNode,
    DanbooruWikiStyledTextNode,
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
    plain_text_from_inline_nodes,
)
from substitute.presentation.danbooru import DanbooruWikiBlockParser


def test_danbooru_wiki_block_parser_shapes_sections_links_and_images() -> None:
    """The parser should preserve headings, semantic text blocks, and post embeds."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "h4. Definition\n\n"
        "Hair that extends below the shoulders. See [[short_hair]].\n\n"
        "h4. Examples\n\n"
        "* ''example one''\n"
        "* '''example two''\n\n"
        "!post #12345\n"
    )

    assert len(sections) == 2
    assert sections[0].heading == "Definition"
    assert isinstance(sections[0].blocks[0], DanbooruWikiParagraphBlock)
    definition_nodes = sections[0].blocks[0].inline_nodes
    assert plain_text_from_inline_nodes(definition_nodes) == (
        "Hair that extends below the shoulders. See short hair."
    )
    assert any(
        isinstance(node, DanbooruWikiWikiLinkNode) and node.target_title == "short_hair"
        for node in definition_nodes
    )
    assert sections[1].heading == "Examples"
    assert isinstance(sections[1].blocks[0], DanbooruWikiListBlock)
    assert len(sections[1].blocks[0].items) == 2
    assert all(item.depth == 1 for item in sections[1].blocks[0].items)
    assert isinstance(sections[1].blocks[1], DanbooruWikiImageReferenceBlock)
    assert sections[1].blocks[1].items == (
        DanbooruWikiImageReference(source_kind="post", source_id=12345),
    )


def test_danbooru_wiki_block_parser_promotes_bulleted_post_embeds() -> None:
    """Bulleted Danbooru example embeds should become image blocks, not list text."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "h4. Examples\n\n"
        "* !post #7467939: [[Hime cut]]\n"
        "* !post #7352787: [[short hair|short]], [[long hair]]\n"
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiImageReferenceBlock)
    first, second = sections[0].blocks[0].items
    assert first.source_kind == "post"
    assert first.source_id == 7467939
    assert first.caption_text == "Hime cut"
    assert first.caption_nodes == (
        DanbooruWikiWikiLinkNode(
            target_title="Hime cut",
            display_label="Hime cut",
        ),
    )
    assert second.caption_text == "short, long hair"
    assert plain_text_from_inline_nodes(second.caption_nodes) == "short, long hair"


def test_danbooru_wiki_block_parser_supports_quoted_relative_and_external_links() -> (
    None
):
    """Old-style quoted DText links should become semantic external-link nodes."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        'See "Pool: Serious Beauty":/pools/4339 and '
        '"Wikipedia: Contrapposto":http://en.wikipedia.org/wiki/Contrapposto.'
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiParagraphBlock)
    nodes = sections[0].blocks[0].inline_nodes
    assert any(
        isinstance(node, DanbooruWikiExternalLinkNode)
        and node.href == "https://danbooru.donmai.us/pools/4339"
        and node.label == "Pool: Serious Beauty"
        for node in nodes
    )
    assert any(
        isinstance(node, DanbooruWikiExternalLinkNode)
        and node.href == "http://en.wikipedia.org/wiki/Contrapposto"
        and node.label == "Wikipedia: Contrapposto"
        for node in nodes
    )
    assert plain_text_from_inline_nodes(nodes).endswith("Contrapposto.")


def test_danbooru_wiki_block_parser_renders_bbcode_style_inline_tags() -> None:
    """Danbooru BBCode-style inline tags should become semantic styled/code nodes."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "Hair that drapes forward. Known in British English as a "
        "[b]fringe[/b].\n\n"
        "The base [code]bangs[/code] tag is no longer used. "
        "[i]Italic[/i] and [u]underline[/u] should render too.\n\n"
        "h4. [b]Examples[/b]"
    )

    assert len(sections) == 2
    paragraph_one = sections[0].blocks[0]
    paragraph_two = sections[0].blocks[1]
    assert isinstance(paragraph_one, DanbooruWikiParagraphBlock)
    assert isinstance(paragraph_two, DanbooruWikiParagraphBlock)
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.bold
        for node in paragraph_one.inline_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiCodeNode) and node.text == "bangs"
        for node in paragraph_two.inline_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.italic
        for node in paragraph_two.inline_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.underline
        for node in paragraph_two.inline_nodes
    )
    assert sections[1].heading == "Examples"


def test_danbooru_wiki_block_parser_renders_html_style_inline_tags() -> None:
    """HTML-style inline tags should become semantic styled nodes too."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "For bangs with <b>large gaps</b> between them. "
        "<i>Italic</i>, <u>underline</u>, and <s>strike</s> should render.\n"
    )

    assert len(sections) == 1
    paragraph = sections[0].blocks[0]
    assert isinstance(paragraph, DanbooruWikiParagraphBlock)
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.bold
        for node in paragraph.inline_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.italic
        for node in paragraph.inline_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.underline
        for node in paragraph.inline_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiStyledTextNode) and node.strikethrough
        for node in paragraph.inline_nodes
    )


def test_danbooru_wiki_block_parser_renders_double_brace_search_tags() -> None:
    """Danbooru double-brace tokens should become semantic post-search links."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "An image less than 500 pixels wide or tall. "
        "Approximately equivalent to {{mpixels:<=0.25}}."
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiParagraphBlock)
    nodes = sections[0].blocks[0].inline_nodes
    assert any(
        isinstance(node, DanbooruWikiSearchLinkNode)
        and node.query_text == "mpixels:<=0.25"
        and node.href == "https://danbooru.donmai.us/posts?tags=mpixels%3A%3C%3D0.25"
        for node in nodes
    )


def test_danbooru_wiki_block_parser_preserves_quoted_caption_links() -> None:
    """Quoted links inside image captions should remain semantic caption nodes."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        'h4. Examples\n\n* !post #4339: "Pool: Serious Beauty":/pools/4339'
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiImageReferenceBlock)
    [item] = sections[0].blocks[0].items
    assert item.caption_text == "Pool: Serious Beauty"
    assert item.caption_nodes == (
        DanbooruWikiExternalLinkNode(
            label="Pool: Serious Beauty",
            href="https://danbooru.donmai.us/pools/4339",
        ),
    )


def test_danbooru_wiki_block_parser_renders_caption_breaks_and_post_links() -> None:
    """Caption `[br]` tokens and `post #...` references should become semantic nodes."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "h4. Examples\n\n"
        "* !post #12345: Left: No artifacts [br] Right: artifacts [br] (post #10154238)"
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiImageReferenceBlock)
    [item] = sections[0].blocks[0].items
    assert item.caption_text == "Left: No artifacts\nRight: artifacts\n(post #10154238)"
    assert any(
        isinstance(node, DanbooruWikiLineBreakNode) for node in item.caption_nodes
    )
    assert any(
        isinstance(node, DanbooruWikiExternalLinkNode)
        and node.label == "post #10154238"
        and node.href == "https://danbooru.donmai.us/posts/10154238"
        for node in item.caption_nodes
    )


def test_danbooru_wiki_block_parser_promotes_asset_embeds() -> None:
    """Bulleted Danbooru asset embeds should become image blocks, not literal text."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse("h4. Examples\n\n* !asset #37448022")

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiImageReferenceBlock)
    assert sections[0].blocks[0].items == (
        DanbooruWikiImageReference(source_kind="asset", source_id=37448022),
    )


def test_danbooru_wiki_block_parser_accepts_compact_heading_spacing() -> None:
    """Heading syntax should still parse when Danbooru omits the usual space after the dot."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse("h4.Examples\n\n!post #12345\n\nh4.Non-examples")

    assert len(sections) == 2
    assert sections[0].heading == "Examples"
    assert isinstance(sections[0].blocks[0], DanbooruWikiImageReferenceBlock)
    assert sections[1].heading == "Non-examples"
    assert sections[1].blocks == ()


def test_danbooru_wiki_block_parser_accepts_anchored_heading_syntax() -> None:
    """Danbooru anchored headings should parse as section headings, not prose."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse("h4#see-also. See also\n\n* [[silhouette]]")

    assert len(sections) == 1
    assert sections[0].heading == "See also"
    assert sections[0].anchor_id == "see-also"
    assert isinstance(sections[0].blocks[0], DanbooruWikiListBlock)


def test_danbooru_wiki_block_parser_accepts_uppercase_anchored_heading_syntax() -> None:
    """Uppercase Danbooru anchored headings should still parse as headings."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse("H4#styles. Style\n\n* [[Detached sleeves]]")

    assert len(sections) == 1
    assert sections[0].heading == "Style"
    assert sections[0].anchor_id == "styles"
    assert isinstance(sections[0].blocks[0], DanbooruWikiListBlock)


def test_danbooru_wiki_block_parser_renders_empty_pipe_wiki_labels_without_qualifiers() -> (
    None
):
    """Danbooru empty-pipe wiki links should display their dequalified page title."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "h4. Notable characters\n\n"
        "* [[Cyborg (DC)|]] ([[DC Comics]])\n"
        "* [[Raiden (metal gear)|]] ([[Metal Gear (series)|]])\n"
        "* [[Robocop (character)|]] ([[Robocop]])\n"
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiListBlock)
    first_item = sections[0].blocks[0].items[0]
    assert plain_text_from_inline_nodes(first_item.inline_nodes) == "Cyborg (DC Comics)"
    assert any(
        isinstance(node, DanbooruWikiWikiLinkNode) and node.display_label == "Cyborg"
        for node in first_item.inline_nodes
    )


def test_danbooru_wiki_block_parser_renders_expand_toc_fragments_and_wrapped_intro() -> (
    None
):
    """Expand wrappers and local fragment links should become clean semantic content."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "[See [[tag groups]].]\n\n"
        "[expand=Table of Contents]\n"
        '* 1. "Colors":#dtext-colors\n'
        '* 2. "Patterns":#dtext-patterns\n'
        "[/expand]\n\n"
        "h4#colors. Colors\n"
        "* [[Black sleeves]]\n"
        "** [[White sleeves]]\n"
    )

    assert len(sections) == 2
    assert isinstance(sections[0].blocks[0], DanbooruWikiParagraphBlock)
    intro_nodes = sections[0].blocks[0].inline_nodes
    assert plain_text_from_inline_nodes(intro_nodes) == "See tag groups."
    assert isinstance(sections[0].blocks[1], DanbooruWikiListBlock)
    first_item = sections[0].blocks[1].items[0]
    second_item = sections[0].blocks[1].items[1]
    assert first_item == DanbooruWikiListItem(
        inline_nodes=(
            DanbooruWikiTextNode(text="1. "),
            DanbooruWikiExternalLinkNode(
                label="Colors",
                href="danbooru-fragment:dtext-colors",
            ),
        ),
    )
    assert second_item == DanbooruWikiListItem(
        inline_nodes=(
            DanbooruWikiTextNode(text="2. "),
            DanbooruWikiExternalLinkNode(
                label="Patterns",
                href="danbooru-fragment:dtext-patterns",
            ),
        ),
    )
    assert sections[1].heading == "Colors"
    assert sections[1].anchor_id == "colors"
    assert isinstance(sections[1].blocks[0], DanbooruWikiListBlock)
    assert len(sections[1].blocks[0].items) == 2
    assert (
        plain_text_from_inline_nodes(sections[1].blocks[0].items[1].inline_nodes)
        == "White sleeves"
    )
    assert sections[1].blocks[0].items[0].depth == 1
    assert sections[1].blocks[0].items[1].depth == 2


def test_danbooru_wiki_block_parser_keeps_blank_line_list_runs_in_one_block() -> None:
    """Blank lines between same-kind list items should not split the list into blocks."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "h4#colors. Colors\n"
        "* [[See-through sleeves]]\n"
        "* [[Gradient sleeves]]\n"
        "\n"
        "* [[Aqua sleeves]]\n"
        "* [[Black sleeves]]\n"
    )

    assert len(sections) == 1
    assert len(sections[0].blocks) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiListBlock)
    assert len(sections[0].blocks[0].items) == 4
    assert all(item.depth == 1 for item in sections[0].blocks[0].items)


def test_danbooru_wiki_block_parser_preserves_nested_list_depth() -> None:
    """Nested DText list markers should keep their semantic depth."""

    parser = DanbooruWikiBlockParser()

    sections = parser.parse(
        "h4#lengths. Length\n"
        "* [[Short sleeves]]\n"
        "* [[Short over long sleeves]]\n"
        "* [[Three-quarter sleeves]]\n"
        "* [[Long sleeves]]\n"
        "** [[Sleeves past wrists]]\n"
        "** [[Sleeves past fingers]]\n"
        "* [[Uneven sleeves]]\n"
    )

    assert len(sections) == 1
    assert isinstance(sections[0].blocks[0], DanbooruWikiListBlock)
    items = sections[0].blocks[0].items
    assert [plain_text_from_inline_nodes(item.inline_nodes) for item in items] == [
        "Short sleeves",
        "Short over long sleeves",
        "Three-quarter sleeves",
        "Long sleeves",
        "Sleeves past wrists",
        "Sleeves past fingers",
        "Uneven sleeves",
    ]
    assert [item.depth for item in items] == [1, 1, 1, 1, 2, 2, 1]
