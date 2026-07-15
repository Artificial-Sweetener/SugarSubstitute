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

"""Contract tests for Settings as a shell-owned non-tab route."""

from __future__ import annotations

import os

import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableTabItemBase,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
    TabBar,
    TabItem,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "workflow tab Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_settings_route_cannot_be_added_as_workflow_tab() -> None:
    """Settings should stay owned by the app menu instead of the workflow tabbar."""

    _app()
    tabbar = TabBar()

    with pytest.raises(ValueError, match="shell-owned route"):
        tabbar.addTab(SETTINGS_WORKSPACE_ROUTE, "Settings")

    assert SETTINGS_WORKSPACE_ROUTE not in tabbar.itemMap
    assert tabbar.count() == 0
    assert tabbar.workflow_ids_in_order() == []


def test_settings_projection_can_clear_workflow_tab_selection() -> None:
    """Opening Settings from the app menu should leave no workflow tab selected."""

    _app()
    tabbar = TabBar()
    workflow_emissions: list[str] = []
    tabbar.workflowSelected.connect(workflow_emissions.append)
    tabbar.addTab("wf-a", "Untitled Workflow")

    assert tabbar.selected_route_key() == "wf-a"

    tabbar.clear_selection()

    assert tabbar.currentIndex() == -1
    assert tabbar.selected_route_key() is None
    assert tabbar.workflow_ids_in_order() == ["wf-a"]
    assert workflow_emissions == []


def test_settings_projection_preserves_orb_adjacent_tab_ownership() -> None:
    """Opening Settings should clear selection without changing first-tab cutout role."""

    _app()
    tabbar = TabBar()
    first_tab = tabbar.addTab("wf-a", "First")
    second_tab = tabbar.addTab("wf-b", "Second")

    assert isinstance(first_tab, TabItem)
    assert isinstance(second_tab, TabItem)
    assert first_tab.orb_cutout_progress() == 1.0
    assert second_tab.orb_cutout_progress() == 0.0

    tabbar.clear_selection()

    assert tabbar.currentIndex() == -1
    assert first_tab.orb_cutout_progress() == 1.0
    assert second_tab.orb_cutout_progress() == 0.0


def test_workflow_helpers_ignore_shell_owned_settings_route() -> None:
    """Workflow-only helpers should not treat Settings as a workflow id."""

    _app()
    tabbar = TabBar()
    workflow_emissions: list[str] = []
    tabbar.workflowSelected.connect(workflow_emissions.append)
    tabbar.addTab("wf-a", "Untitled Workflow")

    tabbar.select_workflow_tab(SETTINGS_WORKSPACE_ROUTE, emit=True)
    tabbar.remove_workflow_tab(SETTINGS_WORKSPACE_ROUTE, emit=True)

    assert SETTINGS_WORKSPACE_ROUTE not in tabbar.itemMap
    assert tabbar.workflow_ids_in_order() == ["wf-a"]
    assert tabbar.selected_route_key() == "wf-a"
    assert workflow_emissions == []


def test_empty_tab_text_paint_path_does_not_divide_by_zero() -> None:
    """Empty tab labels should not crash the shared tab text painter."""

    _app()
    item = ReorderableTabItemBase("")
    pixmap = QPixmap(64, 36)
    painter = QPainter(pixmap)
    try:
        item._drawText(painter)
    finally:
        painter.end()


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
