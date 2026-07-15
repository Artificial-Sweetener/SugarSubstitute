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

"""Render one parsed Danbooru wiki section using native stacked widgets."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import unquote

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SubtitleLabel  # type: ignore[import-untyped]

from substitute.application.danbooru.content_models import (
    DanbooruWikiImagePreview,
)
from substitute.application.danbooru.wiki_render_models import (
    DanbooruWikiInlineNode,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiListItem,
    DanbooruWikiListBlock,
    DanbooruWikiParagraphBlock,
    DanbooruWikiQuoteBlock,
    DanbooruWikiSectionContent,
    inline_nodes_contain_tag_chips,
)
from substitute.presentation.danbooru.wiki_image_card import DanbooruWikiImageCard
from substitute.presentation.danbooru.wiki_inline_flow import DanbooruWikiInlineFlow
from substitute.presentation.danbooru.wiki_inline_html_renderer import (
    render_inline_nodes_to_html,
)

_WIKI_SCHEME_PREFIX = "danbooru-wiki:"
_FRAGMENT_SCHEME_PREFIX = "danbooru-fragment:"
_TEXT_BLOCK_HTML_PREFIX = (
    "<html><head><style>"
    "body { font-family: 'Segoe UI'; font-size: 10pt; line-height: 1.45; color: palette(text); }"
    "p { margin: 0 0 10px 0; }"
    "ul,ol { margin: 0 0 10px 0; padding-left: 14px; }"
    "li { margin: 0 0 4px 0; }"
    "blockquote { margin: 0 0 10px 12px; padding-left: 10px; border-left: 3px solid rgba(127,127,127,0.35); }"
    "code { font-family: 'Cascadia Mono'; background: rgba(127,127,127,0.12); padding: 1px 3px; border-radius: 3px; }"
    "a { text-decoration: none; }"
    "</style></head><body>"
)
_TEXT_BLOCK_HTML_SUFFIX = "</body></html>"


class _DanbooruWikiImageGalleryWidget(QWidget):
    """Lay out Danbooru thumbnail items using the actual available width."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create one width-driven gallery grid."""

        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(10)
        self._item_widgets: list[QWidget] = []

    def add_gallery_item(self, item_widget: QWidget) -> None:
        """Append one gallery item and relayout the grid."""

        self._item_widgets.append(item_widget)
        self._relayout_items()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """Reflow the gallery whenever the available width changes."""

        super().resizeEvent(event)
        self._relayout_items()

    def _relayout_items(self) -> None:
        """Pack gallery items into as many columns as the width allows."""

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)
        if not self._item_widgets:
            return
        margins = self._layout.contentsMargins()
        available_width = max(
            1,
            self.width() - margins.left() - margins.right(),
        )
        row = 0
        column = 0
        row_width = 0
        horizontal_spacing = self._layout.horizontalSpacing()
        for item_widget in self._item_widgets:
            item_width = max(1, item_widget.sizeHint().width())
            required_width = (
                item_width
                if column == 0
                else row_width + horizontal_spacing + item_width
            )
            if column > 0 and required_width > available_width:
                row += 1
                column = 0
                row_width = 0
                required_width = item_width
            self._layout.addWidget(
                item_widget,
                row,
                column,
                Qt.AlignmentFlag.AlignTop,
            )
            row_width = required_width
            column += 1


class DanbooruWikiSectionWidget(QWidget):
    """Render one parsed Danbooru wiki section with native block widgets."""

    def __init__(
        self,
        *,
        section: DanbooruWikiSectionContent,
        image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview],
        open_url: Callable[[str], bool],
        navigate_to_title: Callable[[str], None],
        navigate_to_fragment: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        """Build one native wiki section from parsed blocks."""

        super().__init__(parent)
        self._open_url = open_url
        self._navigate_to_title = navigate_to_title
        self._navigate_to_fragment = navigate_to_fragment
        self._build_layout(section, image_previews_by_post_id)

    def _build_layout(
        self,
        section: DanbooruWikiSectionContent,
        image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview],
    ) -> None:
        """Create the section heading and native block widget stack."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        if section.heading:
            heading_label = SubtitleLabel(section.heading, self)
            layout.addWidget(heading_label)
        for block in section.blocks:
            if isinstance(block, DanbooruWikiParagraphBlock):
                layout.addWidget(self._paragraph_block_widget(block))
                continue
            if isinstance(block, DanbooruWikiQuoteBlock):
                layout.addWidget(self._quote_block_widget(block))
                continue
            if isinstance(block, DanbooruWikiListBlock):
                layout.addWidget(self._list_block_widget(block))
                continue
            layout.addWidget(
                self._image_block_widget(
                    block,
                    image_previews_by_post_id=image_previews_by_post_id,
                )
            )

    def _paragraph_block_widget(self, block: DanbooruWikiParagraphBlock) -> QWidget:
        """Create one paragraph widget from semantic inline content."""

        if inline_nodes_contain_tag_chips(block.inline_nodes):
            return self._inline_flow_widget(block.inline_nodes)
        return self._rich_text_label(
            f"<p>{render_inline_nodes_to_html(block.inline_nodes)}</p>"
        )

    def _quote_block_widget(self, block: DanbooruWikiQuoteBlock) -> QWidget:
        """Create one quote block widget from semantic inline content."""

        if not inline_nodes_contain_tag_chips(block.inline_nodes):
            return self._rich_text_label(
                f"<blockquote>{render_inline_nodes_to_html(block.inline_nodes)}</blockquote>"
            )

        quote_widget = QWidget(self)
        layout = QHBoxLayout(quote_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        rule = QFrame(quote_widget)
        rule.setFixedWidth(3)
        rule.setStyleSheet("QFrame { background: rgba(127, 127, 127, 0.35); }")
        layout.addWidget(rule, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._inline_flow_widget(block.inline_nodes), 1)
        return quote_widget

    def _list_block_widget(self, block: DanbooruWikiListBlock) -> QWidget:
        """Create one list widget from semantic inline content items."""

        if not any(
            inline_nodes_contain_tag_chips(item.inline_nodes) for item in block.items
        ) and not any(item.depth > 1 for item in block.items):
            tag = "ol" if block.ordered else "ul"
            list_items = "".join(
                f"<li>{render_inline_nodes_to_html(item.inline_nodes)}</li>"
                for item in block.items
            )
            return self._rich_text_label(f"<{tag}>{list_items}</{tag}>")

        list_widget = QWidget(self)
        layout = QVBoxLayout(list_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for index, item in enumerate(block.items, start=1):
            layout.addWidget(
                self._list_item_widget(
                    marker=f"{index}." if block.ordered and item.depth == 1 else "•",
                    item=item,
                )
            )
        return list_widget

    def _list_item_widget(
        self,
        *,
        marker: str,
        item: DanbooruWikiListItem,
    ) -> QWidget:
        """Create one native list item row with marker plus inline content."""

        item_widget = QWidget(self)
        layout = QHBoxLayout(item_widget)
        indent_pixels = max(0, item.depth - 1) * 18
        layout.setContentsMargins(indent_pixels, 0, 0, 0)
        layout.setSpacing(8)
        marker_label = QLabel(marker, item_widget)
        marker_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        marker_label.setFixedWidth(14)
        layout.addWidget(marker_label, 0, Qt.AlignmentFlag.AlignTop)
        if inline_nodes_contain_tag_chips(item.inline_nodes):
            layout.addWidget(self._inline_flow_widget(item.inline_nodes), 1)
        else:
            layout.addWidget(
                self._rich_text_label(
                    f"<p>{render_inline_nodes_to_html(item.inline_nodes)}</p>"
                ),
                1,
            )
        return item_widget

    def _rich_text_label(self, body_html: str) -> QLabel:
        """Create one rich-text label that uses the existing wiki HTML style path."""

        label = QLabel(self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(f"{_TEXT_BLOCK_HTML_PREFIX}{body_html}{_TEXT_BLOCK_HTML_SUFFIX}")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        label.linkActivated.connect(self._handle_link_activated)
        return label

    def _inline_flow_widget(
        self,
        inline_nodes: tuple[DanbooruWikiInlineNode, ...],
        *,
        compact: bool = False,
    ) -> DanbooruWikiInlineFlow:
        """Create one native inline-flow renderer for chip-capable inline content."""

        view = DanbooruWikiInlineFlow(
            inline_nodes=inline_nodes,
            compact=compact,
            open_url=self._open_url,
            parent=self,
        )
        view.linkActivated.connect(self._handle_link_activated)
        return view

    def _handle_link_activated(self, link: str) -> None:
        """Route internal wiki links locally and external links to the opener."""

        if link.startswith(_WIKI_SCHEME_PREFIX):
            self._navigate_to_title(unquote(link.split(":", 1)[1]))
            return
        if link.startswith(_FRAGMENT_SCHEME_PREFIX):
            self._navigate_to_fragment(unquote(link.split(":", 1)[1]))
            return
        self._open_url(link)

    def _image_block_widget(
        self,
        block: DanbooruWikiImageReferenceBlock,
        *,
        image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview],
    ) -> QWidget:
        """Render one image block as a compact side-by-side thumbnail gallery."""

        gallery = _DanbooruWikiImageGalleryWidget(self)
        for item in block.items:
            preview = image_previews_by_post_id.get((item.source_kind, item.source_id))
            if preview is None:
                continue
            item_widget = QWidget(gallery)
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(6)
            item_layout.addWidget(
                DanbooruWikiImageCard(
                    preview=preview,
                    caption_text=item.caption_text,
                    open_url=self._open_url,
                    parent=item_widget,
                ),
                alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            )
            if item.caption_nodes:
                if inline_nodes_contain_tag_chips(item.caption_nodes):
                    caption_widget = self._inline_flow_widget(
                        item.caption_nodes,
                        compact=True,
                    )
                    caption_widget.setStyleSheet(
                        "DanbooruWikiInlineFlow { color: rgba(235, 235, 235, 0.88); }"
                    )
                    item_layout.addWidget(
                        caption_widget,
                        0,
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    )
                else:
                    caption_label = self._rich_text_label(
                        f"<p>{render_inline_nodes_to_html(item.caption_nodes)}</p>"
                    )
                    caption_label.setStyleSheet(
                        "QLabel { color: rgba(235, 235, 235, 0.88); }"
                    )
                    caption_label.setAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                    )
                    item_layout.addWidget(
                        caption_label,
                        0,
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    )
            else:
                item_layout.addStretch(0)
            gallery.add_gallery_item(item_widget)
        return gallery


__all__ = ["DanbooruWikiSectionWidget"]
