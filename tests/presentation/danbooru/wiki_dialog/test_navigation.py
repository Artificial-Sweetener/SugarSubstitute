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

"""Test internal and external Danbooru wiki dialog navigation."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QLabel

from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    chipify_target,
    dialog_contains_text,
    first_inline_flow_with_text,
    page_view,
    record_opened_url,
    success_result,
)


def test_internal_wiki_link_navigates_inside_modal(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Navigate an internal wiki link without leaving the dialog."""

    service = StubDanbooruWikiService(
        selection_results={"long hair": success_result(page_view())},
        title_results={
            "short_hair": success_result(
                page_view(
                    title="short_hair",
                    display_title="short hair",
                    body_dtext="h4. Definition\n\nHair above the shoulders.",
                )
            )
        },
    )
    dialog = danbooru_dialog_owner.build(
        wiki_service=service,
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    dialog._handle_anchor_clicked(QUrl("danbooru-wiki:short_hair"))

    assert dialog._title_label.text() == '"short hair"'
    assert dialog_contains_text(dialog, "Hair above the shoulders.")
    assert dialog._back_button.isEnabled() is True
    assert service.calls == [("selection", "long hair"), ("title", "short_hair")]


def test_tag_chip_navigates_inside_modal(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Navigate a resolved tag chip through the dialog's internal route."""

    service = StubDanbooruWikiService(
        selection_results={
            "long hair": success_result(
                page_view(body_dtext="h4. See also\n\n* [[short_hair]]")
            )
        },
        title_results={
            "short_hair": success_result(
                page_view(
                    title="short_hair",
                    display_title="short hair",
                    body_dtext="h4. Definition\n\nHair above the shoulders.",
                )
            )
        },
        section_resolver=lambda sections: chipify_target(
            sections,
            target_title="short_hair",
            display_label="short hair",
            category_name="general",
        ),
    )
    dialog = danbooru_dialog_owner.build(
        wiki_service=service,
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    first_inline_flow_with_text(dialog, "short hair").linkActivated.emit(
        "danbooru-wiki:short_hair"
    )

    assert dialog._title_label.text() == '"short hair"'
    assert dialog_contains_text(dialog, "Hair above the shoulders.")


def test_external_link_delegates_to_url_opener(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Delegate an absolute external link to the supplied URL opener."""

    opened_urls: list[str] = []
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={"long hair": success_result(page_view())}
        ),
        selection_text="long hair",
        open_url=lambda url: record_opened_url(opened_urls, url),
        lookup_dispatcher=ImmediateDispatcher(),
    )

    dialog._handle_anchor_clicked(QUrl("https://example.com/wiki"))

    assert opened_urls == ["https://example.com/wiki"]


def test_pixiv_post_alias_delegates_to_url_opener(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render and open a Pixiv artwork alias from the metadata row."""

    opened_urls: list[str] = []
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "artist name": success_result(
                    page_view(
                        title="artist_name",
                        display_title="artist name",
                        body_dtext="h4. Definition\n\nArtist page.",
                        other_names=("pixiv #12345678",),
                    )
                )
            }
        ),
        selection_text="artist name",
        open_url=lambda url: record_opened_url(opened_urls, url),
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert dialog._pixiv_prefix_label.text() == "On Pixiv:"
    assert dialog._pixiv_label.text() == (
        '<a href="https://www.pixiv.net/artworks/12345678">pixiv #12345678</a>'
    )
    dialog._pixiv_label.linkActivated.emit("https://www.pixiv.net/artworks/12345678")

    assert opened_urls == ["https://www.pixiv.net/artworks/12345678"]


def test_plain_alias_delegates_to_pixiv_tag_search(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render plain aliases as encoded Pixiv tag-search links."""

    first_url = (
        "https://www.pixiv.net/en/tags/"
        "%E3%82%B3%E3%83%B3%E3%83%88%E3%83%A9%E3%83%9D%E3%82%B9%E3%83%88/artworks"
    )
    second_url = (
        "https://www.pixiv.net/en/tags/%E9%80%8F%E8%A6%96%E7%B5%B6%E5%A3%81/artworks"
    )
    opened_urls: list[str] = []
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "contrapposto": success_result(
                    page_view(
                        title="contrapposto",
                        display_title="contrapposto",
                        body_dtext="h4. Definition\n\nBody pose.",
                        other_names=("コントラポスト", "透視絶壁"),
                    )
                )
            }
        ),
        selection_text="contrapposto",
        open_url=lambda url: record_opened_url(opened_urls, url),
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert dialog._pixiv_prefix_label.text() == "On Pixiv:"
    assert dialog._pixiv_label.text() == (
        f'<a href="{first_url}">コントラポスト</a>, <a href="{second_url}">透視絶壁</a>'
    )
    dialog._pixiv_label.linkActivated.emit(first_url)

    assert opened_urls == [first_url]


def test_relative_pool_link_opens_as_absolute_url(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Resolve a quoted relative Danbooru pool link before opening it."""

    pool_url = "https://danbooru.donmai.us/pools/4339"
    opened_urls: list[str] = []
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "serious": success_result(
                    page_view(
                        title="serious",
                        display_title="serious",
                        body_dtext='h4. See also\n\n"Pool: Serious Beauty":/pools/4339',
                    )
                )
            }
        ),
        selection_text="serious",
        open_url=lambda url: record_opened_url(opened_urls, url),
        lookup_dispatcher=ImmediateDispatcher(),
    )

    pool_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if f'href="{pool_url}"' in label.text()
    )
    pool_label.linkActivated.emit(pool_url)

    assert opened_urls == [pool_url]


def test_fragment_link_routes_to_content_anchor(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route a quoted fragment link to the content view's anchor owner."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "tag group:sleeves": success_result(
                    page_view(
                        title="tag_group:sleeves",
                        display_title="tag group:sleeves",
                        body_dtext=(
                            "[expand=Table of Contents]\n"
                            '* 1. "Colors":#dtext-colors\n'
                            "[/expand]\n\n"
                            "h4#padding. Padding\n"
                            + "\n".join("* [[Black sleeves]]" for _ in range(25))
                            + "\n\nh4#colors. Colors\n* [[White sleeves]]\n"
                        ),
                    )
                )
            }
        ),
        selection_text="tag group:sleeves",
        lookup_dispatcher=ImmediateDispatcher(),
    )
    scrolled_to: list[str] = []
    monkeypatch.setattr(
        dialog._content_view,
        "scroll_to_anchor",
        lambda anchor_id: scrolled_to.append(anchor_id),
    )

    dialog._handle_anchor_clicked(QUrl("danbooru-fragment:dtext-colors"))

    assert scrolled_to == ["dtext-colors"]
