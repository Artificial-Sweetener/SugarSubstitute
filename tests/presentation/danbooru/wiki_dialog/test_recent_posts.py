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

"""Test recent-post resolution and gallery presentation in wiki dialogs."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru import (
    DanbooruImagePreviewState,
    DanbooruWikiImagePreview,
)
from substitute.presentation.danbooru import DanbooruWikiImageCard
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
    StubImagePreviewResolver,
    StubRecentPostsResolver,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    dialog_contains_text,
    page_view,
    success_result,
    write_image,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_dialog_appends_recent_posts_section_when_available(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render visible recent post identifiers in a bottom Posts section."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=_wiki_service(),
        image_preview_service=StubImagePreviewResolver(
            {("post", post_id): _preview(post_id) for post_id in (2001, 2002)}
        ),
        recent_posts_service=StubRecentPostsResolver({"head_tilt": (2001, 2002)}),
        selection_text="head tilt",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert dialog_contains_text(dialog, "Posts")
    post_cards = [
        card
        for card in dialog.findChildren(DanbooruWikiImageCard)
        if card._preview.post_id in {2001, 2002}
    ]
    assert {card._preview.post_id for card in post_cards} == {2001, 2002}


def test_recent_posts_use_available_row_width(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    tmp_path: Path,
) -> None:
    """Keep five recent-post tiles on one row when the gallery has room."""

    image_path = tmp_path / "recent_post_preview.png"
    write_image(image_path, width=120, height=156)
    recent_post_ids = (3001, 3002, 3003, 3004, 3005)
    dialog = danbooru_dialog_owner.build(
        wiki_service=_wiki_service(),
        image_preview_service=StubImagePreviewResolver(
            {
                ("post", post_id): _preview(post_id, local_path=image_path)
                for post_id in recent_post_ids
            }
        ),
        recent_posts_service=StubRecentPostsResolver({"head_tilt": recent_post_ids}),
        selection_text="head tilt",
        lookup_dispatcher=ImmediateDispatcher(),
    )
    dialog.show()

    def all_cards_share_row() -> bool:
        """Return whether all recent cards are laid out on one row."""

        post_cards = [
            card
            for card in dialog.findChildren(DanbooruWikiImageCard)
            if card._preview.post_id in set(recent_post_ids)
        ]
        return len(post_cards) == 5 and len({card.y() for card in post_cards}) == 1

    wait_for_qt_condition(all_cards_share_row)


def _wiki_service() -> StubDanbooruWikiService:
    """Build a service with one representative recent-post tag page."""

    return StubDanbooruWikiService(
        selection_results={
            "head tilt": success_result(
                page_view(title="head_tilt", display_title="head tilt")
            )
        }
    )


def _preview(
    post_id: int,
    *,
    local_path: Path | None = None,
) -> DanbooruWikiImagePreview:
    """Build one ready safe-rated recent post preview."""

    return DanbooruWikiImagePreview(
        post_id=post_id,
        canonical_post_url=f"https://danbooru.donmai.us/posts/{post_id}",
        state=DanbooruImagePreviewState.READY,
        local_path=local_path,
        rating="g",
        width=120,
        height=156,
    )
