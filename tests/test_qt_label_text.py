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

"""Tests for Qt label text preparation."""

from __future__ import annotations

from substitute.presentation.qt_label_text import literal_label_text


def test_literal_label_text_escapes_ampersands_for_qt_labels() -> None:
    """Literal labels should preserve authored ampersands instead of mnemonics."""

    assert literal_label_text("Schedule & Encode Prompts") == (
        "Schedule && Encode Prompts"
    )
