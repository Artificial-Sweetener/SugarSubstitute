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

"""Test rich Danbooru wiki body and status rendering."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from substitute.application.danbooru import (
    DanbooruFailureReason,
    DanbooruWikiContentLookupResult,
)
from substitute.presentation.danbooru import DanbooruWikiInlineFlow
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    chipify_target,
    dialog_contains_text,
    dialog_texts,
    first_inline_flow_with_text,
    page_view,
    record_opened_url,
    success_result,
)


def test_valid_tag_renders_as_native_chip_flow(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render a resolved valid tag through the native inline-flow chip path."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "long hair": success_result(
                    page_view(body_dtext="h4. See also\n\n* [[short_hair]]")
                )
            },
            section_resolver=lambda sections: chipify_target(
                sections,
                target_title="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    inline_flow = first_inline_flow_with_text(dialog, "short hair")
    assert "danbooru-wiki:short_hair" in inline_flow.link_targets()


def test_mixed_prose_and_chip_use_native_inline_flow(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Keep mixed prose and resolved chips on the native inline-flow path."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "serious": success_result(
                    page_view(title="serious", display_title="serious")
                )
            },
            section_resolver=lambda sections: chipify_target(
                sections,
                target_title="short_hair",
                display_label="short hair",
                category_name="general",
            ),
        ),
        selection_text="serious",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert any(
        "See short hair." in view.plain_text()
        for view in dialog.findChildren(DanbooruWikiInlineFlow)
    )
    assert not any(
        'href="danbooru-wiki:short_hair" style="background-color:' in label.text()
        for label in dialog.findChildren(QLabel)
    )


def test_double_brace_search_tag_renders_as_link(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render a double-brace token as a clickable Danbooru post-search link."""

    search_url = "https://danbooru.donmai.us/posts?tags=mpixels%3A%3C%3D0.25"
    opened_urls: list[str] = []
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "lowres": success_result(
                    page_view(
                        title="lowres",
                        display_title="lowres",
                        body_dtext=(
                            "An image less than 500 pixels wide or tall. "
                            "Approximately equivalent to {{mpixels:<=0.25}}."
                        ),
                    )
                )
            }
        ),
        selection_text="lowres",
        open_url=lambda url: record_opened_url(opened_urls, url),
        lookup_dispatcher=ImmediateDispatcher(),
    )

    search_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if f'href="{search_url}"' in label.text()
    )
    assert "{{mpixels:<=0.25}}" not in search_label.text()
    search_label.linkActivated.emit(search_url)

    assert opened_urls == [search_url]


def test_not_found_lookup_renders_status_state(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render the native not-found state when no wiki page exists."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "missing tag": DanbooruWikiContentLookupResult(
                    page=None,
                    navigation_entry=None,
                    requested_text="missing tag",
                    resolved_title="missing_tag",
                    failure_reason=DanbooruFailureReason.NOT_FOUND,
                )
            }
        ),
        selection_text="missing tag",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert dialog._status_title_label.text() == "Definition not found"
    assert dialog._title_label.text() == '"missing tag"'
    assert dialog._status_body_label.text() == (
        'No Danbooru wiki page was found for "missing tag".'
    )


def test_expand_toc_renders_without_raw_dtext(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render expand wrappers and fragments without leaking their raw DText."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "tag group:sleeves": success_result(
                    page_view(
                        title="tag_group:sleeves",
                        display_title="tag group:sleeves",
                        body_dtext=(
                            "[See [[tag groups]].]\n\n"
                            "[expand=Table of Contents]\n"
                            '* 1. "Colors":#dtext-colors\n'
                            "[/expand]\n\n"
                            "h4#colors. Colors\n"
                            "* [[Black sleeves]]\n"
                        ),
                    )
                )
            }
        ),
        selection_text="tag group:sleeves",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert any("See " in text and "tag groups" in text for text in dialog_texts(dialog))
    assert not dialog_contains_text(dialog, "[expand=Table of Contents]")
    assert not dialog_contains_text(dialog, '"Colors":#dtext-colors')
    assert any(
        'href="danbooru-fragment:dtext-colors"' in label.text()
        for label in dialog.findChildren(QLabel)
    )
