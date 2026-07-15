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

"""Prepare literal user-facing text for Qt label widgets."""

from __future__ import annotations


def literal_label_text(text: str) -> str:
    """Return text escaped for QLabel-style literal display.

    Qt treats ampersands in label text as mnemonic markers. Escaping each
    ampersand preserves authored names such as "Schedule & Encode Prompts".
    """

    return text.replace("&", "&&")


__all__ = ["literal_label_text"]
