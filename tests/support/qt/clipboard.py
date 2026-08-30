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

"""Preserve the process clipboard around focused Qt interaction tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtGui import QClipboard

from tests.support.qt.lifecycle import ensure_qt_application


@contextmanager
def preserve_qt_clipboard() -> Iterator[QClipboard]:
    """Restore clipboard text after one test-owned interaction."""

    clipboard = ensure_qt_application().clipboard()
    original_text = clipboard.text()
    try:
        yield clipboard
    finally:
        clipboard.setText(original_text)


__all__ = ["preserve_qt_clipboard"]
