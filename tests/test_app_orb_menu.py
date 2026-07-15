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

"""Contract tests for the shell application orb menu button."""

from __future__ import annotations

import os
from typing import Any, cast

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QCursor, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QAbstractButton, QWidget
import pytest
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]

from substitute.presentation.shell.app_orb_menu import (
    APP_ORB_MENU_ACCESSIBLE_NAME,
    APP_ORB_MENU_OBJECT_NAME,
    APP_ORB_MENU_OVERLAP_PX,
    COMFYUI_SETTINGS_MENU_TEXT,
    EXPORT_COMFY_WORKFLOW_MENU_TEXT,
    OPEN_SUGAR_SCRIPT_MENU_TEXT,
    RESTART_COMFYUI_MENU_TEXT,
    RESTART_GUI_MENU_TEXT,
    SAVE_SUGAR_SCRIPT_AS_MENU_TEXT,
    SAVE_SUGAR_SCRIPT_MENU_TEXT,
    SETTINGS_MENU_TEXT,
    AppOrbMenuButton,
)
from substitute.presentation.shell.chrome_style import APP_ORB_DIAMETER

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "app-orb Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by app-orb contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_app_orb_menu_button_exposes_expected_menu_actions() -> None:
    """The app orb should own the first-pass application command menu."""

    _app()
    button = AppOrbMenuButton()

    assert button.objectName() == APP_ORB_MENU_OBJECT_NAME
    assert button.isCheckable() is False
    assert button.toolTip() == APP_ORB_MENU_ACCESSIBLE_NAME
    assert button.accessibleName() == APP_ORB_MENU_ACCESSIBLE_NAME
    assert button._open_action.text() == OPEN_SUGAR_SCRIPT_MENU_TEXT
    assert button._save_action.text() == SAVE_SUGAR_SCRIPT_MENU_TEXT
    assert button._save_as_action.text() == SAVE_SUGAR_SCRIPT_AS_MENU_TEXT
    assert button._export_action.text() == EXPORT_COMFY_WORKFLOW_MENU_TEXT
    assert button._settings_action.text() == SETTINGS_MENU_TEXT
    assert button._comfyui_settings_action.text() == COMFYUI_SETTINGS_MENU_TEXT
    assert button._restart_gui_action.text() == RESTART_GUI_MENU_TEXT
    assert button._restart_comfyui_action.text() == RESTART_COMFYUI_MENU_TEXT
    restart_actions = [
        action.text()
        for action in button._menu.actions()
        if action.text() in {RESTART_GUI_MENU_TEXT, RESTART_COMFYUI_MENU_TEXT}
    ]
    assert restart_actions == [RESTART_GUI_MENU_TEXT, RESTART_COMFYUI_MENU_TEXT]
    assert not hasattr(button, "_reopen_closed_workflow_action")
    assert not hasattr(button, "reopenClosedWorkflowRequested")
    assert not hasattr(button, "set_reopen_closed_workflow_enabled")

    button.close()


def test_app_orb_menu_actions_emit_intent_signals() -> None:
    """Triggering menu actions should emit intents without owning file behavior."""

    _app()
    button = AppOrbMenuButton()
    emitted: list[str] = []
    button.openRequested.connect(lambda: emitted.append("open"))
    button.saveRequested.connect(lambda: emitted.append("save"))
    button.saveAsRequested.connect(lambda: emitted.append("save-as"))
    button.exportRequested.connect(lambda: emitted.append("export"))
    button.settingsRequested.connect(lambda: emitted.append("settings"))
    button.comfyUiSettingsRequested.connect(lambda: emitted.append("comfy-settings"))
    button.restartGuiRequested.connect(lambda: emitted.append("restart-gui"))
    button.restartComfyRequested.connect(lambda: emitted.append("restart-comfy"))

    button._open_action.trigger()
    button._save_action.trigger()
    button._save_as_action.trigger()
    button._export_action.trigger()
    button._settings_action.trigger()
    button._comfyui_settings_action.trigger()
    button._restart_gui_action.trigger()
    button._restart_comfyui_action.trigger()

    assert emitted == [
        "open",
        "save",
        "save-as",
        "export",
        "settings",
        "comfy-settings",
        "restart-gui",
        "restart-comfy",
    ]

    button.close()


def test_app_orb_menu_workflow_file_actions_can_be_disabled() -> None:
    """Settings route policy should gray out workflow-only file commands."""

    _app()
    button = AppOrbMenuButton()

    button.set_workflow_file_actions_enabled(False)

    assert button._open_action.isEnabled() is True
    assert button._save_action.isEnabled() is False
    assert button._save_as_action.isEnabled() is False
    assert button._export_action.isEnabled() is False
    assert button._settings_action.isEnabled() is True
    assert button._comfyui_settings_action.isEnabled() is True
    assert button._restart_gui_action.isEnabled() is True
    assert button._restart_comfyui_action.isEnabled() is True
    button.set_workflow_file_actions_enabled(True)

    assert button._save_action.isEnabled() is True
    assert button._save_as_action.isEnabled() is True
    assert button._export_action.isEnabled() is True

    button.close()


def test_app_orb_menu_button_closes_open_menu_on_second_click() -> None:
    """Clicking the app orb again should close its already-open command menu."""

    _app()
    button = AppOrbMenuButton()
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)

    button.click()
    button.click()

    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert button.isChecked() is False
    assert button._menu_controller.is_menu_open() is False

    button.close()


def test_app_orb_menu_button_second_mouse_click_consumes_reopen_signal() -> None:
    """Second owner mouse activation should close without emitting a reopen click."""

    app = _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    clicked_states: list[bool] = []
    button.clicked.connect(lambda checked: clicked_states.append(bool(checked)))
    button.show()
    app.processEvents()

    _send_left_click(button)
    _send_left_click(button)

    assert clicked_states == [False]
    assert len(menu.exec_calls) == 1
    assert menu.hide_calls == 1
    assert button.isChecked() is False
    assert button.isDown() is False
    assert button._menu_controller.is_menu_open() is False
    assert button._menu_controller._suppress_next_owner_click is False
    assert button._menu_controller._application_filter_installed is False

    button.close()


def test_app_orb_menu_button_does_not_reopen_after_popup_owner_press(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner clicks that first auto-hide the popup should not reopen it."""

    app = _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    app.processEvents()

    button.click()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    _send_left_click(button)

    assert len(menu.exec_calls) == 1
    assert button.isChecked() is False
    assert button.isDown() is False
    assert button._menu_controller.is_menu_open() is False

    button.close()


def test_app_orb_menu_button_does_not_reopen_after_system_hide_on_owner() -> None:
    """QFluent system-hide closure over the orb should consume the owner click."""

    app = _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    app.processEvents()

    button.click()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    menu.visible = False
    menu.isHideBySystem = True
    menu.closedSignal.emit()
    _send_left_click(button)

    assert len(menu.exec_calls) == 1
    assert button._menu_controller.is_menu_open() is False

    button.close()


def test_app_orb_menu_button_opens_after_elsewhere_release_clears_owner_ignore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closing owner gesture delivered elsewhere must not poison later clicks."""

    app = _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _MenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    app.processEvents()

    button.click()
    QCursor.setPos(button.mapToGlobal(button.rect().center()))
    menu.visible = False
    _emit_about_to_hide_during_left_press(monkeypatch, menu)
    other_widget = QWidget()
    other_widget.resize(20, 20)
    other_widget.show()
    app.processEvents()
    _send_left_release(other_widget)
    _send_left_click(button)

    assert len(menu.exec_calls) == 2
    assert button.isChecked() is False
    assert button._menu_controller.is_menu_open() is True
    assert button._menu_controller._suppress_next_owner_click is False
    assert button._menu_controller._application_filter_installed is True

    other_widget.close()
    button.close()


def test_app_orb_menu_button_failed_open_stays_unclicked_visual() -> None:
    """A failed menu open should not leave the orb in its clicked visual state."""

    _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    renderer = _RendererProbe()
    menu = _MenuProbe(open_on_exec=False)
    cast(Any, button)._orb_renderer = renderer
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    image = QImage(
        button.size(),
        QImage.Format.Format_ARGB32,
    )

    button.click()
    button.render(image)

    assert len(menu.exec_calls) == 1
    assert button._menu_controller.is_menu_open() is False
    assert renderer.calls[-1]["pressed"] is False

    button.click()

    assert len(menu.exec_calls) == 2

    button.close()


def test_app_orb_menu_button_external_close_repaints_unclicked_visual() -> None:
    """Click-away popup closure should immediately clear the orb clicked visual."""

    _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    renderer = _RendererProbe()
    menu = _MenuProbe()
    cast(Any, button)._orb_renderer = renderer
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    image = QImage(
        button.size(),
        QImage.Format.Format_ARGB32,
    )

    button.click()
    button.render(image)

    assert button._menu_controller.is_menu_open() is True
    assert renderer.calls[-1]["pressed"] is True

    menu.visible = False
    menu.closedSignal.emit()
    button.render(image)

    assert button._menu_controller.is_menu_open() is False
    assert renderer.calls[-1]["pressed"] is False

    button.close()


def test_app_orb_menu_button_qfluent_menu_tucks_under_orb_edge() -> None:
    """The app-orb menu should overlap the orb edge without covering row text."""

    app = _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)
    menu = _QFluentMenuProbe()
    cast(Any, button)._menu = menu
    cast(Any, button)._menu_controller.set_menu(menu)
    button.show()
    app.processEvents()

    button.click()

    expected_position = button.mapToGlobal(
        QPoint(0, button.height() - APP_ORB_MENU_OVERLAP_PX)
    )
    assert menu.exec_calls[0][0][0] == expected_position
    assert menu.exec_calls[0][1]["aniType"] is MenuAnimationType.DROP_DOWN
    assert menu.view.adjust_calls[-1] == (
        expected_position,
        MenuAnimationType.DROP_DOWN,
    )

    button.close()


def test_app_orb_menu_button_reuses_shared_application_icon() -> None:
    """The orb should paint the same app icon resource used by the shell."""

    _app()
    button = AppOrbMenuButton()

    assert button._orb_renderer.app_icon().cacheKey() == button._app_icon.cacheKey()

    button.close()


class _RendererProbe:
    """Record app-orb render state requests."""

    def __init__(self) -> None:
        """Initialize the empty render call list."""

        self.calls: list[dict[str, object]] = []

    def app_icon(self) -> object:
        """Return a stable icon identity for tests that inspect the renderer."""

        return object()

    def clear_cache(self) -> None:
        """Accept cache clearing without side effects."""

    def render(self, size: object, **kwargs: object) -> QPixmap:
        """Record render state and return a transparent pixmap."""

        self.calls.append(kwargs)
        if not hasattr(size, "width") or not hasattr(size, "height"):
            pixmap = QPixmap(1, 1)
            pixmap.fill(Qt.GlobalColor.transparent)
            return pixmap
        typed_size = cast(Any, size)
        pixmap = QPixmap(
            max(1, int(typed_size.width())),
            max(1, int(typed_size.height())),
        )
        pixmap.fill(Qt.GlobalColor.transparent)
        return pixmap


class _MenuProbe:
    """Record app-orb menu execution and hide calls."""

    def __init__(self, *, open_on_exec: bool = True) -> None:
        """Initialize fake menu state."""

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


class _QFluentMenuProbe(_MenuProbe):
    """Record QFluent-style app-orb menu sizing and positioning calls."""

    def __init__(self) -> None:
        """Initialize a QFluent-shaped menu probe."""

        super().__init__()
        self.view = _QFluentMenuViewProbe()

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
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(center),
        QPointF(global_center),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(center),
        QPointF(global_center),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(button, press)
    QApplication.sendEvent(button, release)


def _send_left_release(widget: QWidget) -> None:
    """Send a left-button release to ``widget``."""

    center = widget.rect().center()
    global_center = widget.mapToGlobal(center)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(center),
        QPointF(global_center),
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


def test_app_orb_menu_button_connects_theme_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Theme and accent changes should invalidate cached orb art."""

    import substitute.presentation.shell.app_orb_menu as orb_menu_module

    _app()
    callbacks: list[tuple[AppOrbMenuButton, object]] = []

    def connect_theme_refresh(widget: object, refresh: object) -> None:
        """Capture the button's refresh callback instead of registering globally."""

        callbacks.append((cast(AppOrbMenuButton, widget), refresh))

    monkeypatch.setattr(orb_menu_module, "connect_theme_refresh", connect_theme_refresh)
    button = AppOrbMenuButton()

    assert callbacks == [(button, button._refresh_orb_theme)]

    button.close()


def test_app_orb_hit_button_uses_circular_target() -> None:
    """The square overlay widget should only accept clicks inside its circle."""

    _app()
    button = AppOrbMenuButton()
    button.resize(APP_ORB_DIAMETER, APP_ORB_DIAMETER)

    assert button.hitButton(button.rect().center()) is True
    assert button.hitButton(QPoint(0, 0)) is False

    button.close()
