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

"""Test Danbooru image-embed promotion and gallery layout."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from substitute.application.danbooru import (
    DanbooruImagePreviewState,
    DanbooruWikiImagePreview,
)
from substitute.presentation.danbooru import DanbooruWikiImageCard
from substitute.presentation.dialogs.danbooru_wiki_dialog import DanbooruWikiDialog
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
    StubImagePreviewResolver,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    dialog_contains_text,
    dialog_texts,
    page_view,
    success_result,
    write_image,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_bulleted_post_embed_promotes_to_image(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Promote a bulleted post embed without leaking literal DText."""

    dialog = _build_dialog(
        danbooru_dialog_owner,
        selection_text="long hair",
        body_dtext="h4. Examples\n\n* !post #12345: [[Hime cut]]",
        previews={
            ("post", 12345): _hidden_preview(
                source_id=12345,
                canonical_url="https://danbooru.donmai.us/posts/12345",
                rating="q",
            )
        },
    )

    assert dialog_contains_text(dialog, "Hime cut")
    assert len(dialog.findChildren(DanbooruWikiImageCard)) == 1
    assert not any("!post" in text for text in dialog_texts(dialog))


def test_bulleted_asset_embed_promotes_to_image(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Promote a bulleted media-asset embed without leaking literal DText."""

    dialog = _build_dialog(
        danbooru_dialog_owner,
        selection_text="shaft look",
        title="shaft_look",
        display_title="shaft look",
        body_dtext="h4. Examples\n\n* !asset #37448022",
        previews={
            ("asset", 37448022): _hidden_preview(
                source_id=37448022,
                canonical_url=("https://danbooru.donmai.us/media_assets/37448022"),
                rating=None,
            )
        },
    )

    assert len(dialog.findChildren(DanbooruWikiImageCard)) == 1
    assert not any("!asset" in text for text in dialog_texts(dialog))


def test_consecutive_examples_share_thumbnail_row(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render consecutive example embeds as sibling tiles rather than stacked cards."""

    dialog = _build_dialog(
        danbooru_dialog_owner,
        selection_text="long hair",
        body_dtext=(
            "h4. Examples\n\n"
            "* !post #11111: [[First style]]\n"
            "* !post #22222: [[Second style]]\n"
        ),
        previews={
            ("post", post_id): _hidden_preview(
                source_id=post_id,
                canonical_url=f"https://danbooru.donmai.us/posts/{post_id}",
                rating="q",
            )
            for post_id in (11111, 22222)
        },
    )
    dialog.show()

    def cards_share_row() -> bool:
        """Return whether both image cards occupy one gallery row."""

        image_cards = dialog.findChildren(DanbooruWikiImageCard)
        return len(image_cards) == 2 and image_cards[0].y() == image_cards[1].y()

    wait_for_qt_condition(cards_share_row)


def test_thumbnail_and_caption_center_within_gallery_cell(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    tmp_path: Path,
) -> None:
    """Center a visible thumbnail and its caption within the gallery cell."""

    image_path = tmp_path / "narrow_preview.png"
    write_image(image_path, width=120, height=156)
    dialog = _build_dialog(
        danbooru_dialog_owner,
        selection_text="bangs",
        title="bangs",
        display_title="bangs",
        body_dtext=(
            "h4. Types of bangs\n\n"
            "* !post #12345: [[arched bangs]] - For bangs that curve upward"
        ),
        previews={
            ("post", 12345): DanbooruWikiImagePreview(
                post_id=12345,
                canonical_post_url="https://danbooru.donmai.us/posts/12345",
                state=DanbooruImagePreviewState.READY,
                local_path=image_path,
                rating="g",
                width=120,
                height=156,
            )
        },
    )
    dialog.show()
    wait_for_qt_condition(lambda: dialog.findChild(DanbooruWikiImageCard) is not None)

    card = dialog.findChild(DanbooruWikiImageCard)
    assert card is not None
    item_layout = card.parentWidget().layout()
    assert item_layout is not None
    assert item_layout.itemAt(0).alignment() & Qt.AlignmentFlag.AlignHCenter
    assert item_layout.itemAt(1).alignment() & Qt.AlignmentFlag.AlignHCenter


def _build_dialog(
    owner: DanbooruWikiDialogOwner,
    *,
    selection_text: str,
    body_dtext: str,
    previews: dict[tuple[str, int], DanbooruWikiImagePreview],
    title: str = "long_hair",
    display_title: str = "long hair",
) -> DanbooruWikiDialog:
    """Build one loaded dialog with deterministic image previews."""

    return owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                selection_text: success_result(
                    page_view(
                        title=title,
                        display_title=display_title,
                        body_dtext=body_dtext,
                    )
                )
            }
        ),
        image_preview_service=StubImagePreviewResolver(previews),
        selection_text=selection_text,
        lookup_dispatcher=ImmediateDispatcher(),
    )


def _hidden_preview(
    *,
    source_id: int,
    canonical_url: str,
    rating: str | None,
) -> DanbooruWikiImagePreview:
    """Build one content-policy-hidden image preview."""

    return DanbooruWikiImagePreview(
        post_id=source_id,
        canonical_post_url=canonical_url,
        state=DanbooruImagePreviewState.HIDDEN,
        local_path=None,
        rating=rating,
        width=None,
        height=None,
        hidden_reason="Hidden by Danbooru content settings.",
    )
