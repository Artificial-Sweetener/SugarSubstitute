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

"""Test Danbooru wiki chip context-menu routing."""

from __future__ import annotations

import pytest

from substitute.application.danbooru import (
    DanbooruWikiTagChipNode,
    DanbooruWikiTextNode,
    DanbooruWikiWikiLinkNode,
)
from tests.presentation.danbooru.wiki_inline_flow.support import (
    InlineFlowOwner,
    install_recording_clipboard,
    install_recording_menu_renderer,
    send_context_menu_event,
)


def test_chip_menu_offers_copy_and_browser_actions(
    inline_flow_owner: InlineFlowOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offer the complete chip-local action set on right-click."""

    menus = install_recording_menu_renderer(monkeypatch)
    view = inline_flow_owner.build(
        inline_nodes=(_tag_chip(),),
        open_url=lambda _url: True,
    )

    send_context_menu_event(widget=view, token_text="short hair")

    assert len(menus) == 1
    assert [action.text() for action in menus[0].actions] == [
        "Copy tag",
        "Open in browser",
    ]
    assert menus[0].exec_positions


def test_copy_tag_uses_semantic_target_not_visible_label(
    inline_flow_owner: InlineFlowOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize the semantic tag target when copying a chip."""

    menus = install_recording_menu_renderer(monkeypatch)
    clipboard = install_recording_clipboard(monkeypatch)
    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiTagChipNode(
                tag_name="short_hair",
                display_label="Short Hair",
                category_name="general",
            ),
        ),
        open_url=lambda _url: True,
    )

    send_context_menu_event(widget=view, token_text="Short Hair")
    menus[0].actions[0].trigger()

    assert clipboard.text == "short hair"


def test_open_in_browser_uses_tag_wiki_page_target(
    inline_flow_owner: InlineFlowOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route the browser action to the external Danbooru wiki page."""

    menus = install_recording_menu_renderer(monkeypatch)
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record external browser opens without launching anything."""

        opened_urls.append(url)
        return True

    view = inline_flow_owner.build(
        inline_nodes=(_tag_chip(),),
        open_url=open_url,
    )

    send_context_menu_event(widget=view, token_text="short hair")
    menus[0].actions[1].trigger()

    assert opened_urls == ["https://danbooru.donmai.us/wiki_pages/short_hair"]


def test_plain_text_shows_no_chip_menu(
    inline_flow_owner: InlineFlowOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave plain prose outside the chip-specific menu path."""

    menus = install_recording_menu_renderer(monkeypatch)
    view = inline_flow_owner.build(
        inline_nodes=(DanbooruWikiTextNode(text="Just plain text"),),
        open_url=lambda _url: True,
    )

    send_context_menu_event(widget=view, token_text="Just")

    assert menus == []


def test_non_chip_wiki_link_shows_no_chip_menu(
    inline_flow_owner: InlineFlowOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep ordinary wiki links outside the chip context-menu path."""

    menus = install_recording_menu_renderer(monkeypatch)
    view = inline_flow_owner.build(
        inline_nodes=(
            DanbooruWikiWikiLinkNode(
                target_title="help:users",
                display_label="help:users",
            ),
        ),
        open_url=lambda _url: True,
    )

    send_context_menu_event(widget=view, token_text="help:users")

    assert menus == []


def test_caption_chip_matches_body_chip_behavior(
    inline_flow_owner: InlineFlowOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose the same menu actions from compact caption chips."""

    menus = install_recording_menu_renderer(monkeypatch)
    view = inline_flow_owner.build(
        inline_nodes=(_tag_chip(),),
        compact=True,
        open_url=lambda _url: True,
    )

    send_context_menu_event(widget=view, token_text="short hair")

    assert len(menus) == 1
    assert [action.text() for action in menus[0].actions] == [
        "Copy tag",
        "Open in browser",
    ]


def _tag_chip() -> DanbooruWikiTagChipNode:
    """Build one representative general-category tag chip."""

    return DanbooruWikiTagChipNode(
        tag_name="short_hair",
        display_label="short hair",
        category_name="general",
    )
