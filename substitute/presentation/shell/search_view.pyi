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

from typing import Any

class FloatingSearchBox:
    contextSearchChanged: Any
    cycleSearchMatchRequested: Any
    cycleSearchMatchRequestedBackward: Any
    closed: Any
    contextSearchBox: Any
    nextButton: Any
    prevButton: Any
    closeButton: Any

    def __init__(self, parent: Any = ...) -> None: ...
    def set_navigation_enabled(self, enabled: bool) -> None: ...
    def hide(self) -> None: ...
    def searchLineEdit(self) -> Any: ...
    def context(self) -> str: ...
    def searchText(self) -> str: ...
