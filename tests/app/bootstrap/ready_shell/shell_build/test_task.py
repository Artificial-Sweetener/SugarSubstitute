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

"""Tests for ready-shell startup task orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
)

from ..support.shell_surfaces import _Splash
from ..support.timing import _Timer
from ..support.trace import _patch_trace

PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_build_ready_shell_skeleton_builds_and_wires_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell skeleton building should sequence existing startup ports."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    context = object()
    output_stream = object()
    runtime_services = object()
    ignore_repository = object()
    shell_frame = object()
    restore_preload = object()
    main_window = _MainWindow()

    def shutdown_request(_state: object | None) -> None:
        """Record shutdown requests if invoked."""

        calls.append("shutdown")

    def build_main_window(received_context: object, **kwargs: object) -> object:
        """Record build-main-window inputs and return the shell frame."""

        assert received_context is context
        assert kwargs["comfy_output_stream"] is output_stream
        assert kwargs["shutdown_request"] is shutdown_request
        assert kwargs["runtime_services"] is runtime_services
        assert kwargs["startup_diagnostics_ignore_repository"] is ignore_repository
        calls.append("build_main_window")
        return shell_frame

    result = ready_shell_controller.build_ready_shell_skeleton(
        startup_cancelled=False,
        splash=_Splash(calls),
        context=context,
        comfy_output_stream=output_stream,
        shutdown_request=shutdown_request,
        startup_timer=_Timer(calls),
        runtime_services=runtime_services,
        startup_diagnostics_ignore_repository=ignore_repository,
        build_main_window=build_main_window,
        attach_gui_reload_command=lambda frame: calls.append(
            "attach_reload" if frame is shell_frame else "attach_wrong"
        ),
        set_current_shell=lambda frame: calls.append(
            "set_current" if frame is shell_frame else "set_current_wrong"
        ),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        restore_asset_preload=restore_preload,
        comfy_http_ready=True,
        set_backend_state=lambda state: calls.append(f"backend:{state}"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result is shell_frame
    assert calls == [
        "splash_log:Preparing the application interface.",
        "phase:start:startup.build_main_window",
        "span:start:build_shell_task.build_main_window",
        "build_main_window",
        "span:end:build_shell_task.build_main_window",
        "phase:end:startup.build_main_window",
        "attach_reload",
        "set_current",
        "backend:ready",
    ]
    assert main_window.workspace_restore_image_adapter.preloads == [restore_preload]
    assert events == [
        ("build_shell_task.start", {"route": "ready"}),
        ("build_shell_task.restore_asset_preload.attached", {"route": "ready"}),
        ("build_shell_task.end", {"route": "ready"}),
    ]


def test_build_ready_shell_skeleton_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not build shell collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    result = ready_shell_controller.build_ready_shell_skeleton(
        startup_cancelled=True,
        splash=_Splash(calls),
        context=object(),
        comfy_output_stream=object(),
        shutdown_request=lambda _state: calls.append("shutdown"),
        startup_timer=_Timer(calls),
        runtime_services=object(),
        startup_diagnostics_ignore_repository=object(),
        build_main_window=lambda *_args, **_kwargs: calls.append("build"),
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("set_current"),
        main_window_for_shell=lambda _frame: object(),
        restore_asset_preload=object(),
        comfy_http_ready=False,
        set_backend_state=lambda _state: calls.append("backend"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result is None
    assert calls == []
    assert events == [
        ("build_shell_task.start", {"route": "ready"}),
        ("build_shell_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_build_ready_shell_skeleton_task_records_built_shell_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell build task should store the built shell frame."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    shell_frame = object()
    recorded_frames: list[object] = []

    result = ready_shell_controller.build_ready_shell_skeleton_task(
        startup_cancelled=False,
        splash=_Splash(calls),
        context=object(),
        comfy_output_stream=object(),
        shutdown_request=lambda _state: calls.append("shutdown"),
        startup_timer=_Timer(calls),
        runtime_services=object(),
        startup_diagnostics_ignore_repository=object(),
        build_main_window=lambda *_args, **_kwargs: shell_frame,
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("set_current"),
        main_window_for_shell=lambda _frame: _MainWindow(),
        restore_asset_preload=None,
        comfy_http_ready=False,
        set_backend_state=lambda state: calls.append(f"backend:{state}"),
        set_shell_frame=recorded_frames.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result is shell_frame
    assert recorded_frames == [shell_frame]
    assert calls == [
        "splash_log:Preparing the application interface.",
        "phase:start:startup.build_main_window",
        "span:start:build_shell_task.build_main_window",
        "span:end:build_shell_task.build_main_window",
        "phase:end:startup.build_main_window",
        "attach",
        "set_current",
        "backend:starting",
    ]
    assert events == [
        ("build_shell_task.start", {"route": "ready"}),
        (
            "build_shell_task.restore_asset_preload.skip",
            {"reason": "no_restore_asset_preload", "route": "ready"},
        ),
        ("build_shell_task.end", {"route": "ready"}),
    ]


def test_build_ready_shell_skeleton_task_leaves_state_when_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped ready-shell build task must not mutate shell-frame state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    recorded_frames: list[object] = []

    result = ready_shell_controller.build_ready_shell_skeleton_task(
        startup_cancelled=True,
        splash=_Splash(calls),
        context=object(),
        comfy_output_stream=object(),
        shutdown_request=lambda _state: calls.append("shutdown"),
        startup_timer=_Timer(calls),
        runtime_services=object(),
        startup_diagnostics_ignore_repository=object(),
        build_main_window=lambda *_args, **_kwargs: calls.append("build"),
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("set_current"),
        main_window_for_shell=lambda _frame: object(),
        restore_asset_preload=object(),
        comfy_http_ready=False,
        set_backend_state=lambda _state: calls.append("backend"),
        set_shell_frame=recorded_frames.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result is None
    assert recorded_frames == []
    assert calls == []
    assert events == [
        ("build_shell_task.start", {"route": "ready"}),
        ("build_shell_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_ready_shell_build_task_uses_live_startup_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell build task should read live startup state when it runs."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    shell_frame = object()
    restore_preload = object()
    main_window = _MainWindow()
    cancelled = [True]
    splash_state: list[_Splash | None] = [None]
    restore_preload_state: list[object | None] = [None]
    comfy_http_ready = [False]
    recorded_frames: list[object] = []

    def build_main_window(*_args: object, **_kwargs: object) -> object:
        """Record shell construction and return the shell frame."""

        calls.append("build_main_window")
        return shell_frame

    task = ready_shell_controller.ReadyShellBuildTask(
        startup_cancelled=lambda: cancelled[0],
        splash=lambda: splash_state[0],
        context=object(),
        comfy_output_stream=object(),
        shutdown_request=lambda _state: calls.append("shutdown"),
        startup_timer=_Timer(calls),
        runtime_services=object(),
        startup_diagnostics_ignore_repository=object(),
        build_main_window=build_main_window,
        attach_gui_reload_command=lambda frame: calls.append(
            "attach_reload" if frame is shell_frame else "attach_wrong"
        ),
        set_current_shell=lambda frame: calls.append(
            "set_current" if frame is shell_frame else "set_current_wrong"
        ),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        restore_asset_preload=lambda: restore_preload_state[0],
        comfy_http_ready=lambda: comfy_http_ready[0],
        set_backend_state=lambda state: calls.append(f"backend:{state}"),
        set_shell_frame=recorded_frames.append,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.build()

    assert skipped is None
    assert recorded_frames == []
    assert calls == []

    cancelled[0] = False
    splash_state[0] = _Splash(calls)
    restore_preload_state[0] = restore_preload
    comfy_http_ready[0] = True

    built = task.build()

    assert built is shell_frame
    assert recorded_frames == [shell_frame]
    assert calls == [
        "splash_log:Preparing the application interface.",
        "phase:start:startup.build_main_window",
        "span:start:build_shell_task.build_main_window",
        "build_main_window",
        "span:end:build_shell_task.build_main_window",
        "phase:end:startup.build_main_window",
        "attach_reload",
        "set_current",
        "backend:ready",
    ]
    assert main_window.workspace_restore_image_adapter.preloads == [restore_preload]
    assert events == [
        ("build_shell_task.start", {"route": "ready"}),
        ("build_shell_task.skip", {"reason": "startup_cancelled"}),
        ("build_shell_task.start", {"route": "ready"}),
        ("build_shell_task.restore_asset_preload.attached", {"route": "ready"}),
        ("build_shell_task.end", {"route": "ready"}),
    ]


def test_create_ready_shell_build_task_returns_task() -> None:
    """Ready-shell build task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_build_task(
        startup_cancelled=lambda: False,
        splash=lambda: None,
        context=object(),
        comfy_output_stream=object(),
        shutdown_request=lambda _state: None,
        startup_timer=_Timer([]),
        runtime_services=object(),
        startup_diagnostics_ignore_repository=object(),
        build_main_window=lambda *_args, **_kwargs: object(),
        attach_gui_reload_command=lambda _frame: None,
        set_current_shell=lambda _frame: None,
        main_window_for_shell=lambda _frame: object(),
        restore_asset_preload=lambda: None,
        comfy_http_ready=lambda: False,
        set_backend_state=lambda _state: None,
        set_shell_frame=lambda _frame: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellBuildTask)


class _RestoreImageAdapter:
    """Record restore preload attachments."""

    def __init__(self) -> None:
        """Initialize recorded preloads."""

        self.preloads: list[object] = []

    def set_restore_asset_preload(self, preload: object) -> None:
        """Record one restore preload."""

        self.preloads.append(preload)


class _MainWindow:
    """Expose shell adapters consumed by the ready-shell controller."""

    def __init__(self) -> None:
        """Create shell adapter doubles."""

        self.workspace_restore_image_adapter = _RestoreImageAdapter()
