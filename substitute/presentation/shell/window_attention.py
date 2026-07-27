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

"""Request native user attention for visible shell windows without stealing focus."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


def request_window_attention_if_inactive(window: QWidget) -> bool:
    """Request platform attention when the visible window does not have focus."""

    if window.isActiveWindow():
        return False
    QApplication.alert(window, 0)
    return True


__all__ = ["request_window_attention_if_inactive"]
