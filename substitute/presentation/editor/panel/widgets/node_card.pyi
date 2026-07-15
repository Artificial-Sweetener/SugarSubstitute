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

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor

class NodeCardWidget(QWidget):
    def __init__(self, parent: Any) -> None: ...

class _NodeCardSurface(QWidget): ...
class _NodeCardContentSurface(QWidget): ...
class _NodeCardHeaderSurface(QWidget): ...

def _node_card_background_color(widget: QWidget | None = ...) -> QColor: ...
def _node_card_border_color() -> QColor: ...
def reconcile_node_card_body_separators(
    row_widgets: Mapping[object, tuple[object | None, object | None]],
) -> None: ...
def rotate_icon(icon_enum: Any, angle: int) -> Any: ...

NODE_CARD_TITLE_ICON_SLOT_SIZE: int
NODE_CARD_TITLE_ICON_SIZE: int
NODE_CARD_TITLE_HEIGHT: int
NODE_CARD_BODY_TOP_PADDING: int
NODE_CARD_BODY_BOTTOM_PADDING: int
NODE_CARD_BODY_ROW_SPACING: int
