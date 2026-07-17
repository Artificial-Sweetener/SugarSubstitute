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

"""Contract tests for the shell titlebar Comfy output toggle."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
import pytest
from qframelesswindow.titlebar.title_bar_buttons import (  # type: ignore[import-untyped]
    TitleBarButton,
    TitleBarButtonState,
)

from substitute.presentation.shell.titlebar_buttons import ComfyOutputToggleButton
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.chrome_style import (
    APP_ORB_DIAMETER,
    APP_ORB_LEFT_MARGIN,
    APP_ORB_TAB_RESERVED_WIDTH,
    APP_ORB_TOP,
    BODY_MATERIAL_SURFACE_OBJECT_NAME,
    WORKFLOW_TITLEBAR_HEIGHT,
    WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT,
    body_material_wash_rgba,
    workflow_chrome_wash_rgba,
)
from substitute.presentation.shell.window_frame import (
    APP_ORB_TITLEBAR_SPACER_OBJECT_NAME,
    ShellBackdropMode,
    SubstituteWindowFrame,
    titlebar_menu_content_insert_index,
)
import substitute.presentation.shell.window_frame as window_frame

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "titlebar Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by frameless-window contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


class _WorkflowTabDragOwner:
    """Expose mutable workflow-tab gesture state for titlebar tests."""

    def __init__(self, *, idle: bool) -> None:
        """Store whether the fake workflow-tab gesture is idle."""

        self.idle = idle

    def workflow_tab_gesture_is_idle(self) -> bool:
        """Return whether the fake workflow-tab gesture is idle."""

        return self.idle


def test_shell_frame_inserts_comfy_output_toggle_before_minimize_button() -> None:
    """The shell frame should place the Comfy output toggle in the titlebar cluster."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
    )

    assert frame.menuContainer is not None
    assert frame.comfyOutputToggleButton is not None
    menu_layout = frame.menuContainer.layout()
    assert menu_layout is not None
    assert frame.titleBar.height() == WORKFLOW_TITLEBAR_HEIGHT
    assert menu_layout.contentsMargins().top() == (WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT)
    assert isinstance(frame.comfyOutputToggleButton, TitleBarButton)
    assert frame.comfyOutputToggleButton.isCheckable() is True
    assert frame.comfyOutputToggleButton.toolTip() == "Show Comfy output"
    assert frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) == (
        frame.titleBar.layout().indexOf(frame.titleBar.minBtn) - 1
    )

    frame.set_comfy_output_toggle_checked(True)

    assert frame.comfyOutputToggleButton.isChecked() is True
    assert frame.comfyOutputToggleButton.toolTip() == "Hide Comfy output"

    frame.close()


def test_shell_titlebar_blocks_native_move_during_workflow_tab_gesture() -> None:
    """Active workflow-tab gestures must not become qframeless window drags."""

    _app()
    frame = SubstituteWindowFrame(create_menu_container=True)
    frame.resize(900, 160)
    frame.set_workflow_tab_drag_owner(_WorkflowTabDragOwner(idle=False))

    assert frame.titleBar.canDrag(QPoint(80, 18)) is False

    frame.close()


def test_shell_titlebar_keeps_native_move_when_workflow_tabs_idle() -> None:
    """Idle workflow-tab state should leave qframeless titlebar dragging intact."""

    _app()
    frame = SubstituteWindowFrame(create_menu_container=True)
    frame.resize(900, 160)
    frame.set_workflow_tab_drag_owner(_WorkflowTabDragOwner(idle=True))

    assert frame.titleBar.canDrag(QPoint(80, 18)) is True

    frame.close()


def test_shell_frame_positions_app_orb_as_frame_overlay() -> None:
    """The app orb should overlap titlebar and toolbar as a frame child."""

    app = _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_app_orb_menu=True,
    )
    frame.resize(1200, 800)
    frame.show()
    app.processEvents()

    assert frame.appOrbMenuButton is not None
    assert frame.appOrbMenuButton.parentWidget() is frame
    assert frame.appOrbMenuButton.geometry().getRect() == (
        APP_ORB_LEFT_MARGIN,
        APP_ORB_TOP,
        APP_ORB_DIAMETER,
        APP_ORB_DIAMETER,
    )

    frame.resize(1280, 820)
    app.processEvents()

    assert frame.appOrbMenuButton.geometry().getRect() == (
        APP_ORB_LEFT_MARGIN,
        APP_ORB_TOP,
        APP_ORB_DIAMETER,
        APP_ORB_DIAMETER,
    )

    frame.close()


def test_shell_frame_titlebar_container_reserves_app_orb_space() -> None:
    """The workflow tabbar insertion index should follow shell-owned spacers."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_app_orb_menu=True,
    )

    assert frame.menuContainer is not None
    menu_layout = frame.menuContainer.layout()
    assert menu_layout is not None
    spacer_item = menu_layout.itemAt(0)
    assert spacer_item is not None
    spacer = spacer_item.widget()
    assert spacer is not None
    assert spacer.objectName() == APP_ORB_TITLEBAR_SPACER_OBJECT_NAME
    assert spacer.minimumWidth() == APP_ORB_TAB_RESERVED_WIDTH
    assert spacer.maximumWidth() == APP_ORB_TAB_RESERVED_WIDTH
    assert titlebar_menu_content_insert_index(frame.menuContainer) == 1

    frame.close()


def test_comfy_output_toggle_uses_window_console_app_icon() -> None:
    """The console toggle should use the vendored Fluent window console icon."""

    _app()
    button = ComfyOutputToggleButton()

    assert button._icon is AppIcon.WINDOW_CONSOLE_20_FILLED

    button.close()


def test_comfy_output_toggle_uses_qframeless_hover_backgrounds_when_checked() -> None:
    """Checked console hover and press backgrounds should follow TitleBarButton."""

    _app()
    button = ComfyOutputToggleButton()
    button.setChecked(True)

    button.setState(TitleBarButtonState.HOVER)
    assert button._background_color() == button.getHoverBackgroundColor()

    button.setState(TitleBarButtonState.PRESSED)
    assert button._background_color() == button.getPressedBackgroundColor()

    button.close()


def test_comfy_output_toggle_paints_hover_when_under_mouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Console hover paint should survive missed qframeless enter transitions."""

    _app()
    button = ComfyOutputToggleButton()
    button.setState(TitleBarButtonState.NORMAL)
    monkeypatch.setattr(button, "underMouse", lambda: True)

    assert button._background_color() == button.getHoverBackgroundColor()

    button.close()


def test_shell_frame_styles_comfy_output_toggle_like_min_max_buttons() -> None:
    """The console toggle should use the same hover policy as min/max buttons."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
    )
    assert frame.comfyOutputToggleButton is not None

    output_button = frame.comfyOutputToggleButton
    assert output_button.getHoverBackgroundColor() == (
        frame.titleBar.minBtn.getHoverBackgroundColor()
    )
    assert output_button.getPressedBackgroundColor() == (
        frame.titleBar.minBtn.getPressedBackgroundColor()
    )
    assert output_button.getNormalBackgroundColor() == (
        frame.titleBar.minBtn.getNormalBackgroundColor()
    )

    output_button.setChecked(True)
    output_button.setState(TitleBarButtonState.HOVER)
    assert output_button._background_color() == (
        frame.titleBar.minBtn.getHoverBackgroundColor()
    )

    output_button.setState(TitleBarButtonState.PRESSED)
    assert output_button._background_color() == (
        frame.titleBar.minBtn.getPressedBackgroundColor()
    )

    frame.close()


def test_shell_frame_inserts_generation_cluster_left_of_output_toggle() -> None:
    """The generation cluster should sit directly left of the Comfy output toggle."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
    )

    assert frame.generationActionCluster is not None
    assert frame.comfyOutputToggleButton is not None
    assert frame.generationActionCluster.segment_roles == (
        "stop",
        "play",
        "skip",
        "queue",
    )
    assert frame.generationActionCluster.bottom_corner_radius > 0
    assert frame.generationActionCluster.top_bleed > 0
    assert frame.titleBar.layout().indexOf(frame.generationActionCluster) == (
        frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) - 1
    )
    assert frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) == (
        frame.titleBar.layout().indexOf(frame.titleBar.minBtn) - 1
    )

    frame.close()


def test_shell_frame_inserts_startup_diagnostics_between_generation_and_output() -> (
    None
):
    """Startup diagnostics should sit between generation and console titlebar controls."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
        create_startup_diagnostics_button=True,
    )

    assert frame.generationActionCluster is not None
    assert frame.startupDiagnosticsButton is not None
    assert frame.comfyOutputToggleButton is not None
    layout = frame.titleBar.layout()

    assert layout.indexOf(frame.generationActionCluster) == (
        layout.indexOf(frame.startupDiagnosticsButton) - 1
    )
    assert layout.indexOf(frame.startupDiagnosticsButton) == (
        layout.indexOf(frame.comfyOutputToggleButton) - 1
    )
    assert layout.indexOf(frame.comfyOutputToggleButton) == (
        layout.indexOf(frame.titleBar.minBtn) - 1
    )
    assert frame.startupDiagnosticsButton.is_collapsed() is True

    frame.close()


def test_startup_diagnostics_expansion_settles_left_of_output_before_signal() -> None:
    """Expansion signal should fire after titlebar geometry stops overlapping."""

    app = _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
        create_startup_diagnostics_button=True,
    )
    frame.resize(1440, 900)
    frame.show()
    app.processEvents()
    assert frame.startupDiagnosticsButton is not None
    assert frame.comfyOutputToggleButton is not None

    emitted_geometry: list[tuple[int, int]] = []
    frame.startupDiagnosticsButton.expanded.connect(
        lambda: emitted_geometry.append(
            (
                frame.startupDiagnosticsButton.x()
                + frame.startupDiagnosticsButton.width(),
                frame.comfyOutputToggleButton.x(),
            )
        )
    )

    frame.startupDiagnosticsButton.set_collapsed(False)
    QTest.qWait(200)
    app.processEvents()

    assert emitted_geometry
    diagnostics_right, output_left = emitted_geometry[-1]
    assert diagnostics_right <= output_left

    frame.close()


def test_shell_frame_leaves_diagnostics_absent_when_not_requested() -> None:
    """Default shell frame construction should not create a diagnostics titlebar button."""

    _app()
    frame = SubstituteWindowFrame(
        create_menu_container=True,
        create_comfy_output_toggle=True,
        create_generation_action_cluster=True,
    )

    assert frame.startupDiagnosticsButton is None
    assert frame.generationActionCluster is not None
    assert frame.comfyOutputToggleButton is not None
    assert frame.titleBar.layout().indexOf(frame.generationActionCluster) == (
        frame.titleBar.layout().indexOf(frame.comfyOutputToggleButton) - 1
    )

    frame.close()


def test_shell_frame_backdrop_modes_route_to_expected_native_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backdrop mode selection should map materials and respect dark/light state."""

    effect_calls: list[tuple[str, dict[str, object]]] = []

    def record_mica(_handle: object, **kwargs: object) -> None:
        """Record one fake Mica call."""

        effect_calls.append(("mica", kwargs))

    acrylic_fix_calls: list[object] = []

    def record_acrylic_fix(window: object) -> None:
        """Record acrylic helper routing without invoking Win32 APIs."""

        acrylic_fix_calls.append(window)

    fake_frame = SimpleNamespace(
        _backdrop_mode=ShellBackdropMode.MICA,
        windowEffect=SimpleNamespace(
            setMicaEffect=record_mica,
            setAcrylicEffect=lambda *_args: None,
        ),
        winId=lambda: 123,
        _is_dark_backdrop_enabled=lambda: False,
    )
    monkeypatch.setattr(window_frame, "apply_acrylic_effect", record_acrylic_fix)
    SubstituteWindowFrame._apply_backdrop(cast(Any, fake_frame))
    fake_frame._backdrop_mode = ShellBackdropMode.MICA_ALT
    SubstituteWindowFrame._apply_backdrop(cast(Any, fake_frame))
    fake_frame._backdrop_mode = ShellBackdropMode.ACRYLIC
    SubstituteWindowFrame._apply_backdrop(cast(Any, fake_frame))

    assert effect_calls == [
        ("mica", {"isDarkMode": False, "isAlt": False}),
        ("mica", {"isDarkMode": False, "isAlt": True}),
    ]
    assert acrylic_fix_calls == [fake_frame]


def test_apply_acrylic_effect_applies_native_effect_then_normalizes_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic helper should run the toolkit effect before normalizing chrome."""

    calls: list[tuple[str, object]] = []
    fake_window = SimpleNamespace(
        windowEffect=SimpleNamespace(
            setAcrylicEffect=lambda handle, color: calls.append(
                ("effect", (handle, color))
            )
        ),
        winId=lambda: 123,
    )
    monkeypatch.setattr(
        window_frame,
        "normalize_acrylic_frameless_chrome",
        lambda window: calls.append(("normalize", window)),
    )

    window_frame.apply_acrylic_effect(fake_window)

    assert calls == [
        ("effect", (123, window_frame.ACRYLIC_BLEND_COLOR)),
        ("normalize", fake_window),
    ]


@pytest.mark.parametrize(
    ("dark_theme", "expected_color"),
    [(True, "#202020"), (False, "#f8f8f8")],
)
def test_non_material_shell_paints_an_opaque_theme_surface(
    monkeypatch: pytest.MonkeyPatch,
    dark_theme: bool,
    expected_color: str,
) -> None:
    """Avoid compositor-gray shells when native materials are unavailable."""

    _app()
    monkeypatch.setattr(window_frame, "isDarkTheme", lambda: dark_theme)
    frame = SubstituteWindowFrame(backdrop_mode=None)

    assert frame.autoFillBackground() is True
    assert (
        frame.palette().color(QPalette.ColorRole.Window).name().lower()
        == expected_color
    )

    frame.deleteLater()


def test_normalize_acrylic_frameless_chrome_restores_frameless_resize_bits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic normalization should restore frameless resize bits and refresh."""

    style_before = 0x00C00000 | 0x00080000
    style_updates: list[tuple[int, int, int]] = []
    frame_updates: list[tuple[int, object, int, int, int, int, int]] = []
    flag_updates: list[tuple[object, bool]] = []
    corner_updates: list[int] = []

    fake_win32con = SimpleNamespace(
        GWL_STYLE=-16,
        WS_CAPTION=0x00C00000,
        WS_THICKFRAME=0x00040000,
        WS_MINIMIZEBOX=0x00020000,
        WS_MAXIMIZEBOX=0x00010000,
        SWP_NOMOVE=0x0002,
        SWP_NOSIZE=0x0001,
        SWP_NOZORDER=0x0004,
        SWP_FRAMECHANGED=0x0020,
    )
    fake_win32gui = SimpleNamespace(
        GetWindowLong=lambda hwnd, index: (
            style_before if (hwnd, index) == (123, -16) else 0
        ),
        SetWindowLong=lambda hwnd, index, style: style_updates.append(
            (hwnd, index, style)
        ),
        SetWindowPos=lambda hwnd, insert_after, x, y, cx, cy, flags: (
            frame_updates.append((hwnd, insert_after, x, y, cx, cy, flags))
        ),
    )

    monkeypatch.setattr(window_frame, "_PLATFORM", "win32")
    monkeypatch.setattr(window_frame, "win32con", fake_win32con)
    monkeypatch.setattr(window_frame, "win32gui", fake_win32gui)
    monkeypatch.setattr(
        window_frame,
        "restore_rounded_window_corners",
        lambda window_id: corner_updates.append(int(window_id)),
    )

    fake_window = SimpleNamespace(
        setWindowFlag=lambda flag, enabled: flag_updates.append((flag, enabled)),
        winId=lambda: 123,
    )

    window_frame.normalize_acrylic_frameless_chrome(fake_window)

    assert flag_updates == [(Qt.WindowType.FramelessWindowHint, True)]
    assert style_updates == [
        (
            123,
            -16,
            (
                style_before
                | fake_win32con.WS_THICKFRAME
                | fake_win32con.WS_MINIMIZEBOX
                | fake_win32con.WS_MAXIMIZEBOX
            )
            & ~fake_win32con.WS_CAPTION,
        )
    ]
    assert frame_updates == [
        (
            123,
            None,
            0,
            0,
            0,
            0,
            fake_win32con.SWP_NOMOVE
            | fake_win32con.SWP_NOSIZE
            | fake_win32con.SWP_NOZORDER
            | fake_win32con.SWP_FRAMECHANGED,
        )
    ]
    assert corner_updates == [123]


def test_normalize_acrylic_frameless_chrome_noops_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acrylic normalization should be inert outside Windows."""

    calls: list[str] = []
    fake_win32gui = SimpleNamespace(
        GetWindowLong=lambda *_args: calls.append("get"),
        SetWindowLong=lambda *_args: calls.append("set"),
        SetWindowPos=lambda *_args: calls.append("pos"),
    )

    monkeypatch.setattr(window_frame, "_PLATFORM", "linux")
    monkeypatch.setattr(window_frame, "win32gui", fake_win32gui)

    fake_window = SimpleNamespace(
        setWindowFlag=lambda *_args: calls.append("flag"),
        winId=lambda: 123,
    )

    window_frame.normalize_acrylic_frameless_chrome(fake_window)

    assert calls == []


def test_restore_rounded_window_corners_requests_windows_11_rounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rounded-corner helper should request the standard Win11 round preference."""

    calls: list[tuple[int, int, int, int]] = []

    fake_dwmapi = SimpleNamespace(
        DwmSetWindowAttribute=lambda hwnd, attribute, value, size: calls.append(
            (hwnd, attribute, cast(int, value._obj.value), size)
        )
    )

    monkeypatch.setattr(window_frame, "_PLATFORM", "win32")
    monkeypatch.setattr(window_frame, "_DWMAPI", fake_dwmapi)
    monkeypatch.setattr(window_frame, "_WINDOWS_BUILD", 26200)
    monkeypatch.setattr(window_frame, "_WINDOW_CORNER_ATTRIBUTE", 33)
    monkeypatch.setattr(window_frame, "_WINDOW_CORNER_ROUND", 2)

    window_frame.restore_rounded_window_corners(123)

    assert calls == [(123, 33, 2, 4)]


def test_shell_frame_body_material_surface_owns_main_body_wash() -> None:
    """The optional body material surface should wrap body content below titlebar."""

    _app()
    frame = SubstituteWindowFrame(
        backdrop_mode=ShellBackdropMode.MICA_ALT,
        create_body_material_surface=True,
    )
    body_widget = QWidget()

    frame.add_body_widget(body_widget)

    assert frame.layout() is not None
    assert frame.layout().contentsMargins().top() == frame.titleBar.height()
    assert frame.bodyMaterialSurface is not None
    assert frame.bodyMaterialLayout is not None
    assert frame.bodyMaterialSurface.objectName() == BODY_MATERIAL_SURFACE_OBJECT_NAME
    assert body_material_wash_rgba() in frame.bodyMaterialSurface.styleSheet()
    assert workflow_chrome_wash_rgba().startswith("rgba(")
    assert body_widget.parent() is frame.bodyMaterialSurface
    assert frame.titleBar.parent() is frame

    frame.close()
