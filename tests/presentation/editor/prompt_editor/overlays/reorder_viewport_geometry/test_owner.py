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

"""Cover bounded reorder viewport geometry identity ownership."""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QScrollBar, QWidget

from substitute.presentation.editor.prompt_editor.overlays.reorder_overlay_ports import (
    PromptReorderEditor,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_viewport_geometry import (
    PromptReorderViewportGeometryOwner,
)


class _Editor:
    """Expose deterministic viewport, document, and scroll geometry."""

    def __init__(self) -> None:
        """Create stable offscreen geometry collaborators with one owner."""

        self._viewport = QWidget()
        self._viewport.setGeometry(0, 0, 320, 180)
        self._document = QTextDocument(self._viewport)
        self._document.setDocumentMargin(4.0)
        self._scrollbar = QScrollBar(self._viewport)
        self._scrollbar.setRange(0, 100)

    def close(self) -> None:
        """Release all test widget collaborators through the viewport owner."""

        self._viewport.close()
        self._viewport.deleteLater()

    def viewport(self) -> QWidget:
        """Return the test viewport."""

        return self._viewport

    def document(self) -> QTextDocument:
        """Return the test text document."""

        return self._document

    def verticalScrollBar(self) -> QScrollBar:
        """Return the test scrollbar."""

        return self._scrollbar


def test_viewport_geometry_owner_publishes_complete_bounded_identity() -> None:
    """Publish viewport, content margin, and scroll in one identity key."""

    _ensure_qapp()
    editor = _Editor()
    try:
        owner = PromptReorderViewportGeometryOwner(cast(PromptReorderEditor, editor))

        initial = owner.position_geometry_key()
        editor.verticalScrollBar().setValue(27)
        scrolled = owner.position_geometry_key()

        assert initial.viewport_width == 320
        assert initial.viewport_height == 180
        assert initial.content_left == 4
        assert initial.content_top == 4
        assert initial.content_width == 312
        assert initial.scroll_offset == 0
        assert scrolled.scroll_offset == 27
        assert scrolled != initial
    finally:
        editor.close()


def test_viewport_geometry_owner_captures_one_coherent_refresh_snapshot() -> None:
    """Use one viewport read for geometry, identity, and published state."""

    _ensure_qapp()
    editor = _Editor()
    try:
        owner = PromptReorderViewportGeometryOwner(cast(PromptReorderEditor, editor))

        snapshot = owner.capture()

        assert snapshot.viewport_rect == editor.viewport().rect()
        assert snapshot.content_rect.left() == snapshot.position_key.content_left
        assert snapshot.content_rect.top() == snapshot.position_key.content_top
        assert snapshot.content_rect.width() == snapshot.position_key.content_width
        assert snapshot.position_key.viewport_width == snapshot.viewport_rect.width()
        assert snapshot.position_key.viewport_height == snapshot.viewport_rect.height()
        assert owner.published_content_rect == snapshot.content_rect
        published = owner.published_content_rect
        published.setLeft(published.left() + 10)
        assert owner.published_content_rect == snapshot.content_rect
    finally:
        editor.close()


def _ensure_qapp() -> QApplication:
    """Return the shared offscreen Qt application."""

    instance = QApplication.instance()
    if instance is not None:
        return cast(QApplication, instance)
    return QApplication([])
