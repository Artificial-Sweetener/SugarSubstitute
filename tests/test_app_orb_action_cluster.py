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

"""Contract tests for the under-orb shell action cluster."""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QCursor, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication, QAbstractButton, QWidget
import pytest
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]

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

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "app-orb action cluster Qt tests require non-xdist execution",
        allow_module_level=True,
    )


def test_app_orb_action_cluster_places_actions_under_orb_center() -> None:
    """The under-orb actions should sit on either side of the orb center divider."""

    _app()
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

    _app()
    cluster = AppOrbActionCluster()

    assert cluster.cube_stack_button.hitButton(QPoint(11, 30)) is True
    assert cluster.cube_stack_button.hitButton(QPoint(22, 0)) is False
    assert cluster.override_button.hitButton(QPoint(11, 30)) is True
    assert cluster.override_button.hitButton(QPoint(0, 0)) is False

    cluster.close()


def test_app_orb_action_button_icons_are_shifted_down_inside_buttons() -> None:
    """The lower action glyphs should sit 2 px lower inside their buttons."""

    _app()
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


def test_app_orb_override_button_opens_attached_menu() -> None:
    """The custom override button should preserve menu trigger behavior."""

    _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()

    assert len(menu.exec_calls) == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is True
    assert cluster.override_button._background_color().alpha() > 0

    cluster.close()


def test_app_orb_override_button_closes_open_menu_on_second_click() -> None:
    """Clicking the override button again should close its already-open menu."""

    _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()
    cluster.override_button.click()

    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._background_color().alpha() == 0

    cluster.close()


def test_app_orb_override_button_second_mouse_click_consumes_reopen_signal() -> None:
    """Second owner mouse activation should close without emitting a reopen click."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    clicked_states: list[bool] = []
    cluster.override_button.clicked.connect(
        lambda checked: clicked_states.append(bool(checked))
    )
    cluster.show()
    app.processEvents()

    _send_left_click(cluster.override_button)
    _send_left_click(cluster.override_button)

    assert clicked_states == [False]
    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button.isDown() is False
    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._menu_controller._suppress_next_owner_click is False
    assert (
        cluster.override_button._menu_controller._application_filter_installed is False
    )

    cluster.close()


def test_app_orb_override_button_popup_grabbed_owner_press_closes_without_reopen() -> (
    None
):
    """A popup-grabbed press over the owner should close without reopening."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _WidgetMenuProbe()
    cluster.override_button.setMenu(menu)
    clicked_states: list[bool] = []
    cluster.override_button.clicked.connect(
        lambda checked: clicked_states.append(bool(checked))
    )
    cluster.show()
    app.processEvents()

    _send_left_click(cluster.override_button)
    owner_center = cluster.override_button.mapToGlobal(
        cluster.override_button.rect().center()
    )
    _send_left_press(menu, owner_center)
    _send_left_release(cluster.override_button, owner_center)

    assert clicked_states == [False]
    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert cluster.override_button._menu_controller.is_menu_open() is False

    cluster.close()


def test_app_orb_override_button_does_not_reopen_after_popup_owner_press(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner clicks that first auto-hide the popup should not reopen it."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    app.processEvents()

    cluster.override_button.click()
    QCursor.setPos(
        cluster.override_button.mapToGlobal(cluster.override_button.rect().center())
    )
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 1
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button.isDown() is False
    assert cluster.override_button._menu_controller.is_menu_open() is False

    cluster.close()


def test_app_orb_override_button_does_not_reopen_after_system_hide_on_owner() -> None:
    """QFluent system-hide closure over the owner should consume the owner click."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    app.processEvents()

    cluster.override_button.click()
    QCursor.setPos(
        cluster.override_button.mapToGlobal(cluster.override_button.rect().center())
    )
    menu.visible = False
    menu.isHideBySystem = True
    menu.closedSignal.emit()
    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 1
    assert cluster.override_button._menu_controller.is_menu_open() is False

    cluster.close()


def test_app_orb_override_button_owner_suppression_uses_hit_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Popup closure over the cutout should not suppress the next real click."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    app.processEvents()

    cluster.override_button.click()
    QCursor.setPos(cluster.override_button.mapToGlobal(QPoint(0, 0)))
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)

    assert cluster.override_button.hitButton(QPoint(0, 0)) is False
    assert cluster.override_button._menu_controller._suppress_next_owner_click is False

    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 2
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is True

    cluster.close()


def test_app_orb_override_button_opens_after_elsewhere_release_clears_owner_ignore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closing owner gesture delivered elsewhere must not poison later clicks."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)
    cluster.show()
    app.processEvents()

    cluster.override_button.click()
    QCursor.setPos(
        cluster.override_button.mapToGlobal(cluster.override_button.rect().center())
    )
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    other_widget = QWidget()
    other_widget.resize(20, 20)
    other_widget.show()
    app.processEvents()
    _send_left_release(other_widget)
    _send_left_click(cluster.override_button)

    assert len(menu.exec_calls) == 2
    assert cluster.override_button.isChecked() is False
    assert cluster.override_button._menu_controller.is_menu_open() is True
    assert cluster.override_button._menu_controller._suppress_next_owner_click is False
    assert (
        cluster.override_button._menu_controller._application_filter_installed is True
    )

    other_widget.close()
    cluster.close()


def test_app_orb_override_button_failed_open_stays_unclicked_visual() -> None:
    """A failed menu open should not leave the override button looking clicked."""

    _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe(open_on_exec=False)
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()

    assert len(menu.exec_calls) == 1
    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._background_color().alpha() == 0

    cluster.override_button.click()

    assert len(menu.exec_calls) == 2

    cluster.close()


def test_app_orb_override_button_external_close_repaints_unclicked_visual() -> None:
    """Click-away popup closure should immediately clear the clicked visual."""

    _app()
    cluster = AppOrbActionCluster()
    menu = _MenuProbe()
    cluster.override_button.setMenu(menu)

    cluster.override_button.click()

    assert cluster.override_button._menu_controller.is_menu_open() is True
    assert cluster.override_button._background_color().alpha() > 0

    menu.visible = False
    menu.closedSignal.emit()

    assert cluster.override_button._menu_controller.is_menu_open() is False
    assert cluster.override_button._background_color().alpha() == 0

    cluster.close()


def test_app_orb_override_button_positions_menu_left_anchored() -> None:
    """Shell menus should open from the button's left edge and extend rightward."""

    app = _app()
    cluster = AppOrbActionCluster()
    menu = _QFluentMenuProbe(left_margin=7)
    cluster.override_button.setMenu(menu)
    cluster.show()
    app.processEvents()

    cluster.override_button.click()

    expected_position = cluster.override_button.mapToGlobal(
        QPoint(0, cluster.override_button.height())
    )
    assert menu.exec_calls[0][0][0] == expected_position
    assert menu.exec_calls[0][1]["aniType"] is MenuAnimationType.DROP_DOWN
    assert menu.view.adjust_calls[-1] == (
        expected_position,
        MenuAnimationType.DROP_DOWN,
    )

    cluster.close()


def test_app_orb_cube_stack_button_does_not_paint_checked_as_menu_open() -> None:
    """Compact state should not reuse the menu button's clicked visual fill."""

    _app()
    cluster = AppOrbActionCluster()

    cluster.cube_stack_button.setChecked(True)

    assert cluster.cube_stack_button._background_color().alpha() == 0

    cluster.close()


def test_app_orb_action_cluster_renders_without_standard_toolbar_buttons() -> None:
    """The custom cluster should render its own shaped buttons and glyphs."""

    _app()
    cluster = AppOrbActionCluster()
    image = QImage(
        QSize(APP_ORB_RESERVED_WIDTH, WORKFLOW_TOOLBAR_CONTROL_HEIGHT),
        QImage.Format.Format_ARGB32,
    )

    cluster.render(image)

    assert not image.isNull()

    cluster.close()


class _MenuProbe:
    """Record menu execution calls from the custom override button."""

    def __init__(self, *, open_on_exec: bool = True) -> None:
        """Initialize the empty execution call list."""

        self.exec_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.hide_calls = 0
        self.visible = False
        self.isHideBySystem = False
        self._open_on_exec = open_on_exec
        self.aboutToHide = _SignalProbe()
        self.closedSignal = _SignalProbe()

    def exec(self, *args: object, **kwargs: object) -> None:
        """Record one menu execution call."""

        self.exec_calls.append((args, kwargs))
        self.visible = self._open_on_exec

    def hide(self) -> None:
        """Record one menu hide call."""

        self.hide_calls += 1
        self.visible = False

    def isVisible(self) -> bool:
        """Return whether the probe menu is considered visible."""

        return self.visible


class _WidgetMenuProbe(QWidget):
    """Record menu calls while receiving real Qt mouse events."""

    def __init__(self) -> None:
        """Initialize widget-backed menu probe state."""

        super().__init__()
        self.exec_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.hide_calls = 0

    def exec(self, *args: object, **kwargs: object) -> None:
        """Record one menu execution and show the widget."""

        self.exec_calls.append((args, kwargs))
        self.show()

    def hide(self) -> None:
        """Record one hide and delegate to QWidget."""

        self.hide_calls += 1
        super().hide()


class _QFluentMenuProbe(_MenuProbe):
    """Record QFluent-style menu sizing and positioning calls."""

    def __init__(self, *, left_margin: int) -> None:
        """Initialize a visible QFluent-shaped menu probe."""

        super().__init__()
        self.left_margin = left_margin
        self.view = _QFluentMenuViewProbe()

    def layout(self) -> object:
        """Return a layout probe exposing content margins."""

        return _LayoutProbe(self.left_margin)

    def adjustSize(self) -> None:
        """Accept menu-level size adjustment."""


class _QFluentMenuViewProbe:
    """Record QFluent menu-view sizing calls."""

    def __init__(self) -> None:
        """Initialize empty sizing call storage."""

        self.minimum_widths: list[int] = []
        self.adjust_calls: list[tuple[object, ...]] = []

    def setMinimumWidth(self, width: int) -> None:
        """Record the requested minimum menu width."""

        self.minimum_widths.append(width)

    def adjustSize(self, *args: object) -> None:
        """Record QFluent view adjustment calls."""

        self.adjust_calls.append(args)

    def heightForAnimation(
        self,
        _position: QPoint,
        animation_type: MenuAnimationType,
    ) -> int:
        """Prefer drop-down animation for deterministic placement tests."""

        return 100 if animation_type is MenuAnimationType.DROP_DOWN else 20


class _LayoutProbe:
    """Expose QFluent-style layout content margins."""

    def __init__(self, left_margin: int) -> None:
        """Store the left margin returned by the margin probe."""

        self._left_margin = left_margin

    def contentsMargins(self) -> object:
        """Return a margin probe."""

        return _MarginProbe(self._left_margin)


class _MarginProbe:
    """Expose the left content margin used by QFluent menu placement."""

    def __init__(self, left_margin: int) -> None:
        """Store the left margin."""

        self._left_margin = left_margin

    def left(self) -> int:
        """Return the stored left margin."""

        return self._left_margin


class _SignalProbe:
    """Store and emit callbacks for fake Qt signals."""

    def __init__(self) -> None:
        """Initialize the callback list."""

        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self._callbacks.append(callback)

    def emit(self) -> None:
        """Invoke all connected callbacks."""

        for callback in self._callbacks:
            if callable(callback):
                callback()


def _send_left_click(button: QAbstractButton) -> None:
    """Send a real press/release sequence to ``button``."""

    center = button.rect().center()
    global_center = button.mapToGlobal(center)
    _send_left_press(button, global_center)
    _send_left_release(button, global_center)


def _send_left_press(widget: QWidget, global_position: QPoint) -> None:
    """Send one left-button press to ``widget`` at ``global_position``."""

    local_position = widget.mapFromGlobal(global_position)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(local_position),
        QPointF(global_position),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, press)


def _send_left_release(
    widget: QWidget,
    global_position: QPoint | None = None,
) -> None:
    """Send a left-button release to ``widget``."""

    if global_position is None:
        global_position = widget.mapToGlobal(widget.rect().center())
    local_position = widget.mapFromGlobal(global_position)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(local_position),
        QPointF(global_position),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, release)


def _emit_about_to_hide_during_left_press(
    monkeypatch: pytest.MonkeyPatch,
    menu: _MenuProbe,
) -> None:
    """Emit menu closure while the application reports a left-button press."""

    import substitute.presentation.shell.menu_button_controller as controller_module

    monkeypatch.setattr(
        controller_module,
        "left_mouse_button_is_down",
        lambda: True,
    )
    menu.aboutToHide.emit()


def _app() -> QApplication:
    """Return the shared QApplication used by app-orb action tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
