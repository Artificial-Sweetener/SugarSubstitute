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

"""Own the plain source QTextDocument mirror used by projection surfaces."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QFont, QTextCursor, QTextDocument, QTextOption

from .source_change_applier import PromptProjectionSourceDocumentRangeEdit


class PromptProjectionSourceDocument:
    """Own source mirror document mutation behind a narrow Qt adapter."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the source mirror document with editor-compatible defaults."""

        self._document = QTextDocument(parent)
        self._document.setDocumentMargin(4.0)
        self._document.setUndoRedoEnabled(False)
        self._default_font: QFont | None = None

        source_text_option = QTextOption()
        source_text_option.setWrapMode(
            QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        )
        self._document.setDefaultTextOption(source_text_option)

    def document(self) -> QTextDocument:
        """Return the live Qt document exposed for host compatibility."""

        return self._document

    def sync_default_font(self, font: QFont) -> None:
        """Apply a copied widget font to the mirror when it changed."""

        current_font = QFont(font)
        if self._default_font is not None and self._default_font == current_font:
            return
        self._document.setDefaultFont(current_font)
        self._default_font = QFont(current_font)

    def sync_text_width(self, width: float) -> None:
        """Apply the current projection layout width to Qt word wrapping."""

        self._document.setTextWidth(width)

    def replace_text(self, text: str) -> None:
        """Replace the mirror text exactly with the committed source text."""

        self._document.setPlainText(text)

    def apply_range_edit(self, edit: PromptProjectionSourceDocumentRangeEdit) -> bool:
        """Apply one bounded mirror edit in place when it is safe."""

        if (
            edit.start < 0
            or edit.end < edit.start
            or edit.end > len(edit.previous_text)
            or self._document.toPlainText() != edit.previous_text
            or edit.previous_text[: edit.start]
            + edit.replacement_text
            + edit.previous_text[edit.end :]
            != edit.next_text
            or len(edit.replacement_text) > 1
            or edit.end - edit.start > 1
        ):
            return False

        cursor = QTextCursor(self._document)
        cursor.beginEditBlock()
        cursor.setPosition(edit.start)
        cursor.setPosition(edit.end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(edit.replacement_text)
        cursor.endEditBlock()
        if self._document.toPlainText() == edit.next_text:
            return True
        self.replace_text(edit.next_text)
        return True

    def replace_with_range_fallback(
        self,
        *,
        next_text: str,
        previous_text: str | None,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> bool:
        """Mirror committed text, preferring a bounded range edit when possible."""

        if previous_text is not None and start is not None and end is not None:
            if replacement_text is not None and self.apply_range_edit(
                PromptProjectionSourceDocumentRangeEdit(
                    previous_text=previous_text,
                    next_text=next_text,
                    start=start,
                    end=end,
                    replacement_text=replacement_text,
                )
            ):
                return True
        self.replace_text(next_text)
        return False


__all__ = ["PromptProjectionSourceDocument"]
