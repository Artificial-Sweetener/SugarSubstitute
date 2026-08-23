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

"""Verify main-window menu composition through real production widgets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QWidget

from substitute.presentation.shell.app_orb_action_cluster import (
    APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME,
    APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH,
)
from substitute.presentation.shell.chrome_style import (
    APP_ORB_LEFT_MARGIN,
    APP_ORB_RESERVED_WIDTH,
    WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    WORKFLOW_TOOLBAR_HEIGHT,
    WORKFLOW_TOOLBAR_VERTICAL_PADDING,
    workflow_chrome_wash_rgba,
)
from substitute.presentation.shell.main_window_menu import build_main_window_menu
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_toolbar_geometry_and_style_are_owned_by_shell_chrome() -> None:
    """The built toolbar should expose its canonical geometry and material style."""

    ensure_qt_application()
    window = QWidget()
    widgets = build_main_window_menu(window, workspace_controller=object())

    assert widgets.menu_bar.objectName() == "WorkflowChromeToolbar"
    assert widgets.menu_bar.height() == WORKFLOW_TOOLBAR_HEIGHT
    assert widgets.menu_bar.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert widgets.menu_bar.sizePolicy().horizontalPolicy() == (
        QSizePolicy.Policy.Expanding
    )
    assert widgets.menu_bar.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert workflow_chrome_wash_rgba(None) in widgets.menu_bar.styleSheet()
    margins = widgets.menu_bar_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        8,
        WORKFLOW_TOOLBAR_VERTICAL_PADDING,
        8,
        WORKFLOW_TOOLBAR_VERTICAL_PADDING,
    )
    assert widgets.orb_action_cluster.geometry().getRect() == (
        APP_ORB_LEFT_MARGIN,
        WORKFLOW_TOOLBAR_VERTICAL_PADDING,
        APP_ORB_RESERVED_WIDTH,
        WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    )
    destroy_qt_object(window)


def test_toolbar_layout_preserves_control_ownership_and_order() -> None:
    """The layout should retain stable owners for orb, search, restart, and overrides."""

    ensure_qt_application()
    window = QWidget()
    widgets = build_main_window_menu(window, workspace_controller=object())
    layout_widgets = [
        widgets.menu_bar_layout.itemAt(index).widget()
        for index in range(widgets.menu_bar_layout.count())
    ]

    assert len(layout_widgets) == 3
    assert layout_widgets[0] is widgets.orb_action_layout_anchor
    assert layout_widgets[1] is widgets.settings_toolbar_search_box
    assert layout_widgets[2] is widgets.pending_restart_button
    for spacer_name in (
        "SettingsToolbarSearchLeadingSpacer",
        "SettingsToolbarSearchBalanceSpacer",
        "RestartToolbarLeadingSpacer",
    ):
        spacer = widgets.menu_bar.findChild(QWidget, spacer_name)
        assert spacer is not None
        assert spacer.isHidden()
        assert widgets.menu_bar_layout.indexOf(spacer) == -1
    assert widgets.orb_action_layout_anchor.objectName() == (
        APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME
    )
    assert widgets.orb_action_layout_anchor.width() == (
        APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH
    )
    assert widgets.cube_stack_mode_button is (
        widgets.orb_action_cluster.cube_stack_button
    )
    assert widgets.override_dropdown_btn is widgets.orb_action_cluster.override_button
    assert widgets.override_dropdown_btn.menu() is widgets.global_override_menu
    assert widgets.override_dropdown_btn.property("layoutAnchorWidget") is (
        widgets.orb_action_layout_anchor
    )
    destroy_qt_object(window)


def test_initial_search_and_restart_surfaces_match_shell_state() -> None:
    """New shell controls should begin hidden and ready for their owning workflows."""

    ensure_qt_application()
    window = QWidget()
    widgets = build_main_window_menu(window, workspace_controller=object())

    assert widgets.override_managers == {}
    assert widgets.context_search_box.isHidden()
    assert widgets.settings_toolbar_search_box.isHidden()
    assert widgets.settings_toolbar_search_box.objectName() == (
        "SettingsToolbarSearchLineEdit"
    )
    assert widgets.settings_toolbar_search_box.width() == 420
    assert widgets.settings_toolbar_search_box.height() == (
        WORKFLOW_TOOLBAR_CONTROL_HEIGHT
    )
    assert widgets.settings_toolbar_search_box.placeholderText() == "Search settings"
    assert widgets.settings_toolbar_search_box.isClearButtonEnabled()
    assert not hasattr(widgets, "generate_button")
    assert not hasattr(widgets, "interrupt_button")
    destroy_qt_object(window)
