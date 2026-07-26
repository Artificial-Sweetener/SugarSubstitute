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

"""Map prompt-editor widget geometry across presentation coordinate spaces."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRect
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QWidget


class PromptViewportSurface(Protocol):
    """Describe the viewport geometry needed by prompt overlays."""

    def document(self) -> QTextDocument:
        """Return the surface document."""

    def viewport(self) -> QWidget:
        """Return the surface viewport."""


def autocomplete_panel_host(editor: QWidget) -> QWidget:
    """Return the non-clipping host used for prompt overlays."""

    window = editor.window()
    if isinstance(window, QWidget) and window is not editor:
        return window
    parent = editor.parentWidget()
    if parent is not None:
        return parent
    return editor


def map_rect_to_host(
    source_widget: QWidget,
    rect: QRect,
    host: QWidget,
) -> QRect:
    """Map a widget-local rectangle into host coordinates."""

    top_left = host.mapFromGlobal(source_widget.mapToGlobal(rect.topLeft()))
    return QRect(top_left, rect.size())


def map_cursor_rect_to_host(
    viewport: QWidget,
    cursor_rect: QRect,
    host: QWidget,
) -> QRect:
    """Map a viewport-local caret rectangle into host coordinates."""

    return map_rect_to_host(viewport, cursor_rect, host)


def reorder_overlay_content_rect(editor: PromptViewportSurface) -> QRect:
    """Return the viewport-local text area used by reorder chips."""

    document_margin = max(0, int(round(editor.document().documentMargin())))
    return (
        editor.viewport()
        .rect()
        .adjusted(
            document_margin,
            document_margin,
            -document_margin,
            0,
        )
    )
