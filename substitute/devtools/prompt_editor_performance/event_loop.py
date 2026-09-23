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

"""Flush bounded Qt event turns for prompt-editor performance timings."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


def process_events(app: QApplication, cycles: int = 3) -> None:
    """Flush a bounded number of Qt event-loop turns."""

    for _ in range(cycles):
        app.processEvents()


__all__ = ["process_events"]
