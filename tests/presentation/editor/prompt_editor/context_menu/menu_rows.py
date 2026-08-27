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

"""Read visible context-menu rows through QFluent's rendered item model."""

from __future__ import annotations

from PySide6.QtCore import Qt
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)


def visible_menu_rows(menu: RoundMenu) -> list[str]:
    """Return menu labels in rendered order, retaining separator boundaries."""

    rows: list[str] = []
    for row in range(menu.view.count()):
        item = menu.view.item(row)
        if item.data(Qt.ItemDataRole.DecorationRole) == "seperator":
            rows.append("<separator>")
            continue
        action = item.data(Qt.ItemDataRole.UserRole)
        if hasattr(action, "text"):
            rows.append(str(action.text()))
        else:
            rows.append(item.text().strip())
    return rows
