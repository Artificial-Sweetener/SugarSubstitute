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

"""Cover main-window attachment to the bootstrap shell."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QApplication, QWidget

from substitute.app.bootstrap import composition
from tests.support.qt.lifecycle import destroy_widget_roots


def _ensure_runtime_qapplication() -> None:
    """Ensure shell attachment tests have a real Qt application owner."""

    if QApplication.instance() is None:
        QApplication([])


def _destroy_qt_widgets(*widgets: QWidget) -> None:
    """Synchronously dispose test-owned Qt widgets."""

    destroy_widget_roots(widgets)


def test_attach_main_window_to_shell_syncs_app_orb_after_body_attachment() -> None:
    """Body attachment should raise the frame-owned app orb after MainWindow is added."""

    _ensure_runtime_qapplication()
    events: list[str] = []

    class _FakeFrame(QWidget):
        def __init__(self) -> None:
            """Create a shell-frame double without optional titlebar controls."""

            super().__init__()
            self.menuContainer = None
            self.generationActionCluster = None
            self.comfyOutputToggleButton = None
            self.startupDiagnosticsButton = None

        def add_body_widget(self, _widget: QWidget) -> None:
            """Record body attachment order."""

            events.append("body")

        def sync_app_orb_overlay(self) -> None:
            """Record app-orb overlay sync order."""

            events.append("orb")

    class _FakeMainWindow(QWidget):
        workflow_tabbar = None
        comfy_output_panel_visibility_changed = SimpleNamespace(
            connect=lambda *_args: None
        )

        def __init__(self) -> None:
            """Create the protocol attributes used by shell attachment."""

            super().__init__()
            self.workspace_controller = SimpleNamespace()
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    frame = _FakeFrame()
    main_window = _FakeMainWindow()

    composition._attach_main_window_to_shell(
        cast(composition.CustomWindow, frame),
        main_window,
    )

    assert events == ["body", "orb"]

    _destroy_qt_widgets(frame, main_window)


def test_attach_main_window_to_shell_mounts_body_before_moving_titlebar_child(
    monkeypatch: Any,
) -> None:
    """Mount the body first so native child moves stay within one window tree."""

    _ensure_runtime_qapplication()
    events: list[str] = []

    class _FakeFrame(QWidget):
        def __init__(self) -> None:
            """Create a shell-frame double without optional titlebar controls."""

            super().__init__()
            self.generationActionCluster = None
            self.comfyOutputToggleButton = None
            self.startupDiagnosticsButton = None

        def add_body_widget(self, _widget: QWidget) -> None:
            """Record the native body mount."""

            events.append("body")

    class _FakeMainWindow(QWidget):
        comfy_output_panel_visibility_changed = SimpleNamespace(
            connect=lambda *_args: None
        )

        def __init__(self) -> None:
            """Create the protocol attributes used by shell attachment."""

            super().__init__()
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_generation_titlebar_control_registry=lambda _registry: None,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    monkeypatch.setattr(
        composition,
        "_move_workflow_tabbar_to_shell",
        lambda _frame, _main_window: events.append("tabbar"),
    )
    frame = _FakeFrame()
    main_window = _FakeMainWindow()

    composition._attach_main_window_to_shell(
        cast(composition.CustomWindow, frame),
        main_window,
    )

    assert events == ["body", "tabbar"]

    _destroy_qt_widgets(frame, main_window)


def test_attach_main_window_to_shell_uses_generation_action_owner() -> None:
    """Titlebar generation controls should call shell-owned generation actions."""

    _ensure_runtime_qapplication()
    events: list[tuple[str, object]] = []
    registries: list[object] = []
    queue_target = object()

    class _Signal:
        """Provide a tiny Qt-like signal for registry callback assertions."""

        def __init__(self) -> None:
            """Create an empty callback list."""

            self._callbacks: list[Callable[..., None]] = []

        def connect(self, callback: Callable[..., None]) -> None:
            """Record one connected callback."""

            self._callbacks.append(callback)

        def disconnect(self, callback: Callable[..., None]) -> None:
            """Remove one connected callback."""

            self._callbacks.remove(callback)

        def emit(self, *args: object) -> None:
            """Invoke every connected callback with emitted arguments."""

            for callback in tuple(self._callbacks):
                callback(*args)

    class _FakeTitlebarControl:
        """Expose the titlebar control protocol consumed by the registry."""

        def __init__(self) -> None:
            """Create fake titlebar signals and batch-count capture."""

            self.playClicked = _Signal()
            self.skipClicked = _Signal()
            self.stopClicked = _Signal()
            self.queueClicked = _Signal()
            self.queueContextMenuRequested = _Signal()
            self.generateModeSelected = _Signal()
            self.batchCountChanged = _Signal()
            self.batch_counts: list[int] = []

        def queue_button_target(self) -> object:
            """Return the queue-menu anchor target."""

            return queue_target

        def set_batch_count(self, value: int) -> None:
            """Record synchronized batch-count values."""

            self.batch_counts.append(value)

        def apply_generation_presentation(self, _presentation: object) -> None:
            """Accept presentation updates from the registry."""

            return None

    class _FakeFrame(QWidget):
        """Provide a shell frame with generation titlebar controls enabled."""

        def __init__(self) -> None:
            """Create a frame double with optional controls used by attachment."""

            super().__init__()
            self.menuContainer = None
            self.generationActionCluster = object()
            self.comfyOutputToggleButton = None
            self.startupDiagnosticsButton = None

        def add_body_widget(self, _widget: QWidget) -> None:
            """Accept body attachment."""

            return None

    class _FakeMainWindow(QWidget):
        """Provide shell collaborators consumed by frame attachment."""

        workflow_tabbar = None
        comfy_output_panel_visibility_changed = SimpleNamespace(
            connect=lambda *_args: None
        )

        def __init__(self) -> None:
            """Create callback collaborators and registry capture."""

            super().__init__()
            self.workspace_generation_actions = SimpleNamespace(
                on_generate_clicked=lambda: events.append(("generate", None)),
                on_skip_generation_clicked=lambda: events.append(("skip", None)),
                on_stop_generation_clicked=lambda: events.append(("stop", None)),
            )
            self.generation_queue_controller = SimpleNamespace(
                show_for=lambda target: events.append(("queue", target)),
                show_context_menu_for=lambda target: events.append(
                    ("queue_context", target)
                ),
            )
            self.generation_action_controller = SimpleNamespace(
                set_generation_selected_mode=lambda mode: events.append(("mode", mode))
            )
            self.comfy_runtime_actions = SimpleNamespace(
                set_comfy_output_panel_visible=lambda _visible: None,
                is_comfy_output_panel_visible=lambda: False,
            )
            self.shell_frame_integration_controller = SimpleNamespace(
                set_generation_titlebar_control_registry=registries.append,
                attach_startup_diagnostics_titlebar=(
                    lambda _button, _ignore_repository: None
                ),
            )

    frame = _FakeFrame()
    main_window = _FakeMainWindow()

    composition._attach_main_window_to_shell(
        cast(composition.CustomWindow, frame),
        main_window,
    )
    control = _FakeTitlebarControl()
    cast(Any, registries[0]).register(cast(Any, control))
    control.playClicked.emit()
    control.skipClicked.emit()
    control.stopClicked.emit()
    control.queueClicked.emit()
    control.queueContextMenuRequested.emit()
    control.generateModeSelected.emit("continuous")

    assert events == [
        ("generate", None),
        ("skip", None),
        ("stop", None),
        ("queue", queue_target),
        ("queue_context", queue_target),
        ("mode", "continuous"),
    ]
    assert control.batch_counts == [1]

    _destroy_qt_widgets(frame, main_window)
