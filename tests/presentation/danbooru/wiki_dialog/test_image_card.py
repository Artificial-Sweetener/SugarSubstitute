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

"""Test Danbooru wiki image-card sizing and hidden presentation."""

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
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    dialog_contains_text,
    page_view,
    success_result,
    write_image,
)


def test_dialog_renders_hidden_image_placeholder(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render policy-hidden images with native placeholder copy."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "long hair": success_result(
                    page_view(body_dtext="h4. Examples\n\n!post #12345")
                )
            }
        ),
        image_preview_service=StubImagePreviewResolver(
            {("post", 12345): _hidden_preview()}
        ),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    assert dialog_contains_text(dialog, "Hidden by content preferences")
    assert len(dialog.findChildren(DanbooruWikiImageCard)) == 1


def test_visible_preview_preserves_aspect_ratio(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    tmp_path: Path,
) -> None:
    """Bound ready previews by height rather than forcing a square box."""

    image_path = tmp_path / "wide_preview.png"
    write_image(image_path, width=320, height=160)
    card = danbooru_dialog_owner.own_widget(
        DanbooruWikiImageCard(
            preview=DanbooruWikiImagePreview(
                post_id=12345,
                canonical_post_url="https://danbooru.donmai.us/posts/12345",
                state=DanbooruImagePreviewState.READY,
                local_path=image_path,
                rating="g",
                width=320,
                height=160,
            ),
            open_url=lambda _url: True,
        )
    )
    card.ensurePolished()

    assert card.width() == 312
    assert card.height() == 156


def test_hidden_preview_keeps_square_placeholder(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Keep a square footprint for a hidden preview placeholder."""

    card = danbooru_dialog_owner.own_widget(
        DanbooruWikiImageCard(
            preview=_hidden_preview(width=320, height=160),
            open_url=lambda _url: True,
        )
    )
    card.ensurePolished()

    assert card.width() == 156
    assert card.height() == 156


def _hidden_preview(
    *,
    width: int | None = None,
    height: int | None = None,
) -> DanbooruWikiImagePreview:
    """Build one explicit-rating preview hidden by content policy."""

    return DanbooruWikiImagePreview(
        post_id=12345,
        canonical_post_url="https://danbooru.donmai.us/posts/12345",
        state=DanbooruImagePreviewState.HIDDEN,
        local_path=None,
        rating="e",
        width=width,
        height=height,
        hidden_reason="Hidden by Danbooru content settings.",
    )
