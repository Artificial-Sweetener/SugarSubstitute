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

"""Render parsed Danbooru wiki sections inside a native scrollable body."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from substitute.application.danbooru.content_models import (
    DanbooruWikiContentPage,
    DanbooruWikiImagePreview,
)
from substitute.application.danbooru.wiki_render_models import (
    DanbooruWikiSectionContent,
)
from substitute.presentation.danbooru.wiki_section_widget import (
    DanbooruWikiSectionWidget,
)


class DanbooruWikiContentView(QScrollArea):
    """Render one Danbooru wiki page as native sections and block widgets."""

    def __init__(
        self,
        *,
        open_url: Callable[[str], bool],
        navigate_to_title: Callable[[str], None],
        navigate_to_fragment: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        """Build the native scrollable content host."""

        super().__init__(parent)
        self._open_url = open_url
        self._navigate_to_title = navigate_to_title
        self._navigate_to_fragment = navigate_to_fragment
        self._section_widgets_by_anchor: dict[str, QWidget] = {}
        self.setObjectName("DanbooruWikiContentView")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setStyleSheet(
            "QScrollArea#DanbooruWikiContentView { background: transparent; border: none; }"
            "QWidget#DanbooruWikiScrollContent { background: transparent; }"
        )
        self.viewport().setAutoFillBackground(False)
        self._content_widget = QWidget(self)
        self._content_widget.setObjectName("DanbooruWikiScrollContent")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 6)
        self._content_layout.setSpacing(16)
        self._content_layout.addStretch(1)
        self.setWidget(self._content_widget)

    def render_page(
        self,
        *,
        page: DanbooruWikiContentPage,
        sections: tuple[DanbooruWikiSectionContent, ...],
        image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview],
    ) -> None:
        """Render one parsed Danbooru wiki page into the scroll body."""

        self._clear_content()
        for section in sections:
            section_widget = DanbooruWikiSectionWidget(
                section=section,
                image_previews_by_post_id=image_previews_by_post_id,
                open_url=self._open_url,
                navigate_to_title=self._navigate_to_title,
                navigate_to_fragment=self._navigate_to_fragment,
                parent=self._content_widget,
            )
            self._content_layout.addWidget(section_widget)
            if section.anchor_id:
                self._section_widgets_by_anchor[section.anchor_id] = section_widget
        self._content_layout.addStretch(1)
        self.verticalScrollBar().setValue(0)

    def scroll_to_anchor(self, anchor_id: str) -> None:
        """Scroll the body to the section that owns one parsed DText anchor id."""

        section_widget = self._section_widgets_by_anchor.get(anchor_id)
        if section_widget is None and anchor_id.startswith("dtext-"):
            section_widget = self._section_widgets_by_anchor.get(
                anchor_id.removeprefix("dtext-")
            )
        if section_widget is None:
            return
        self.verticalScrollBar().setValue(section_widget.y())

    def _clear_content(self) -> None:
        """Delete previously rendered content widgets before the next page render."""

        self._section_widgets_by_anchor.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


__all__ = ["DanbooruWikiContentView"]
