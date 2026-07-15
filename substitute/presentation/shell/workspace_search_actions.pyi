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

from typing import Any, Protocol

class WorkspaceSearchActionView(Protocol): ...

class WorkspaceSearchActions:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def on_cycle_search_match(self, *args: Any, **kwargs: Any) -> None: ...
    def on_cycle_search_match_backward(self, *args: Any, **kwargs: Any) -> None: ...
    def on_context_search_changed(self, *args: Any, **kwargs: Any) -> None: ...
    def on_search_closed(self, *args: Any, **kwargs: Any) -> None: ...
    def proxy_override_menu_toggled(self, *args: Any, **kwargs: Any) -> None: ...
