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

"""Build the MainWindow menu-row widgets and controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)
from qfluentwidgets import CheckableMenu, MenuIndicatorType  # type: ignore[import-untyped]

from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from substitute.presentation.shell.search_view import FloatingSearchBox
from substitute.presentation.shell.settings_toolbar_search import (
    SettingsToolbarSearchBox,
)
from substitute.presentation.shell.pending_restart_toolbar_button import (
    PendingRestartToolbarButton,
)
from substitute.presentation.shell.app_orb_action_cluster import (
    APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME,
    APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH,
    AppOrbActionCluster,
    AppOrbCubeStackButton,
    AppOrbOverrideButton,
)
from substitute.presentation.shell.chrome_style import (
    APP_ORB_LEFT_MARGIN,
    APP_ORB_RESERVED_WIDTH,
    WORKFLOW_TOOLBAR_HEIGHT,
    WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    WORKFLOW_TOOLBAR_VERTICAL_PADDING,
    connect_theme_refresh,
    workflow_chrome_wash_rgba,
)
from substitute.presentation.shell.window_frame import ShellBackdropMode


@dataclass(frozen=True)
class MainWindowMenuWidgets:
    """Bundle widgets and actions built for the shell menu row."""

    menu_bar: QWidget
    menu_bar_layout: QHBoxLayout
    orb_action_cluster: AppOrbActionCluster
    orb_action_layout_anchor: QWidget
    cube_stack_mode_button: AppOrbCubeStackButton
    override_dropdown_btn: AppOrbOverrideButton
    pending_restart_button: PendingRestartToolbarButton
    settings_toolbar_search_box: SettingsToolbarSearchBox
    context_search_box: FloatingSearchBox
    global_override_menu: CheckableMenu
    override_managers: dict[str, GlobalOverridesManager]


def build_main_window_menu(
    window: QWidget,
    *,
    backdrop_mode: ShellBackdropMode | None = None,
    workspace_controller: object,
) -> MainWindowMenuWidgets:
    """Build the full menu row for MainWindow."""

    menu_bar = QWidget(window)
    menu_bar.setObjectName("WorkflowChromeToolbar")
    menu_bar.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    menu_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    menu_bar.setFixedHeight(WORKFLOW_TOOLBAR_HEIGHT)
    menu_bar_layout = QHBoxLayout(menu_bar)
    menu_bar_layout.setDirection(QBoxLayout.Direction.LeftToRight)
    menu_bar_layout.setContentsMargins(
        8,
        WORKFLOW_TOOLBAR_VERTICAL_PADDING,
        8,
        WORKFLOW_TOOLBAR_VERTICAL_PADDING,
    )
    menu_bar_layout.setSpacing(4)

    orb_action_layout_anchor = QWidget(menu_bar)
    orb_action_layout_anchor.setObjectName(APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME)
    orb_action_layout_anchor.setFixedWidth(APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH)
    menu_bar_layout.addWidget(orb_action_layout_anchor)

    orb_action_cluster = AppOrbActionCluster(menu_bar)
    orb_action_cluster.setGeometry(
        APP_ORB_LEFT_MARGIN,
        WORKFLOW_TOOLBAR_VERTICAL_PADDING,
        APP_ORB_RESERVED_WIDTH,
        WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
    )
    orb_action_cluster.raise_()
    cube_stack_mode_button = orb_action_cluster.cube_stack_button
    override_dropdown_btn = orb_action_cluster.override_button
    override_dropdown_btn.setProperty(
        "layoutAnchorWidget",
        orb_action_layout_anchor,
    )

    settings_toolbar_search_box = SettingsToolbarSearchBox(menu_bar)
    settings_toolbar_search_box.setFixedHeight(WORKFLOW_TOOLBAR_CONTROL_HEIGHT)
    settings_toolbar_search_box.hide()

    settings_toolbar_search_leading_spacer = QWidget(menu_bar)
    settings_toolbar_search_leading_spacer.setObjectName(
        "SettingsToolbarSearchLeadingSpacer"
    )
    settings_toolbar_search_leading_spacer.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )
    menu_bar_layout.addWidget(settings_toolbar_search_leading_spacer)

    menu_bar_layout.addWidget(settings_toolbar_search_box)

    settings_toolbar_search_balance_spacer = QWidget(menu_bar)
    settings_toolbar_search_balance_spacer.setObjectName(
        "SettingsToolbarSearchBalanceSpacer"
    )
    settings_toolbar_search_balance_spacer.setFixedWidth(
        APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH
    )
    menu_bar_layout.addWidget(settings_toolbar_search_balance_spacer)

    restart_toolbar_leading_spacer = QWidget(menu_bar)
    restart_toolbar_leading_spacer.setObjectName("RestartToolbarLeadingSpacer")
    restart_toolbar_leading_spacer.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )
    menu_bar_layout.addWidget(restart_toolbar_leading_spacer)

    pending_restart_button = PendingRestartToolbarButton(menu_bar)
    pending_restart_button.set_centering_spacer(
        settings_toolbar_search_leading_spacer,
        toolbar=menu_bar,
    )
    pending_restart_button.set_balance_spacer(
        settings_toolbar_search_balance_spacer,
        expanded_width=APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH,
        center_widget=settings_toolbar_search_box,
        toolbar=menu_bar,
    )
    pending_restart_button.set_alignment_spacer(
        restart_toolbar_leading_spacer,
        toolbar=menu_bar,
    )
    menu_bar_layout.addWidget(pending_restart_button)

    context_search_box = FloatingSearchBox(window)
    cast(QWidget, context_search_box).setParent(window)
    context_search_box.hide()

    global_override_menu = CheckableMenu(
        parent=menu_bar,
        indicatorType=MenuIndicatorType.CHECK,
    )
    override_dropdown_btn.setMenu(global_override_menu)
    override_managers: dict[str, GlobalOverridesManager] = {}

    def _apply_theme_styles() -> None:
        menu_bar.setStyleSheet(
            f"""
            QWidget#WorkflowChromeToolbar {{
                background-color: {workflow_chrome_wash_rgba(backdrop_mode)};
                border: none;
            }}
            """
        )

    _apply_theme_styles()
    connect_theme_refresh(menu_bar, _apply_theme_styles)

    return MainWindowMenuWidgets(
        menu_bar=menu_bar,
        menu_bar_layout=menu_bar_layout,
        orb_action_cluster=orb_action_cluster,
        orb_action_layout_anchor=orb_action_layout_anchor,
        cube_stack_mode_button=cube_stack_mode_button,
        override_dropdown_btn=override_dropdown_btn,
        pending_restart_button=pending_restart_button,
        settings_toolbar_search_box=settings_toolbar_search_box,
        context_search_box=context_search_box,
        global_override_menu=global_override_menu,
        override_managers=override_managers,
    )


__all__ = ["MainWindowMenuWidgets", "build_main_window_menu"]
