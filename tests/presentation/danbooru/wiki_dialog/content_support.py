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

"""Build and inspect representative Danbooru wiki dialog content."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QWidget

from substitute.application.danbooru import (
    DanbooruContentFreshnessState,
    DanbooruWikiBlock,
    DanbooruWikiContentLookupResult,
    DanbooruWikiContentPage,
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiInlineNode,
    DanbooruWikiListBlock,
    DanbooruWikiListItem,
    DanbooruWikiNavigationEntry,
    DanbooruWikiParagraphBlock,
    DanbooruWikiQuoteBlock,
    DanbooruWikiSectionContent,
    DanbooruWikiTagChipNode,
    DanbooruWikiWikiLinkNode,
)
from substitute.presentation.danbooru import DanbooruWikiInlineFlow
from substitute.presentation.dialogs.danbooru_wiki_dialog import DanbooruWikiDialog


def success_result(
    page_view: DanbooruWikiContentPage,
) -> DanbooruWikiContentLookupResult:
    """Build one successful dialog lookup result."""

    return DanbooruWikiContentLookupResult(
        page=page_view,
        navigation_entry=DanbooruWikiNavigationEntry(
            title=page_view.title,
            display_title=page_view.display_title,
        ),
        requested_text=page_view.display_title,
        resolved_title=page_view.title,
    )


def page_view(
    *,
    title: str = "long_hair",
    display_title: str = "long hair",
    body_dtext: str = (
        "h4. Definition\n\nHair that extends below the shoulders.\n\n"
        "See [[short_hair]]."
    ),
    other_names: tuple[str, ...] = ("long locks", "flowing hair"),
    category_name: str = "general",
) -> DanbooruWikiContentPage:
    """Build one representative Danbooru wiki content page."""

    return DanbooruWikiContentPage(
        title=title,
        display_title=display_title,
        category_name=category_name,
        post_count=5786,
        other_names=other_names,
        canonical_url=f"https://danbooru.donmai.us/wiki_pages/{title}",
        body_dtext=body_dtext,
        freshness_state=DanbooruContentFreshnessState.FRESH,
    )


def record_opened_url(opened_urls: list[str], url: str) -> bool:
    """Record one externally opened URL and report success."""

    opened_urls.append(url)
    return True


def widget_global_center(widget: QWidget) -> QPoint:
    """Return the global center point for one child widget."""

    return widget.mapToGlobal(widget.rect().center())


def dialog_texts(dialog: DanbooruWikiDialog) -> tuple[str, ...]:
    """Return visible non-empty label and inline-flow texts below a dialog."""

    texts = [
        text for label in dialog.findChildren(QLabel) if (text := label.text().strip())
    ]
    texts.extend(
        text
        for view in dialog.findChildren(DanbooruWikiInlineFlow)
        if (text := view.plain_text().strip())
    )
    return tuple(texts)


def dialog_contains_text(dialog: DanbooruWikiDialog, expected: str) -> bool:
    """Return whether any rendered dialog text contains the expected value."""

    return any(expected in text for text in dialog_texts(dialog))


def first_inline_flow_with_text(
    dialog: DanbooruWikiDialog,
    expected_text: str,
) -> DanbooruWikiInlineFlow:
    """Return the first inline-flow widget containing the expected plain text."""

    return next(
        cast(DanbooruWikiInlineFlow, view)
        for view in dialog.findChildren(DanbooruWikiInlineFlow)
        if expected_text in view.plain_text()
    )


def chipify_target(
    sections: tuple[DanbooruWikiSectionContent, ...],
    *,
    target_title: str,
    display_label: str,
    category_name: str,
) -> tuple[DanbooruWikiSectionContent, ...]:
    """Replace one wiki-link target with a resolved tag-chip node."""

    def transform_nodes(
        nodes: tuple[DanbooruWikiInlineNode, ...],
    ) -> tuple[DanbooruWikiInlineNode, ...]:
        """Replace matching wiki nodes while preserving other inline content."""

        transformed: list[DanbooruWikiInlineNode] = []
        for node in nodes:
            if (
                isinstance(node, DanbooruWikiWikiLinkNode)
                and node.target_title == target_title
            ):
                transformed.append(
                    DanbooruWikiTagChipNode(
                        tag_name=target_title,
                        display_label=display_label,
                        category_name=category_name,
                    )
                )
                continue
            transformed.append(node)
        return tuple(transformed)

    resolved_sections: list[DanbooruWikiSectionContent] = []
    for section in sections:
        resolved_blocks: list[DanbooruWikiBlock] = []
        for block in section.blocks:
            if isinstance(block, DanbooruWikiParagraphBlock):
                resolved_blocks.append(
                    DanbooruWikiParagraphBlock(
                        inline_nodes=transform_nodes(block.inline_nodes)
                    )
                )
                continue
            if isinstance(block, DanbooruWikiQuoteBlock):
                resolved_blocks.append(
                    DanbooruWikiQuoteBlock(
                        inline_nodes=transform_nodes(block.inline_nodes)
                    )
                )
                continue
            if isinstance(block, DanbooruWikiListBlock):
                resolved_blocks.append(
                    DanbooruWikiListBlock(
                        ordered=block.ordered,
                        items=tuple(
                            DanbooruWikiListItem(
                                inline_nodes=transform_nodes(item.inline_nodes),
                                depth=item.depth,
                            )
                            for item in block.items
                        ),
                    )
                )
                continue
            resolved_blocks.append(
                DanbooruWikiImageReferenceBlock(
                    items=tuple(
                        DanbooruWikiImageReference(
                            source_kind=item.source_kind,
                            source_id=item.source_id,
                            caption_text=item.caption_text,
                            caption_nodes=transform_nodes(item.caption_nodes),
                        )
                        for item in block.items
                    )
                )
            )
        resolved_sections.append(
            DanbooruWikiSectionContent(
                heading=section.heading,
                blocks=tuple(resolved_blocks),
            )
        )
    return tuple(resolved_sections)


def write_image(path: Path, *, width: int, height: int) -> None:
    """Write one solid-color PNG for widget-size regression coverage."""

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ff66aa"))
    assert image.save(str(path)) is True


__all__ = [
    "chipify_target",
    "dialog_contains_text",
    "dialog_texts",
    "first_inline_flow_with_text",
    "page_view",
    "record_opened_url",
    "success_result",
    "widget_global_center",
    "write_image",
]
