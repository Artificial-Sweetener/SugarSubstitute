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

"""Route accordion transition boundaries to their owning cube section."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from shiboken6 import isValid


class AccordionSectionLayoutBinding:
    """Translate accordion motion boundaries into section-owned layout work."""

    def __init__(self, anchor: QWidget) -> None:
        """Store a card descendant used to locate its nearest section owner."""

        self._anchor = anchor

    def preserve_transition_geometry(self) -> None:
        """Keep section sizing stable while clipped accordion motion begins."""

        self._notify_owner(settled=False)

    def finalize_transition_geometry(self) -> None:
        """Settle the section after the accordion reaches its resting state."""

        self._notify_owner(settled=True)

    def _notify_owner(self, *, settled: bool) -> None:
        """Invoke the strongest layout boundary exposed by the nearest owner."""

        parent = self._anchor.parentWidget()
        while parent is not None and isValid(parent):
            if settled:
                layout = parent.layout()
                if layout is not None:
                    layout.invalidate()
                parent.updateGeometry()
                finalize = getattr(
                    parent,
                    "finalize_layout_after_child_relayout",
                    None,
                )
                if callable(finalize):
                    finalize(reason="accordion_motion_finished")
                    return
            update_height = getattr(parent, "update_cube_height", None)
            if callable(update_height):
                update_height()
                return
            parent = parent.parentWidget()


__all__ = ["AccordionSectionLayoutBinding"]
