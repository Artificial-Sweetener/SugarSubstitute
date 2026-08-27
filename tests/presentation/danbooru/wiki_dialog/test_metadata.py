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

"""Test loaded Danbooru wiki page metadata presentation."""

from __future__ import annotations

from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    dialog_contains_text,
    page_view,
    success_result,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_dialog_renders_page_metadata_and_body(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render canonical title, counts, aliases, body, and enabled actions."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={"long hair": success_result(page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert dialog._title_label.text() == '"long hair"'
    assert dialog._post_count_label.text() == "5,786 posts"
    assert dialog._pixiv_prefix_label.text() == "On Pixiv:"
    assert (
        '<a href="https://www.pixiv.net/en/tags/long%20locks/artworks">long locks</a>, '
        '<a href="https://www.pixiv.net/en/tags/flowing%20hair/artworks">flowing hair</a>'
        == dialog._pixiv_label.text()
    )
    assert dialog_contains_text(dialog, "Hair that extends below the shoulders.")
    assert dialog._open_button.isEnabled() is True
    assert dialog._copy_button.isEnabled() is True


def test_pixiv_metadata_aligns_to_post_count_baseline(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Align Pixiv metadata with the post-count text baseline."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "ribbon": success_result(
                    page_view(
                        title="ribbon",
                        display_title="ribbon",
                        body_dtext="h4. Definition\n\nRibbon page.",
                        other_names=("リボン", "띠본", "丝带"),
                    )
                )
            }
        ),
        selection_text="ribbon",
        lookup_dispatcher=ImmediateDispatcher(),
    )
    dialog.show()

    def baselines_align() -> bool:
        """Return whether both rendered text baselines align within one pixel."""

        post_baseline = int(dialog._post_count_label.y()) + int(
            dialog._post_count_label.fontMetrics().ascent()
        )
        pixiv_baseline = int(dialog._pixiv_prefix_label.y()) + int(
            dialog._pixiv_prefix_label.fontMetrics().ascent()
        )
        return abs(post_baseline - pixiv_baseline) <= 1

    wait_for_qt_condition(baselines_align)
