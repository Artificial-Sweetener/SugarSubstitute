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

"""Own the shared model-recommendation card geometry."""

from PySide6.QtCore import QSize

CARD_WIDTH = 204
CARD_HEIGHT = 220
PORTRAIT_WIDTH = 184
PORTRAIT_HEIGHT = 200
THUMBNAIL_SIZE = QSize(PORTRAIT_WIDTH, PORTRAIT_HEIGHT)

__all__ = [
    "CARD_HEIGHT",
    "CARD_WIDTH",
    "PORTRAIT_HEIGHT",
    "PORTRAIT_WIDTH",
    "THUMBNAIL_SIZE",
]
