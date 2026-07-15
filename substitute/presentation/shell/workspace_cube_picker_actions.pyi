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

from collections.abc import Callable
from typing import Any, Protocol

class CubePickerProtocol(Protocol): ...

class WorkspaceCubePickerActionView(Protocol):
    cube_icon_factory: Any
    cube_stack_service: Any
    node_behavior_service: Any
    active_workflow_surface_refresher: Any

class CatalogRefreshRoute:
    def __init__(self, *, submitter: Any, close: Callable[[], None]) -> None: ...

class WorkspaceCubePickerActions:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def prepare_node_behavior_runtime(self, *args: Any, **kwargs: Any) -> Any: ...
    def show_cube_picker(
        self,
        *,
        cube_picker: CubePickerProtocol | None = ...,
        icon_provider: Any = ...,
        cube_loader: Any = ...,
    ) -> None: ...
