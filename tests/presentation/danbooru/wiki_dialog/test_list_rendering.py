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

"""Test Danbooru wiki list layout and native indentation."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from substitute.application.danbooru import DanbooruWikiSectionContent
from substitute.presentation.dialogs.danbooru_wiki_dialog import DanbooruWikiDialog
from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    chipify_target,
    first_inline_flow_with_text,
    page_view,
    success_result,
)


def test_list_uses_compact_native_indentation(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Use the compact native list indent instead of the former wide offset."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "hair styles": success_result(
                    page_view(
                        title="hair_styles",
                        display_title="hair styles",
                        body_dtext=(
                            "h4. See also\n\n"
                            "* [[bangs]]\n"
                            "* [[slicked_back_hair|hair slicked back]]"
                        ),
                    )
                )
            }
        ),
        selection_text="hair styles",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    list_label = next(
        label for label in dialog.findChildren(QLabel) if "<ul>" in label.text()
    )
    assert "ul,ol { margin: 0 0 10px 0; padding-left: 14px; }" in list_label.text()


def test_nested_list_items_indent_beyond_parent_items(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
) -> None:
    """Indent nested DText list items while restoring trailing parent depth."""

    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={
                "tag group:sleeves": success_result(
                    page_view(
                        title="tag_group:sleeves",
                        display_title="Tag group:sleeves",
                        body_dtext=(
                            "h4#lengths. Length\n"
                            "* [[Long sleeves]]\n"
                            "** [[Sleeves past wrists]]\n"
                            "** [[Sleeves past fingers]]\n"
                            "* [[Uneven sleeves]]\n"
                        ),
                    )
                )
            },
            section_resolver=_chipify_sleeve_tags,
        ),
        selection_text="tag group:sleeves",
        lookup_dispatcher=ImmediateDispatcher(),
    )

    parent_indent = _left_margin(dialog, "Long sleeves")
    wrist_indent = _left_margin(dialog, "Sleeves past wrists")
    finger_indent = _left_margin(dialog, "Sleeves past fingers")
    trailing_indent = _left_margin(dialog, "Uneven sleeves")

    assert wrist_indent > parent_indent
    assert finger_indent > parent_indent
    assert trailing_indent == parent_indent


def _chipify_sleeve_tags(
    sections: tuple[DanbooruWikiSectionContent, ...],
) -> tuple[DanbooruWikiSectionContent, ...]:
    """Resolve every list target used by the nested-list contract."""

    resolved = sections
    for title in (
        "Long sleeves",
        "Sleeves past wrists",
        "Sleeves past fingers",
        "Uneven sleeves",
    ):
        resolved = chipify_target(
            resolved,
            target_title=title,
            display_label=title,
            category_name="general",
        )
    return resolved


def _left_margin(dialog: DanbooruWikiDialog, text: str) -> int:
    """Return the left margin of one resolved inline-flow list row."""

    flow = first_inline_flow_with_text(dialog, text)
    row = flow.parentWidget()
    assert row is not None
    layout = row.layout()
    assert layout is not None
    return layout.contentsMargins().left()
