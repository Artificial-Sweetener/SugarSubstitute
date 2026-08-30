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

"""Test Danbooru wiki inline-flow text and chip layout."""

from __future__ import annotations

from substitute.application.danbooru import (
    DanbooruWikiTagChipNode,
    DanbooruWikiTextNode,
)
from tests.presentation.danbooru.wiki_inline_flow.support import InlineFlowOwner


def test_inline_flow_exposes_plain_text_and_chip_targets(
    inline_flow_owner: InlineFlowOwner,
) -> None:
    """Expose semantic text and chip targets for routing."""

    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiTextNode(text="See "),
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="short hair",
                category_name="general",
            ),
            DanbooruWikiTextNode(text="."),
        ),
        width=320,
        height=200,
    )

    assert view.plain_text() == "See short hair."
    assert view.link_targets() == ("danbooru-wiki:short_hair",)


def test_inline_flow_height_grows_when_width_shrinks(
    inline_flow_owner: InlineFlowOwner,
) -> None:
    """Request more height when plain text wraps at a narrow width."""

    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiTextNode(
                text="This sentence is long enough to wrap in a narrow inline flow."
            ),
        )
    )

    assert view.heightForWidth(120) > view.heightForWidth(480)


def test_inline_flow_keeps_mixed_prose_in_natural_order(
    inline_flow_owner: InlineFlowOwner,
) -> None:
    """Preserve normal word spacing and order around chips."""

    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiTextNode(
                text="A character with a serious or solemn demeanor or "
            ),
            DanbooruWikiTagChipNode(
                tag_name="expressionless",
                display_label="expressionless",
                category_name="general",
            ),
            DanbooruWikiTextNode(
                text=", or provided with context such as an impending battle."
            ),
        ),
        width=760,
        height=120,
    )

    layout, _ = view._layout_for_width(760)
    painted_words = [
        token.token.text for token in layout if token.token.kind != "space"
    ]

    assert painted_words == [
        "A",
        "character",
        "with",
        "a",
        "serious",
        "or",
        "solemn",
        "demeanor",
        "or",
        "expressionless",
        ",",
        "or",
        "provided",
        "with",
        "context",
        "such",
        "as",
        "an",
        "impending",
        "battle.",
    ]


def test_inline_flow_aligns_chip_text_to_neighboring_prose_baseline(
    inline_flow_owner: InlineFlowOwner,
) -> None:
    """Anchor chip text to the same baseline as adjacent prose."""

    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiTextNode(text="The term for the mechanical "),
            DanbooruWikiTagChipNode(
                tag_name="prosthetic_limbs",
                display_label="prosthetic limbs",
                category_name="general",
            ),
            DanbooruWikiTextNode(text=" used in "),
        ),
        width=900,
    )

    layout, _ = view._layout_for_width(900)
    prose_token = next(token for token in layout if token.token.text == "mechanical")
    chip_token = next(
        token for token in layout if token.token.text == "prosthetic limbs"
    )
    following_token = next(token for token in layout if token.token.text == "used")

    assert prose_token.rect.y() == chip_token.rect.y()
    assert chip_token.text_rect.y() == prose_token.text_rect.y()
    assert chip_token.text_rect.y() == following_token.text_rect.y()


def test_inline_flow_keeps_consistent_wrapped_line_spacing_with_chip_prose(
    inline_flow_owner: InlineFlowOwner,
) -> None:
    """Keep one line spacing whether a wrapped line contains a chip."""

    layout_width = 160
    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiTextNode(text="Alpha beta gamma "),
            DanbooruWikiTagChipNode(
                tag_name="delta",
                display_label="delta",
                category_name="general",
            ),
            DanbooruWikiTextNode(text=" epsilon zeta eta theta iota kappa lambda."),
        ),
        width=layout_width,
        height=160,
    )

    layout, _ = view._layout_for_width(layout_width)
    line_tops = sorted(
        {round(token.rect.y(), 2) for token in layout if token.token.kind != "space"}
    )

    assert len(line_tops) >= 3
    deltas = [
        round(line_tops[index + 1] - line_tops[index], 2)
        for index in range(len(line_tops) - 1)
    ]
    assert max(deltas) - min(deltas) <= 0.02
