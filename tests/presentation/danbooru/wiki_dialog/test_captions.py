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

"""Test semantic link and line-break rendering in image captions."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from substitute.application.danbooru import (
    DanbooruImagePreviewState,
    DanbooruWikiImagePreview,
)
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
    StubImagePreviewResolver,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    chipify_target,
    dialog_contains_text,
    first_inline_flow_with_text,
    page_view,
    record_opened_url,
    success_result,
)


def test_caption_wiki_link_navigates_inside_dialog(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Route image-caption wiki links through in-dialog navigation."""

    service = StubDanbooruWikiService(
        selection_results={
            "long hair": success_result(
                page_view(
                    body_dtext="h4. Examples\n\n* !post #12345: [[short_hair|short]]"
                )
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
    )
    dialog = danbooru_dialog_owner.build(
        wiki_service=service,
        image_preview_service=_preview_resolver(),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    caption_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if 'href="danbooru-wiki:short_hair"' in label.text()
    )
    caption_label.linkActivated.emit("danbooru-wiki:short_hair")

    assert dialog._title_label.text() == '"short hair"'
    assert dialog_contains_text(dialog, "Hair above the shoulders.")


def test_caption_valid_tag_renders_as_chip(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render a resolved caption tag through the native inline-flow chip path."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "long hair": success_result(
                    page_view(
                        body_dtext=(
                            "h4. Examples\n\n* !post #12345: [[short_hair|short]]"
                        )
                    )
                )
            },
            section_resolver=lambda sections: chipify_target(
                sections,
                target_title="short_hair",
                display_label="short",
                category_name="general",
            ),
        ),
        image_preview_service=_preview_resolver(),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    inline_flow = first_inline_flow_with_text(dialog, "short")
    assert "danbooru-wiki:short_hair" in inline_flow.link_targets()


def test_caption_external_link_routes_to_browser(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Route an image-caption external link through the supplied URL opener."""

    opened_urls: list[str] = []
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "contrapposto": success_result(
                    page_view(
                        title="contrapposto",
                        display_title="contrapposto",
                        body_dtext=(
                            "h4. Examples\n\n"
                            '* !post #12345: "Wikipedia: Contrapposto":http://en.wikipedia.org/wiki/Contrapposto'
                        ),
                    )
                )
            }
        ),
        image_preview_service=_preview_resolver(),
        selection_text="contrapposto",
        open_url=lambda url: record_opened_url(opened_urls, url),
        lookup_dispatcher=ImmediateDispatcher(),
    )

    caption_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if 'href="http://en.wikipedia.org/wiki/Contrapposto"' in label.text()
    )
    caption_label.linkActivated.emit("http://en.wikipedia.org/wiki/Contrapposto")

    assert opened_urls == ["http://en.wikipedia.org/wiki/Contrapposto"]


def test_caption_breaks_and_post_links_render_semantically(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Render caption `[br]` tokens as breaks and post references as links."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "compression artifacts": success_result(
                    page_view(
                        title="compression_artifacts",
                        display_title="compression artifacts",
                        body_dtext=(
                            "h4. Examples\n\n"
                            "* !post #12345: Left: No artifacts [br] Right: artifacts [br] (post #10154238)"
                        ),
                    )
                )
            }
        ),
        image_preview_service=_preview_resolver(),
        selection_text="compression artifacts",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    caption_label = next(
        label
        for label in dialog.findChildren(QLabel)
        if "Left: No artifacts" in label.text()
    )
    assert "<br/>" in caption_label.text()
    assert "[br]" not in caption_label.text()
    assert 'href="https://danbooru.donmai.us/posts/10154238"' in caption_label.text()


def _preview_resolver() -> StubImagePreviewResolver:
    """Build a resolver with one policy-hidden captioned post preview."""

    return StubImagePreviewResolver(
        {
            ("post", 12345): DanbooruWikiImagePreview(
                post_id=12345,
                canonical_post_url="https://danbooru.donmai.us/posts/12345",
                state=DanbooruImagePreviewState.HIDDEN,
                local_path=None,
                rating="q",
                width=None,
                height=None,
                hidden_reason="Hidden by Danbooru content settings.",
            )
        }
    )
