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

"""Cover bootstrap main-window lifecycle composition."""

from __future__ import annotations

import importlib
from pathlib import Path
import types
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap import composition
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from tests.support.qt.lifecycle import destroy_widget_roots


def _ensure_runtime_qapplication() -> None:
    """Ensure startup runtime services have a real Qt owner during tests."""

    if QApplication.instance() is None:
        QApplication([])


def _destroy_qt_widgets(*widgets: QWidget) -> None:
    """Synchronously dispose test-owned widgets without draining global events."""

    destroy_widget_roots(widgets)


def _resolved_appearance_stub() -> object:
    """Return one resolved-appearance stub for startup contract tests."""

    return SimpleNamespace(
        effective_theme_mode=SimpleNamespace(value="dark"),
        effective_accent_color="#E91E63",
        effective_backdrop_mode=None,
    )


def _build_ready_context(tmp_path: Path) -> InstallationContext:
    """Build a ready installation context for startup routing tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


def test_show_main_window_adds_main_window_to_shell_body(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Shell composition should delegate body placement to the frame-owned surface."""

    _ensure_runtime_qapplication()
    context = _build_ready_context(tmp_path)
    added_body_widgets: list[QWidget] = []
    assigned_window_icons: list[object] = []
    attached_app_orbs: list[object] = []

    class _FakeSignal:
        def connect(self, _callback: object) -> None:
            """Accept one connected callback."""

    class _FakeScreen:
        def availableGeometry(self) -> object:
            """Return one large desktop geometry."""

            return types.SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame(QWidget):
        def __init__(
            self,
            *,
            appearance_runtime: object | None = None,
            shutdown_request: object | None = None,
            backdrop_mode: object | None = None,
            create_body_material_surface: bool = False,
        ) -> None:
            super().__init__()
            self.menuContainer = QWidget(self)
            self.comfyOutputToggleButton = None
            self.appOrbMenuButton = object()
            self.titleBar = types.SimpleNamespace(
                height=lambda: 64,
                closeBtn=types.SimpleNamespace(clicked=_FakeSignal()),
            )
            self.appearance_runtime = appearance_runtime
            self.shutdown_request = shutdown_request
            self.backdrop_mode = backdrop_mode
            self.create_body_material_surface = create_body_material_surface

        def setWindowTitle(self, _title: str) -> None:
            """Accept title updates."""

        def setWindowIcon(self, _icon: object) -> None:
            """Accept icon updates."""

            assigned_window_icons.append(_icon)

        def screen(self) -> _FakeScreen:  # type: ignore[override]
            """Return the fake screen geometry."""

            return _FakeScreen()

        def add_body_widget(self, widget: QWidget) -> None:
            """Record shell-body content placement."""

            added_body_widgets.append(widget)

    class _FakeMainWindow(QWidget):
        comfy_output_panel_visibility_changed = _FakeSignal()

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__()
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.menu_container = kwargs["menu_container"]
            self.dependencies = kwargs["dependencies"]
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda app_orb_menu: attached_app_orbs.append(
                    app_orb_menu
                ),
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    fake_module = types.ModuleType("substitute.presentation.shell.main_window")
    setattr(fake_module, "MainWindow", _FakeMainWindow)

    monkeypatch.setattr(
        composition, "_configure_control_registry_service", lambda: None
    )
    monkeypatch.setattr(
        composition,
        "_build_main_window_dependencies",
        lambda _runtime_services: SimpleNamespace(
            shell_resource_lifecycle=SimpleNamespace(shutdown=lambda *_args: ())
        ),
    )
    monkeypatch.setattr(composition, "CustomWindow", _FakeFrame)
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)

    frame = composition.show_main_window(
        context,
        comfy_output_stream=cast(Any, object()),
        runtime_services=cast(
            Any,
            SimpleNamespace(
                appearance_runtime=SimpleNamespace(
                    resolve_preferences=_resolved_appearance_stub
                )
            ),
        ),
    )

    assert len(added_body_widgets) == 1
    assert isinstance(added_body_widgets[0], _FakeMainWindow)
    assert not hasattr(frame, "mainWindow")
    assert composition.main_window_widget(frame) is added_body_widgets[0]
    assert len(assigned_window_icons) == 1
    assert isinstance(assigned_window_icons[0], QIcon)
    assert not assigned_window_icons[0].isNull()
    assert attached_app_orbs == [frame.appOrbMenuButton]

    _destroy_qt_widgets(frame)


def test_show_main_window_wires_titlebar_close_button_to_window_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Titlebar close should use the same close path as a normal shell close."""

    _ensure_runtime_qapplication()
    context = _build_ready_context(tmp_path)
    connected_callbacks: list[object] = []
    close_calls: list[object] = []

    class _FakeSignal:
        def connect(self, callback: object) -> None:
            connected_callbacks.append(callback)

    class _FakeScreen:
        def availableGeometry(self) -> object:
            return SimpleNamespace(
                width=lambda: 1920,
                height=lambda: 1080,
                left=lambda: 0,
                top=lambda: 0,
            )

    class _FakeFrame(QWidget):
        def __init__(
            self,
            *,
            appearance_runtime: object | None = None,
            shutdown_request: object | None = None,
            backdrop_mode: object | None = None,
            create_body_material_surface: bool = False,
        ) -> None:
            super().__init__()
            self.menuContainer = QWidget(self)
            self.comfyOutputToggleButton = None
            self.titleBar = SimpleNamespace(
                height=lambda: 64,
                closeBtn=SimpleNamespace(clicked=_FakeSignal()),
            )
            self.appearance_runtime = appearance_runtime
            self.shutdown_request = shutdown_request
            self.backdrop_mode = backdrop_mode
            self.create_body_material_surface = create_body_material_surface

        def setWindowTitle(self, _title: str) -> None:
            return None

        def setWindowIcon(self, _icon: object) -> None:
            return None

        def screen(self) -> _FakeScreen:  # type: ignore[override]
            return _FakeScreen()

        def close(self) -> bool:
            close_calls.append(self)
            return True

        def add_body_widget(self, _widget: QWidget) -> None:
            return None

    class _FakeMainWindow(QWidget):
        comfy_output_panel_visibility_changed = _FakeSignal()

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__()
            self.shell_frame_integration_controller = SimpleNamespace(
                set_taskbar_progress_presenter=lambda _presenter: None,
                attach_app_orb_menu=lambda _app_orb_menu: None,
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )

    fake_module = types.ModuleType("substitute.presentation.shell.main_window")
    setattr(fake_module, "MainWindow", _FakeMainWindow)

    monkeypatch.setattr(
        composition, "_configure_control_registry_service", lambda: None
    )
    monkeypatch.setattr(
        composition,
        "_build_main_window_dependencies",
        lambda _runtime_services: SimpleNamespace(
            shell_resource_lifecycle=SimpleNamespace(shutdown=lambda *_args: ())
        ),
    )
    monkeypatch.setattr(composition, "CustomWindow", _FakeFrame)
    monkeypatch.setattr(importlib, "import_module", lambda _name: fake_module)

    frame = composition.show_main_window(
        context,
        comfy_output_stream=cast(Any, object()),
        shutdown_request=_noop_shutdown_request,
        runtime_services=cast(
            Any,
            SimpleNamespace(
                appearance_runtime=SimpleNamespace(
                    resolve_preferences=_resolved_appearance_stub
                )
            ),
        ),
    )

    assert connected_callbacks == [frame.close]
    cast(Any, connected_callbacks[0])()
    assert close_calls == [frame]

    _destroy_qt_widgets(frame)


def _noop_shutdown_request(_parent: QWidget | None = None) -> None:
    """Provide one typed no-op shutdown callback for shell composition tests."""
