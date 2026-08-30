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

"""Test app-orb action-cluster layout and hit geometry."""

from __future__ import annotations


from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget
import pytest

from substitute.presentation.shell.app_orb_action_cluster import (
    APP_ORB_ACTION_CLUSTER_OBJECT_NAME,
    APP_ORB_ACTION_SEPARATOR_OBJECT_NAME,
    APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME,
    APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME,
    AppOrbActionCluster,
)
from substitute.presentation.shell.chrome_style import (
    APP_ORB_RESERVED_WIDTH,
    WORKFLOW_TOOLBAR_CONTROL_HEIGHT,
)

from tests.presentation.shell.app_orb.support import app


def test_app_orb_action_cluster_places_actions_under_orb_center() -> None:
    """The under-orb actions should sit on either side of the orb center divider."""

    app()
    cluster = AppOrbActionCluster()

    assert cluster.objectName() == APP_ORB_ACTION_CLUSTER_OBJECT_NAME
    assert cluster.minimumWidth() == APP_ORB_RESERVED_WIDTH
    assert cluster.maximumWidth() == APP_ORB_RESERVED_WIDTH
    assert cluster.minimumHeight() == WORKFLOW_TOOLBAR_CONTROL_HEIGHT
    assert cluster.maximumHeight() == WORKFLOW_TOOLBAR_CONTROL_HEIGHT
    assert (
        cluster.cube_stack_button.objectName() == APP_ORB_CUBE_STACK_BUTTON_OBJECT_NAME
    )
    assert cluster.override_button.objectName() == APP_ORB_OVERRIDE_BUTTON_OBJECT_NAME
    assert cluster.cube_stack_button.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert cluster.override_button.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert cluster.cube_stack_button.accessibleName() == "Collapse cube stack"
    assert cluster.override_button.accessibleName() == "Select Global Field Overrides"
    assert cluster.override_button.isCheckable() is False
    assert cluster.cube_stack_button.geometry().getRect() == (0, 0, 23, 36)
    assert cluster.override_button.geometry().getRect() == (24, 0, 23, 36)

    separator = cluster.findChild(QWidget, APP_ORB_ACTION_SEPARATOR_OBJECT_NAME)

    assert separator is not None
    assert separator.geometry().getRect() == (23, 20, 1, 10)

    cluster.close()


def test_app_orb_action_buttons_use_punched_hit_shape() -> None:
    """The button hit target should follow the same top cutout used for hover paint."""

    app()
    cluster = AppOrbActionCluster()

    assert cluster.cube_stack_button.hitButton(QPoint(11, 30)) is True
    assert cluster.cube_stack_button.hitButton(QPoint(22, 0)) is False
    assert cluster.override_button.hitButton(QPoint(11, 30)) is True
    assert cluster.override_button.hitButton(QPoint(0, 0)) is False

    cluster.close()


def test_app_orb_action_button_icons_are_shifted_down_inside_buttons() -> None:
    """The lower action glyphs should sit 2 px lower inside their buttons."""

    app()
    cluster = AppOrbActionCluster()

    cube_icon_rect = cluster.cube_stack_button._icon_rect()
    pin_icon_rect = cluster.override_button._pin_icon_rect()
    chevron_bounds = cluster.override_button._chevron_path().boundingRect()

    assert cube_icon_rect.y() == pytest.approx(18.5)
    assert cube_icon_rect.bottom() <= cluster.cube_stack_button.height()
    assert pin_icon_rect.y() == pytest.approx(17.0)
    assert pin_icon_rect.bottom() <= cluster.override_button.height()
    assert chevron_bounds.top() == pytest.approx(31.0)
    assert chevron_bounds.bottom() <= cluster.override_button.height()

    cluster.close()


def test_app_orb_cube_stack_button_does_not_paint_checked_as_menu_open() -> None:
    """Compact state should not reuse the menu button's clicked visual fill."""

    app()
    cluster = AppOrbActionCluster()

    cluster.cube_stack_button.setChecked(True)

    assert cluster.cube_stack_button._background_color().alpha() == 0

    cluster.close()


def test_app_orb_action_cluster_renders_without_standard_toolbar_buttons() -> None:
    """The custom cluster should render its own shaped buttons and glyphs."""

    app()
    cluster = AppOrbActionCluster()
    image = QImage(
        QSize(APP_ORB_RESERVED_WIDTH, WORKFLOW_TOOLBAR_CONTROL_HEIGHT),
        QImage.Format.Format_ARGB32,
    )

    cluster.render(image)

    assert not image.isNull()

    cluster.close()
