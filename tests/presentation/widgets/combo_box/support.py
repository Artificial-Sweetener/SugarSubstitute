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

"""Own mounted searchable-combo test state and exact Qt lifetime."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.combo_box import ComboBox

DEFAULT_COMBO_ITEMS = (
    "Flat",
    "Euler",
    "Euclid",
    "Heun",
    "DPM++ 2M Karras",
    "Beta Euler",
)


@dataclass(frozen=True, slots=True)
class MountedCombo:
    """Expose one visible combo and its owning host widget."""

    host: QWidget
    combo: ComboBox


def mount_combo(
    *,
    items: tuple[str, ...] = DEFAULT_COMBO_ITEMS,
    host_size: tuple[int, int] = (480, 240),
    host_position: QPoint | None = None,
    combo_position: QPoint | None = None,
) -> MountedCombo:
    """Create one visible production combo under a dedicated Qt owner."""

    host = QWidget()
    host.resize(*host_size)
    if host_position is not None:
        host.move(host_position)
    host.show()
    combo = ComboBox(host)
    combo.addItems(items)
    combo.resize(220, 34)
    if combo_position is not None:
        combo.move(combo_position)
    combo.show()
    return MountedCombo(host=host, combo=combo)
