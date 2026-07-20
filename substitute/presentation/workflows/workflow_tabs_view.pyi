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

from sugarsubstitute_shared.localization import ApplicationMessage

TabCloseButtonDisplayMode: Any
SETTINGS_WORKSPACE_ROUTE: str
REOPEN_CLOSED_WORKFLOW_MENU_TEXT: ApplicationMessage

def workflow_tab_source_text(item: object) -> str: ...
def set_workflow_tab_source_text(item: object, text: str) -> None: ...

class TabItem:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def orb_cutout_progress(self) -> float: ...
    def set_orb_cutout_active(self, active: bool, *, animated: bool = True) -> None: ...
    def set_orb_cutout_preview_progress(self, progress: float) -> None: ...

class WorkflowTabCornerOverlay:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...

class TabBar:
    currentChanged: Any
    tabBarClicked: Any
    tabCloseRequested: Any
    tabAddRequested: Any
    tabRenamed: Any
    workflowSelected: Any
    workflowCloseRequested: Any
    workflowAddRequested: Any
    workflowRenameRequested: Any
    workflowDuplicateRequested: Any
    workflowReopenClosedRequested: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def workflow_ids_in_order(self) -> list[str]: ...
    def is_settings_route(self, route_key: str | None) -> bool: ...
    def selected_route_key(self) -> str | None: ...
    def clear_selection(self) -> None: ...
    def invalidate_orb_cutout_overlay(self) -> None: ...
    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None: ...
    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None: ...
    def move_workflow_tab(
        self,
        workflow_id: str,
        target_index: int,
        *,
        animated: bool = False,
    ) -> None: ...
    def set_reopen_closed_workflow_enabled(self, enabled: bool) -> None: ...
