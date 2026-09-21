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

"""Compose the workflow tab bar and its immutable initial identity."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QHBoxLayout, QWidget

from substitute.application.workflows import (
    DEFAULT_WORKFLOW_TAB_LABEL,
    WorkflowSessionService,
    WorkflowTabService,
)
from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.presentation.shell.window_frame import (
    titlebar_menu_content_insert_index,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    TabBar,
    TabCloseButtonDisplayMode,
)


def build_workflow_tabbar(
    window: object,
    menu_container: QWidget,
    backdrop_mode: ShellBackdropMode | None,
) -> tuple[WorkflowTabService, WorkflowSessionService[Any], TabBar]:
    """Build and mount the workflow tab row with one UUID-backed workflow."""

    tab_service = WorkflowTabService()
    initial = tab_service.plan_new_workflow_tab(
        base_name=DEFAULT_WORKFLOW_TAB_LABEL,
        existing_labels=(),
        existing_workflow_ids=(),
    )
    session: WorkflowSessionService[Any] = WorkflowSessionService(
        default_workflow_id=initial.workflow_id
    )
    tabbar = TabBar(window)
    set_backdrop_mode = getattr(tabbar, "set_backdrop_mode", None)
    if callable(set_backdrop_mode):
        set_backdrop_mode(backdrop_mode)
    tabbar.setMovable(True)
    tabbar.setTabMaximumWidth(180)
    tabbar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.ON_HOVER)
    tabbar.setMinimumHeight(10)

    menu_layout = menu_container.layout()
    if menu_layout is None:
        raise RuntimeError("Menu container must expose a layout for workflow tabs.")
    typed_layout = cast(QHBoxLayout, menu_layout)
    insert_index = titlebar_menu_content_insert_index(menu_container)
    typed_layout.insertWidget(insert_index, cast(QWidget, tabbar))
    typed_layout.setStretch(insert_index, 8)
    if insert_index > 0:
        typed_layout.setStretch(insert_index - 1, 0)
    if typed_layout.count() > insert_index + 1:
        typed_layout.setStretch(insert_index + 1, 2)
    return tab_service, session, tabbar


__all__ = ["build_workflow_tabbar"]
