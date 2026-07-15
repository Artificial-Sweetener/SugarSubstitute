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

import ast
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from substitute.app.bootstrap import (
    pre_show_restore_projection,
    ready_shell_controller,
    ready_shell_restore_controller,
    startup_model_metadata,
    startup_warmup_controller,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.domain.onboarding import InstallationContext

PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


def test_ready_shell_launch_controller_launches_no_comfy_shell() -> None:
    """Ready-shell launch controller should own the no-Comfy route branch."""

    calls: list[str] = []
    context = cast(InstallationContext, _LaunchContext())
    splash = _Splash(calls)
    shell_frame = object()
    current_shells: list[object] = []
    splashes: list[object | None] = []

    def show_main_window(received_context: object, **kwargs: object) -> object:
        """Record the no-Comfy shell show call."""

        assert received_context is context
        assert kwargs["initial_shell_placement"] == "placement"
        assert kwargs["initial_workspace"] == "workspace"
        calls.append("show")
        return shell_frame

    controller = ready_shell_controller.ReadyShellLaunchController(
        no_comfy=True,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: splash,
        set_splash=splashes.append,
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement="placement",
        initial_workspace="workspace",
        show_main_window=show_main_window,
        attach_gui_reload_command=lambda frame: calls.append(
            "attach_reload" if frame is shell_frame else "attach_wrong"
        ),
        set_current_shell=current_shells.append,
        launch_managed_ready_shell=lambda _context: calls.append("managed"),
    )

    controller.launch(context)

    assert calls == ["splash_close", "show", "attach_reload"]
    assert current_shells == [shell_frame]
    assert splashes == [None]


def test_ready_shell_launch_controller_launches_managed_shell_once() -> None:
    """Ready-shell launch controller should route managed startup behind a callback."""

    calls: list[str] = []
    context = cast(InstallationContext, _LaunchContext())

    controller = ready_shell_controller.ReadyShellLaunchController(
        no_comfy=False,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: _Splash(calls),
        set_splash=lambda _splash: calls.append("set_splash"),
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: calls.append("show"),
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("current"),
        launch_managed_ready_shell=lambda received: calls.append(
            "managed" if received is context else "managed_wrong"
        ),
    )

    controller.launch(context)
    controller.launch(context)

    assert calls == ["managed"]


def test_ready_shell_launch_controller_skips_when_gate_blocks() -> None:
    """Ready-shell launch controller should respect duplicate/cancel gate state."""

    calls: list[str] = []

    controller = ready_shell_controller.ReadyShellLaunchController(
        no_comfy=False,
        startup_cancelled=lambda: True,
        shell_frame_present=lambda: False,
        splash=lambda: _Splash(calls),
        set_splash=lambda _splash: calls.append("set_splash"),
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: calls.append("show"),
        attach_gui_reload_command=lambda _frame: calls.append("attach"),
        set_current_shell=lambda _frame: calls.append("current"),
        launch_managed_ready_shell=lambda _context: calls.append("managed"),
    )

    controller.launch(cast(InstallationContext, _LaunchContext()))

    assert calls == []


def test_create_ready_shell_launch_controller_returns_controller() -> None:
    """Ready-shell launch controller factory should construct the controller."""

    controller = ready_shell_controller.create_ready_shell_launch_controller(
        no_comfy=False,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda *_args, **_kwargs: object(),
        attach_gui_reload_command=lambda _frame: None,
        set_current_shell=lambda _frame: None,
        launch_managed_ready_shell=lambda _context: None,
    )

    assert isinstance(controller, ready_shell_controller.ReadyShellLaunchController)


def test_ready_shell_managed_startup_prelude_wires_cancel_and_splash() -> None:
    """Managed startup prelude should own cancel and splash wiring."""

    calls: list[str] = []
    connected_callbacks: list[Callable[[], None]] = []
    initial_cancel_callbacks: list[Callable[[], None]] = []
    splash = object()
    new_splash = object()

    def start_splash(**kwargs: object) -> object:
        """Record launch-splash inputs and return the new splash reference."""

        assert kwargs["splash"] is splash
        assert kwargs["on_cancel_requested"] is emit_splash_cancel
        calls.append("start_splash")
        return new_splash

    def connect_cancel(callback: Callable[[], None]) -> None:
        """Record the startup cancellation handler."""

        connected_callbacks.append(callback)
        calls.append("connect_cancel")

    def initial_connector(callback: Callable[[], None]) -> None:
        """Record the splash cancel callback exposed to an initial splash."""

        initial_cancel_callbacks.append(callback)
        calls.append("initial_connector")

    def request_startup_cancel() -> None:
        """Record forwarded startup cancellation."""

        calls.append("request_cancel")

    def emit_splash_cancel() -> None:
        """Record splash cancel bridge emission."""

        calls.append("emit_cancel")

    splashes: list[object | None] = []
    prelude = ready_shell_controller.ReadyShellManagedStartupPrelude(
        connect_cancel_request=connect_cancel,
        request_startup_cancel=request_startup_cancel,
        initial_splash_cancel_connector=initial_connector,
        emit_splash_cancel=emit_splash_cancel,
        splash=lambda: splash,
        set_splash=splashes.append,
        startup_timer=object(),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=start_splash,
    )

    prelude.run()
    connected_callbacks[0]()
    initial_cancel_callbacks[0]()

    assert calls == [
        "connect_cancel",
        "initial_connector",
        "start_splash",
        "request_cancel",
        "emit_cancel",
    ]
    assert splashes == [new_splash]


def test_create_ready_shell_managed_startup_prelude_returns_prelude() -> None:
    """Managed startup prelude construction should live in its owner."""

    prelude = ready_shell_controller.create_ready_shell_managed_startup_prelude(
        connect_cancel_request=lambda _callback: None,
        request_startup_cancel=lambda: None,
        initial_splash_cancel_connector=None,
        emit_splash_cancel=lambda: None,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        startup_timer=object(),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=lambda **_kwargs: object(),
    )

    assert isinstance(prelude, ready_shell_controller.ReadyShellManagedStartupPrelude)


def test_ready_shell_failure_queue_cancels_owned_queue_on_startup_cancel() -> None:
    """Ready-shell failure queue should bind fail-closed cleanup to queue cancel."""

    calls: list[str] = []
    scheduled: list[Callable[[], None]] = []
    cancelled = False

    def mark_cancelled() -> None:
        """Record startup cancellation."""

        nonlocal cancelled
        cancelled = True

    failure_queue = ready_shell_controller.ReadyShellFailureQueue(
        is_startup_cancelled=lambda: cancelled,
        mark_startup_cancelled=mark_cancelled,
        readiness_timers=lambda: (),
        runtime_compatibility_probes=lambda: (),
        managed_comfy_state=lambda: None,
        splash=lambda: _CloseSplash(calls),
        cleanup=lambda: calls.append("cleanup"),
        quit_app=lambda: calls.append("quit"),
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=lambda _incident: object(),
        present_startup_failure_report=lambda _report: calls.append("present"),
        scheduler=lambda _delay_ms, callback: scheduled.append(callback),
        startup_timer=StartupTimer(),
    )

    failure_queue.add_task("later", lambda: calls.append("task"))
    failure_queue.request_startup_cancel()
    failure_queue.start_queue()

    assert cancelled is True
    assert scheduled == []
    assert calls == ["splash:close", "cleanup", "quit"]


def test_create_ready_shell_failure_queue_returns_failure_queue() -> None:
    """Ready-shell failure queue construction should live in its owner."""

    failure_queue = ready_shell_controller.create_ready_shell_failure_queue(
        is_startup_cancelled=lambda: False,
        mark_startup_cancelled=lambda: None,
        readiness_timers=lambda: (),
        runtime_compatibility_probes=lambda: (),
        managed_comfy_state=lambda: None,
        splash=lambda: None,
        cleanup=lambda: None,
        quit_app=lambda: None,
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=lambda _incident: object(),
        present_startup_failure_report=lambda _report: None,
        scheduler=lambda _delay_ms, _callback: None,
        startup_timer=StartupTimer(),
    )

    assert isinstance(failure_queue, ready_shell_controller.ReadyShellFailureQueue)


def test_schedule_ready_shell_controller_startup_tasks_adapts_task_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell controller should adapt live task objects into queue ordering."""

    calls: list[str] = []
    task_queue = _ControllerTaskQueue()

    def schedule_startup_tasks(
        *,
        queue: object,
        activate_target: Callable[[], None],
        start_readiness_timer: Callable[[], None],
        build_main_window: Callable[[], None],
        wire_metadata_bridge: Callable[[], None],
        warm_prompt_editor_gui: Callable[[], None],
        prehydrate_initial_workspace: Callable[[], None],
        mark_minimum_shell_ready: Callable[[], None],
    ) -> None:
        """Record callbacks produced by the controller-level task adapter."""

        assert queue is task_queue
        for callback in (
            activate_target,
            start_readiness_timer,
            build_main_window,
            wire_metadata_bridge,
            warm_prompt_editor_gui,
            prehydrate_initial_workspace,
            mark_minimum_shell_ready,
        ):
            callback()

    monkeypatch.setattr(
        ready_shell_controller,
        "schedule_ready_shell_startup_tasks",
        schedule_startup_tasks,
    )

    ready_shell_controller.schedule_ready_shell_controller_startup_tasks(
        queue=task_queue,
        target_activation_task=cast(
            ready_shell_controller.ReadyShellTargetActivationTask,
            _Runnable("activate_target", calls),
        ),
        start_readiness_timer=lambda: calls.append("start_readiness_timer"),
        shell_build_task=cast(
            ready_shell_controller.ReadyShellBuildTask,
            _Runnable("build_main_window", calls),
        ),
        metadata_bridge_task=cast(
            ready_shell_controller.ReadyShellMetadataBridgeTask,
            _Runnable("wire_metadata_bridge", calls),
        ),
        prompt_editor_warmup_task=cast(
            ready_shell_controller.ReadyShellPromptEditorWarmupTask,
            _Runnable("warm_prompt_editor_gui", calls),
        ),
        initial_workspace_prehydration_task=cast(
            ready_shell_controller.ReadyShellInitialWorkspacePrehydrationTask,
            _Runnable("prehydrate_initial_workspace", calls),
        ),
        minimum_shell_ready_task=cast(
            ready_shell_controller.ReadyShellMinimumReadyTask,
            _Runnable("mark_minimum_shell_ready", calls),
        ),
    )

    assert calls == [
        "activate_target",
        "start_readiness_timer",
        "build_main_window",
        "wire_metadata_bridge",
        "warm_prompt_editor_gui",
        "prehydrate_initial_workspace",
        "mark_minimum_shell_ready",
    ]


def test_ready_shell_local_editor_warmup_adapter_uses_live_startup_state() -> None:
    """Local editor warmup adapter should own shell-build warmup port assembly."""

    calls: list[str] = []
    state = startup_warmup_controller.StartupWarmupState()
    shell_frame = object()
    main_window = object()
    registry = object()

    def start_local_editor_warmup(**kwargs: object) -> object:
        """Record local editor warmup inputs."""

        assert kwargs["state"] is state
        assert kwargs["startup_cancelled"] is False
        assert kwargs["shell_frame"] is shell_frame
        assert kwargs["main_window_for_shell"] is main_window_for_shell
        assert kwargs["registry"] is registry
        calls.append("local_editor_warmup")
        return "started"

    def main_window_for_shell(received: object) -> object:
        """Return a main window for the built shell frame."""

        assert received is shell_frame
        return main_window

    adapter = ready_shell_controller.ReadyShellLocalEditorWarmupAdapter(
        state=state,
        startup_cancelled=lambda: False,
        main_window_for_shell=main_window_for_shell,
        registry=registry,
        trace_fields=lambda: {"route": "ready"},
        start_local_editor_warmup=start_local_editor_warmup,
    )

    result = adapter.start(shell_frame)

    assert result == "started"
    assert calls == ["local_editor_warmup"]


def test_create_ready_shell_local_editor_warmup_adapter_returns_adapter() -> None:
    """Local editor warmup adapter construction should live in its owner."""

    adapter = ready_shell_controller.create_ready_shell_local_editor_warmup_adapter(
        state=startup_warmup_controller.StartupWarmupState(),
        startup_cancelled=lambda: False,
        main_window_for_shell=lambda _frame: object(),
        registry=object(),
        trace_fields=lambda: {"route": "ready"},
        start_local_editor_warmup=lambda **_kwargs: None,
    )

    assert isinstance(
        adapter,
        ready_shell_controller.ReadyShellLocalEditorWarmupAdapter,
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


def test_activate_ready_shell_target_starts_managed_comfy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell target activation should sequence managed startup ports."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    context = object()
    splash = object()
    output_stream = object()
    diagnostics = object()
    comfy_state = object()

    def activate_target(**kwargs: object) -> object:
        """Record activation inputs and return a managed Comfy state."""

        assert kwargs["installation_context"] is context
        assert kwargs["splash"] is splash
        assert kwargs["comfy_output_stream"] is output_stream
        assert kwargs["startup_diagnostics"] is diagnostics
        calls.append("activate_target")
        return comfy_state

    result = ready_shell_controller.activate_ready_shell_target(
        startup_cancelled=False,
        splash=splash,
        installation_context=context,
        comfy_output_stream=output_stream,
        startup_diagnostics=diagnostics,
        startup_timer=_Timer(calls),
        activate_target=activate_target,
        mark_activation_started=lambda: calls.append("mark_started"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is True
    assert result.comfy_state is comfy_state
    assert calls == [
        "mark_started",
        "phase:start:startup.activate_target",
        "span:start:activate_target_task.activate",
        "activate_target",
        "span:end:activate_target_task.activate",
        "phase:end:startup.activate_target",
    ]
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        (
            "activate_target_task.end",
            {"comfy_state_present": True, "route": "ready"},
        ),
    ]


def test_activate_ready_shell_target_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not activate managed Comfy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    result = ready_shell_controller.activate_ready_shell_target(
        startup_cancelled=True,
        splash=object(),
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: calls.append("activate"),
        mark_activation_started=lambda: calls.append("mark_started"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is False
    assert result.comfy_state is None
    assert calls == []
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_activate_ready_shell_target_task_records_started_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell activation task should store produced managed Comfy state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    comfy_state = object()
    state = _ActivationState()
    recorded_states: list[object | None] = []

    result = ready_shell_controller.activate_ready_shell_target_task(
        startup_cancelled=False,
        splash=object(),
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: comfy_state,
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is True
    assert result.comfy_state is comfy_state
    assert state.comfy_activation_started is True
    assert recorded_states == [comfy_state]
    assert calls == [
        "phase:start:startup.activate_target",
        "span:start:activate_target_task.activate",
        "span:end:activate_target_task.activate",
        "phase:end:startup.activate_target",
    ]
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        (
            "activate_target_task.end",
            {"comfy_state_present": True, "route": "ready"},
        ),
    ]


def test_activate_ready_shell_target_task_leaves_state_when_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped ready-shell activation must not mutate managed Comfy state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _ActivationState()
    recorded_states: list[object | None] = []

    result = ready_shell_controller.activate_ready_shell_target_task(
        startup_cancelled=True,
        splash=object(),
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: calls.append("activate"),
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is False
    assert result.comfy_state is None
    assert state.comfy_activation_started is False
    assert recorded_states == []
    assert calls == []
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_activate_ready_shell_target_task_skips_when_already_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prestarted managed activation should not launch Comfy a second time."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _ActivationState(comfy_activation_started=True)
    recorded_states: list[object | None] = []

    result = ready_shell_controller.activate_ready_shell_target_task(
        startup_cancelled=False,
        splash=None,
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer(calls),
        activate_target=lambda **_kwargs: calls.append("activate"),
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.started is False
    assert result.comfy_state is None
    assert state.comfy_activation_started is True
    assert recorded_states == []
    assert calls == []
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "already_started"}),
    ]


def test_target_activation_task_uses_live_startup_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target activation task should read cancellation and splash state on run."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    context = object()
    output_stream = object()
    diagnostics = object()
    splash = object()
    splash_state: list[object | None] = [None]
    cancelled = [True]
    comfy_state = object()
    state = _ActivationState()
    recorded_states: list[object | None] = []

    def activate_target(**kwargs: object) -> object:
        """Record activation inputs and return a managed Comfy state."""

        assert kwargs["installation_context"] is context
        assert kwargs["splash"] is splash
        assert kwargs["comfy_output_stream"] is output_stream
        assert kwargs["startup_diagnostics"] is diagnostics
        calls.append("activate")
        return comfy_state

    task = ready_shell_controller.ReadyShellTargetActivationTask(
        startup_cancelled=lambda: cancelled[0],
        splash=lambda: splash_state[0],
        installation_context=context,
        comfy_output_stream=output_stream,
        startup_diagnostics=diagnostics,
        startup_timer=_Timer(calls),
        activate_target=activate_target,
        state=state,
        set_comfy_state=recorded_states.append,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.activate()

    assert skipped.started is False
    assert state.comfy_activation_started is False
    assert recorded_states == []
    assert calls == []

    cancelled[0] = False
    splash_state[0] = splash

    activated = task.activate()

    assert activated.started is True
    assert activated.comfy_state is comfy_state
    assert state.comfy_activation_started is True
    assert recorded_states == [comfy_state]
    assert calls == [
        "phase:start:startup.activate_target",
        "span:start:activate_target_task.activate",
        "activate",
        "span:end:activate_target_task.activate",
        "phase:end:startup.activate_target",
    ]
    assert events == [
        ("activate_target_task.start", {"route": "ready"}),
        ("activate_target_task.skip", {"reason": "startup_cancelled"}),
        ("activate_target_task.start", {"route": "ready"}),
        (
            "activate_target_task.end",
            {"comfy_state_present": True, "route": "ready"},
        ),
    ]


def test_create_ready_shell_target_activation_task_returns_task() -> None:
    """Target activation task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_target_activation_task(
        startup_cancelled=lambda: False,
        splash=lambda: None,
        installation_context=object(),
        comfy_output_stream=object(),
        startup_diagnostics=object(),
        startup_timer=_Timer([]),
        activate_target=lambda **_kwargs: None,
        state=_ActivationState(),
        set_comfy_state=lambda _state: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellTargetActivationTask)


def test_wire_ready_shell_metadata_bridge_delegates_to_metadata_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell metadata task should delegate bridge wiring to its owner."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    shell_frame = object()
    bridge = _SignalBridge()
    registered: list[object] = []
    main_window = _MetadataMainWindow(_MetadataSurfaceRefreshController())

    def bridge_factory(parent: object) -> ModelMetadataUpdateSignalBridgeProtocol:
        """Return the bridge for the expected shell frame."""

        assert parent is shell_frame
        return cast(ModelMetadataUpdateSignalBridgeProtocol, bridge)

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge(
        startup_cancelled=False,
        shell_frame=shell_frame,
        bridge_factory=bridge_factory,
        register_bridge=registered.append,
        main_window_for_shell=lambda parent: (
            main_window if parent is shell_frame else object()
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert cast(object, wired) is bridge
    assert registered == [bridge]
    assert bridge.model_updated.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_wire_ready_shell_metadata_bridge_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not construct metadata bridge collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge(
        startup_cancelled=True,
        shell_frame=object(),
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda _bridge: calls.append("register"),
        main_window_for_shell=lambda _parent: calls.append("main_window"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert wired is None
    assert calls == []
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_wire_ready_shell_metadata_bridge_task_records_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell metadata task should store the wired metadata bridge."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    shell_frame = object()
    bridge = _SignalBridge()
    registered: list[object] = []
    recorded_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []
    main_window = _MetadataMainWindow(_MetadataSurfaceRefreshController())

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge_task(
        startup_cancelled=False,
        shell_frame=shell_frame,
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            bridge,
        ),
        register_bridge=registered.append,
        main_window_for_shell=lambda _parent: main_window,
        set_metadata_update_bridge=recorded_bridges.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert cast(object, wired) is bridge
    assert len(recorded_bridges) == 1
    assert cast(object, recorded_bridges[0]) is bridge
    assert registered == [bridge]
    assert bridge.model_updated.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_wire_ready_shell_metadata_bridge_task_records_skip_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped ready-shell metadata task should store the skipped bridge result."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    recorded_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []

    wired = ready_shell_controller.wire_ready_shell_metadata_bridge_task(
        startup_cancelled=True,
        shell_frame=object(),
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda _bridge: calls.append("register"),
        main_window_for_shell=lambda _parent: calls.append("main_window"),
        set_metadata_update_bridge=recorded_bridges.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert wired is None
    assert recorded_bridges == [None]
    assert calls == []
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "startup_cancelled"}),
    ]


def test_metadata_bridge_task_uses_live_shell_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata bridge task should read shell state when it runs."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    shell_frame = object()
    shell_state: list[object | None] = [None]
    bridge = _SignalBridge()
    registered: list[object] = []
    recorded_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []
    main_window = _MetadataMainWindow(_MetadataSurfaceRefreshController())

    task = ready_shell_controller.ReadyShellMetadataBridgeTask(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_state[0],
        bridge_factory=lambda parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            bridge if parent is shell_frame else _SignalBridge(),
        ),
        register_bridge=registered.append,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        set_metadata_update_bridge=recorded_bridges.append,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.wire()

    assert skipped is None
    assert recorded_bridges == [None]
    assert registered == []

    shell_state[0] = shell_frame

    wired = task.wire()

    assert cast(object, wired) is bridge
    assert cast(object, recorded_bridges[1]) is bridge
    assert registered == [bridge]
    assert bridge.model_updated.callbacks == [
        main_window.model_metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert events == [
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.skip", {"reason": "no_shell_frame"}),
        ("wire_metadata_bridge_task.start", {"route": "ready"}),
        ("wire_metadata_bridge_task.end", {"connected": True, "route": "ready"}),
    ]


def test_create_ready_shell_metadata_bridge_task_returns_task() -> None:
    """Metadata bridge task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_metadata_bridge_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        bridge_factory=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            _SignalBridge(),
        ),
        register_bridge=lambda bridge: bridge,
        main_window_for_shell=lambda _frame: object(),
        set_metadata_update_bridge=lambda _bridge: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellMetadataBridgeTask)


def test_mark_ready_shell_minimum_ready_task_delegates_gate_and_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell minimum-ready task should update state and reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()

    marked = ready_shell_controller.mark_ready_shell_minimum_ready_task(
        startup_cancelled=False,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert marked is True
    assert state.minimum_shell_ready is True
    assert calls == ["try_show"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_mark_ready_shell_minimum_ready_task_runs_after_mark_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell minimum-ready task should run follow-up work after reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()

    marked = ready_shell_controller.mark_ready_shell_minimum_ready_task(
        startup_cancelled=False,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
        after_mark_ready=lambda: calls.append("after_mark"),
    )

    assert marked is True
    assert state.minimum_shell_ready is True
    assert calls == ["try_show", "after_mark"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_mark_ready_shell_minimum_ready_task_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not mark the minimum shell gate."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()

    marked = ready_shell_controller.mark_ready_shell_minimum_ready_task(
        startup_cancelled=True,
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert marked is False
    assert state.minimum_shell_ready is False
    assert calls == []
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        (
            "mark_minimum_shell_ready_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_minimum_ready_task_uses_live_cancellation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Minimum-ready task should read cancellation state when it runs."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _MinimumReadyState()
    cancelled = [True]
    task = ready_shell_controller.ReadyShellMinimumReadyTask(
        startup_cancelled=lambda: cancelled[0],
        state=state,
        try_show_main_window=lambda: calls.append("try_show"),
        trace_fields=lambda: {"route": "ready"},
    )

    skipped = task.mark_ready()

    assert skipped is False
    assert state.minimum_shell_ready is False
    assert calls == []

    cancelled[0] = False

    marked = task.mark_ready()

    assert marked is True
    assert state.minimum_shell_ready is True
    assert calls == ["try_show"]
    assert events == [
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        (
            "mark_minimum_shell_ready_task.skip",
            {"reason": "startup_cancelled"},
        ),
        ("mark_minimum_shell_ready_task.start", {"route": "ready"}),
        ("mark_minimum_shell_ready_task.end", {"route": "ready"}),
    ]


def test_create_ready_shell_minimum_ready_task_returns_task() -> None:
    """Minimum-ready task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_minimum_ready_task(
        startup_cancelled=lambda: False,
        state=_MinimumReadyState(),
        try_show_main_window=lambda: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellMinimumReadyTask)


def test_warm_ready_shell_prompt_editor_gui_delegates_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell prompt editor warmup task should delegate warmup policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    main_window = object()

    warmed = ready_shell_controller.warm_ready_shell_prompt_editor_gui(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        warm_prompt_editor_gui=lambda window: calls.append(
            "warm" if window is main_window else "wrong_window"
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is True
    assert calls == [
        "span:start:warm_prompt_editor_gui_task.run",
        "warm",
        "span:end:warm_prompt_editor_gui_task.run",
    ]
    assert events == [
        ("warm_prompt_editor_gui_task.start", {"route": "ready"}),
        ("warm_prompt_editor_gui_task.end", {"route": "ready"}),
    ]


def test_warm_ready_shell_prompt_editor_gui_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not warm prompt editor GUI collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)

    warmed = ready_shell_controller.warm_ready_shell_prompt_editor_gui(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        warm_prompt_editor_gui=lambda _window: calls.append("warm"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is False
    assert calls == []
    assert events == [
        ("warm_prompt_editor_gui_task.start", {"route": "ready"}),
        (
            "warm_prompt_editor_gui_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_prompt_editor_warmup_task_uses_live_shell_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prompt editor warmup task should read current startup state per run."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    main_window = object()
    shell_state: list[object | None] = [None]
    task = ready_shell_controller.ReadyShellPromptEditorWarmupTask(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_state[0],
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else None
        ),
        warm_prompt_editor_gui=lambda window: calls.append(
            "warm" if window is main_window else "wrong_window"
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert task.warm() is False

    shell_state[0] = shell_frame

    assert task.warm() is True
    assert calls == [
        "span:start:warm_prompt_editor_gui_task.run",
        "warm",
        "span:end:warm_prompt_editor_gui_task.run",
    ]
    assert events[0] == ("warm_prompt_editor_gui_task.start", {"route": "ready"})
    assert events[1] == (
        "warm_prompt_editor_gui_task.skip",
        {"reason": "no_shell_frame"},
    )
    assert events[-1] == ("warm_prompt_editor_gui_task.end", {"route": "ready"})


def test_create_ready_shell_prompt_editor_warmup_task_returns_task() -> None:
    """Prompt editor warmup task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_prompt_editor_warmup_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: object(),
        warm_prompt_editor_gui=lambda _window: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellPromptEditorWarmupTask)


def test_prehydrate_ready_shell_initial_workspace_delegates_prehydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell prehydration task should delegate restore policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _PrehydrationMainWindow(calls)

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda value: 3 if value is workspace else 0,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is True
    assert result.succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        "span:start:prehydrate_initial_workspace_task.prehydrate",
        f"prehydrate:{id(workspace)}",
        "span:end:prehydrate_initial_workspace_task.prehydrate",
        "phase:end:startup.prehydrate_initial_workspace",
    ]
    assert events == [
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        ("prehydrate_initial_workspace_task.end", {"route": "ready"}),
    ]


def test_prehydrate_ready_shell_initial_workspace_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not prehydrate workspace collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=object(),
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda _workspace: 0,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is False
    assert result.succeeded is False
    assert calls == []
    assert events == [
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        (
            "prehydrate_initial_workspace_task.skip",
            {"reason": "startup_cancelled"},
        ),
    ]


def test_prehydrate_ready_shell_initial_workspace_task_records_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell prehydration task should record attempted and succeeded gates."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _PrehydrationMainWindow(calls)
    state = _PrehydrationState()

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace_task(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda value: 1 if value is workspace else 0,
        state=state,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is True
    assert result.succeeded is True
    assert state.prehydration_attempted is True
    assert state.prehydration_succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        "span:start:prehydrate_initial_workspace_task.prehydrate",
        f"prehydrate:{id(workspace)}",
        "span:end:prehydrate_initial_workspace_task.prehydrate",
        "phase:end:startup.prehydrate_initial_workspace",
    ]


def test_prehydrate_ready_shell_initial_workspace_task_leaves_state_when_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipped prehydration should not mutate ready-shell gate state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _PrehydrationState()

    result = ready_shell_controller.prehydrate_ready_shell_initial_workspace_task(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=object(),
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda _workspace: 0,
        state=state,
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.attempted is False
    assert result.succeeded is False
    assert state.prehydration_attempted is False
    assert state.prehydration_succeeded is False
    assert calls == []


def test_initial_workspace_prehydration_task_uses_live_shell_and_workspace_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initial workspace prehydration task should read live shell/workspace state."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    state = _PrehydrationState()
    shell_frame = object()
    shell_state: list[object | None] = [None]
    workspace = object()
    workspace_state: list[object | None] = [workspace]
    main_window = _PrehydrationMainWindow(calls)

    task = ready_shell_controller.ReadyShellInitialWorkspacePrehydrationTask(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_state[0],
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=lambda: workspace_state[0],
        startup_timer=_Timer(calls),
        workspace_workflow_count=lambda value: 2 if value is workspace else 0,
        state=state,
        trace_fields=lambda: {"route": "ready"},
    )

    skipped_result = task.prehydrate()

    assert skipped_result.attempted is False
    assert skipped_result.succeeded is False
    assert state.prehydration_attempted is False
    assert state.prehydration_succeeded is False
    assert calls == []

    shell_state[0] = shell_frame
    workspace_state[0] = object()

    completed_result = task.prehydrate()

    assert completed_result.attempted is True
    assert completed_result.succeeded is True
    assert state.prehydration_attempted is True
    assert state.prehydration_succeeded is True
    assert calls == [
        "phase:start:startup.prehydrate_initial_workspace",
        "span:start:prehydrate_initial_workspace_task.prehydrate",
        f"prehydrate:{id(workspace_state[0])}",
        "span:end:prehydrate_initial_workspace_task.prehydrate",
        "phase:end:startup.prehydrate_initial_workspace",
    ]
    assert events == [
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        (
            "prehydrate_initial_workspace_task.skip",
            {"reason": "no_shell_frame"},
        ),
        ("prehydrate_initial_workspace_task.start", {"route": "ready"}),
        ("prehydrate_initial_workspace_task.end", {"route": "ready"}),
    ]


def test_create_ready_shell_initial_workspace_prehydration_task_returns_task() -> None:
    """Initial workspace prehydration task construction should live in its owner."""

    task = (
        ready_shell_controller.create_ready_shell_initial_workspace_prehydration_task(
            startup_cancelled=lambda: False,
            shell_frame=lambda: None,
            main_window_for_shell=lambda _frame: object(),
            workspace=lambda: None,
            startup_timer=_Timer([]),
            workspace_workflow_count=lambda _workspace: 0,
            state=_PrehydrationState(),
            trace_fields=lambda: {"route": "ready"},
        )
    )

    assert isinstance(
        task,
        ready_shell_controller.ReadyShellInitialWorkspacePrehydrationTask,
    )


def test_project_ready_shell_backend_state_delegates_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell backend-state helper should delegate projection policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    main_window = _BackendStateMainWindow()
    shell_frame = object()

    updated = ready_shell_controller.project_ready_shell_backend_state(
        state="ready",
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is True
    assert main_window.generation_action_controller.states == ["ready"]
    assert events == [
        ("shell_backend_state.update", {"state": "ready", "route": "ready"}),
    ]


def test_project_ready_shell_backend_state_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not inspect backend-state collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    updated = ready_shell_controller.project_ready_shell_backend_state(
        state="ready",
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert updated is False
    assert calls == []
    assert events == []


def test_request_ready_shell_startup_diagnostics_update_delegates_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell diagnostics helper should delegate and trace the request."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    requested: list[dict[str, object]] = []
    main_window = object()
    incident = object()
    ignore_repository = object()
    installation_context = object()
    startup_resources = object()
    execution_runtime = object()

    def execution_dispatcher_factory() -> object:
        """Return a diagnostics dispatcher test double."""

        return object()

    def startup_cancelled() -> bool:
        """Report startup cancellation state."""

        return False

    def shell_frame_available() -> bool:
        """Report shell frame availability state."""

        return True

    def request_update(**kwargs: object) -> bool:
        """Record the delegated diagnostics request."""

        requested.append(kwargs)
        return True

    started = ready_shell_controller.request_ready_shell_startup_diagnostics_update(
        main_window=main_window,
        incidents=(incident,),
        transcript=("line",),
        ignore_repository=ignore_repository,
        installation_context=installation_context,
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
        request_update=request_update,
        trace_fields=lambda: {"route": "ready"},
    )

    assert started is True
    assert requested == [
        {
            "main_window": main_window,
            "incidents": (incident,),
            "transcript": ("line",),
            "ignore_repository": ignore_repository,
            "installation_context": installation_context,
            "startup_resources": startup_resources,
            "execution_runtime": execution_runtime,
            "execution_dispatcher_factory": execution_dispatcher_factory,
            "startup_cancelled": startup_cancelled,
            "shell_frame_available": shell_frame_available,
        }
    ]
    assert events == [("post_show.diagnostics.async_requested", {"route": "ready"})]


def test_ready_shell_startup_diagnostics_update_adapter_uses_live_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostics update adapter should own reveal request port assembly."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    requested: list[dict[str, object]] = []
    main_window = object()
    incident = object()
    ignore_repository = object()
    installation_context = object()
    startup_resources = object()
    execution_runtime = object()

    def execution_dispatcher_factory() -> object:
        """Return a diagnostics dispatcher test double."""

        return object()

    def request_update(**kwargs: object) -> bool:
        """Record the delegated diagnostics request."""

        requested.append(kwargs)
        return True

    def startup_cancelled() -> bool:
        """Report startup cancellation state."""

        return False

    def shell_frame_available() -> bool:
        """Report shell frame availability state."""

        return True

    adapter = ready_shell_controller.ReadyShellStartupDiagnosticsUpdateAdapter(
        incidents=lambda: (incident,),
        transcript=lambda: ("line",),
        ignore_repository=ignore_repository,
        installation_context=installation_context,
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
        startup_cancelled=startup_cancelled,
        shell_frame_available=shell_frame_available,
        request_update=request_update,
        trace_fields=lambda: {"route": "ready"},
    )

    started = adapter.request(main_window)

    assert started is True
    assert requested == [
        {
            "main_window": main_window,
            "incidents": (incident,),
            "transcript": ("line",),
            "ignore_repository": ignore_repository,
            "installation_context": installation_context,
            "startup_resources": startup_resources,
            "execution_runtime": execution_runtime,
            "execution_dispatcher_factory": execution_dispatcher_factory,
            "startup_cancelled": startup_cancelled,
            "shell_frame_available": shell_frame_available,
        }
    ]
    assert events == [("post_show.diagnostics.async_requested", {"route": "ready"})]


def test_create_ready_shell_startup_diagnostics_update_adapter_returns_adapter() -> (
    None
):
    """Ready-shell diagnostics adapter construction should live in its owner."""

    adapter = (
        ready_shell_controller.create_ready_shell_startup_diagnostics_update_adapter(
            incidents=lambda: (),
            transcript=lambda: (),
            ignore_repository=object(),
            installation_context=object(),
            startup_resources=object(),
            execution_runtime=object(),
            execution_dispatcher_factory=lambda: object(),
            startup_cancelled=lambda: False,
            shell_frame_available=lambda: True,
            request_update=lambda **_kwargs: True,
            trace_fields=lambda: {},
        )
    )

    assert isinstance(
        adapter,
        ready_shell_controller.ReadyShellStartupDiagnosticsUpdateAdapter,
    )


def test_reveal_ready_shell_main_window_sequences_post_show_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell reveal should close splash, show shell, and fan out post-show work."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    logs: list[dict[str, object]] = []
    monkeypatch.setattr(
        ready_shell_controller,
        "log_info",
        lambda _logger, message, **fields: logs.append({"message": message, **fields}),
    )
    shell_frame = object()
    shown_shell_frame = object()
    placement = object()

    def show_built_main_window(frame: object, **kwargs: object) -> object:
        """Record show-main-window arguments and return the visible shell frame."""

        assert frame is shell_frame
        assert kwargs["initial_shell_placement"] is placement
        calls.append("show")
        return shown_shell_frame

    result = ready_shell_controller.reveal_ready_shell_main_window(
        splash=_CloseSplash(calls),
        shell_frame=shell_frame,
        initial_shell_placement=placement,
        comfy_http_ready=True,
        startup_timer=_Timer(calls),
        show_built_main_window=show_built_main_window,
        set_current_shell=lambda frame: calls.append(
            "set_current" if frame is shown_shell_frame else "set_current_wrong"
        ),
        update_backend_state=lambda state: calls.append(f"backend:{state}"),
        connect_restore_finalized_warmups=lambda: calls.append("connect_warmups"),
        request_startup_diagnostics_update=lambda: calls.append("diagnostics"),
        schedule_post_show_hydration=lambda: calls.append("schedule_hydration"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.shell_frame is shown_shell_frame
    assert result.splash is None
    assert calls == [
        "phase:start:startup.close_launch_splash",
        "span:start:launch_splash.close",
        "splash:close",
        "span:end:launch_splash.close",
        "phase:end:startup.close_launch_splash",
        "mark:splash_closed",
        "phase:start:startup.show_main_window",
        "span:start:main_shell.show",
        "show",
        "span:end:main_shell.show",
        "phase:end:startup.show_main_window",
        "set_current",
        "mark:main_shell_shown",
        "backend:ready",
        "connect_warmups",
        "diagnostics",
        "schedule_hydration",
    ]
    assert events == [
        ("launch_splash.closed", {"route": "ready"}),
        ("main_shell.shown", {"route": "ready"}),
    ]
    assert logs == [
        {
            "message": "Main shell revealed",
            "comfy_http_ready": True,
        }
    ]


def test_reveal_ready_shell_main_window_tolerates_splash_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash close failures should be logged without blocking shell reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    exceptions: list[str] = []
    monkeypatch.setattr(
        ready_shell_controller,
        "log_exception",
        lambda _logger, message, **_fields: exceptions.append(message),
    )
    monkeypatch.setattr(
        ready_shell_controller,
        "log_info",
        lambda _logger, _message, **_fields: None,
    )
    shell_frame = object()
    shown_shell_frame = object()
    splash = _CloseSplash(calls, fail=True)

    result = ready_shell_controller.reveal_ready_shell_main_window(
        splash=splash,
        shell_frame=shell_frame,
        initial_shell_placement=None,
        comfy_http_ready=False,
        startup_timer=_Timer(calls),
        show_built_main_window=lambda _frame, **_kwargs: shown_shell_frame,
        set_current_shell=lambda _frame: calls.append("set_current"),
        update_backend_state=lambda state: calls.append(f"backend:{state}"),
        connect_restore_finalized_warmups=lambda: calls.append("connect_warmups"),
        request_startup_diagnostics_update=lambda: calls.append("diagnostics"),
        schedule_post_show_hydration=lambda: calls.append("schedule_hydration"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result.shell_frame is shown_shell_frame
    assert result.splash is splash
    assert "Failed to close splash after readiness check" in exceptions
    assert calls == [
        "phase:start:startup.close_launch_splash",
        "span:start:launch_splash.close",
        "splash:close",
        "phase:start:startup.show_main_window",
        "span:start:main_shell.show",
        "span:end:main_shell.show",
        "phase:end:startup.show_main_window",
        "set_current",
        "mark:main_shell_shown",
        "backend:starting",
        "connect_warmups",
        "diagnostics",
        "schedule_hydration",
    ]
    assert events == [
        ("main_shell.shown", {"route": "ready"}),
    ]


def test_ready_shell_reveal_task_uses_live_shell_and_splash_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell reveal task should update live shell and splash references."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    monkeypatch.setattr(
        ready_shell_controller,
        "log_info",
        lambda _logger, _message, **_fields: None,
    )
    shell_frame = object()
    shown_shell_frame = object()
    main_window = _RestoreFinalizedMainWindow(_Signal())
    placement = object()
    splash_state: list[_CloseSplash | None] = [_CloseSplash(calls)]
    shell_state: list[object | None] = [shell_frame]
    recorded_shell_frames: list[object] = []

    def set_shell_frame(frame: object) -> None:
        """Record and update the current shell frame."""

        recorded_shell_frames.append(frame)
        shell_state[0] = frame

    def set_splash(splash: object | None) -> None:
        """Update the current splash reference."""

        splash_state[0] = cast(_CloseSplash | None, splash)

    def show_built_main_window(frame: object, **kwargs: object) -> object:
        """Record shell reveal arguments and return the shown shell frame."""

        calls.append(
            "show"
            if frame is shell_frame and kwargs["initial_shell_placement"] is placement
            else "show_wrong"
        )
        return shown_shell_frame

    task = ready_shell_controller.ReadyShellRevealTask(
        splash=lambda: splash_state[0],
        shell_frame=lambda: shell_state[0],
        initial_shell_placement=lambda: placement,
        comfy_http_ready=lambda: True,
        startup_timer=_Timer(calls),
        show_built_main_window=show_built_main_window,
        set_current_shell=lambda frame: calls.append(
            "set_current" if frame is shown_shell_frame else "set_current_wrong"
        ),
        update_backend_state=lambda state: calls.append(f"backend:{state}"),
        startup_warmup_state=startup_warmup_controller.StartupWarmupState(),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        request_startup_diagnostics_update=lambda window: calls.append(
            "diagnostics" if window is main_window else "diagnostics_wrong"
        ),
        schedule_post_show_hydration=lambda: calls.append("schedule_hydration"),
        set_shell_frame=set_shell_frame,
        set_splash=set_splash,
        trace_fields=lambda: {"route": "ready"},
    )

    result = task.reveal(main_window)

    assert result.shell_frame is shown_shell_frame
    assert result.splash is None
    assert shell_state == [shown_shell_frame]
    assert splash_state == [None]
    assert recorded_shell_frames == [shown_shell_frame]
    assert calls == [
        "phase:start:startup.close_launch_splash",
        "span:start:launch_splash.close",
        "splash:close",
        "span:end:launch_splash.close",
        "phase:end:startup.close_launch_splash",
        "mark:splash_closed",
        "phase:start:startup.show_main_window",
        "span:start:main_shell.show",
        "show",
        "span:end:main_shell.show",
        "phase:end:startup.show_main_window",
        "set_current",
        "mark:main_shell_shown",
        "backend:ready",
        "diagnostics",
        "schedule_hydration",
    ]
    callback = cast(Callable[[], None], main_window.restore_finalized.callbacks[0])
    callback()
    assert calls[-1] == "warmups:restore_finalized"
    assert events == [
        ("launch_splash.closed", {"route": "ready"}),
        ("main_shell.shown", {"route": "ready"}),
        (
            "post_comfy.nonessential_warmups.wait_restore_finalized",
            {"route": "ready"},
        ),
        (
            "post_comfy.nonessential_warmups.restore_finalized",
            {"route": "ready"},
        ),
    ]


def test_create_ready_shell_reveal_task_returns_task() -> None:
    """Reveal task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_reveal_task(
        splash=lambda: None,
        shell_frame=lambda: object(),
        initial_shell_placement=lambda: None,
        comfy_http_ready=lambda: False,
        startup_timer=_Timer([]),
        show_built_main_window=lambda frame, **_kwargs: frame,
        set_current_shell=lambda _frame: None,
        update_backend_state=lambda _state: None,
        startup_warmup_state=startup_warmup_controller.StartupWarmupState(),
        schedule_warmups=lambda _reason: None,
        request_startup_diagnostics_update=lambda _window: None,
        schedule_post_show_hydration=lambda: None,
        set_shell_frame=lambda _frame: None,
        set_splash=lambda _splash: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellRevealTask)


def test_connect_ready_shell_restore_finalized_warmups_delegates_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell restore-finalized helper should delegate warmup wiring."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    state = startup_warmup_controller.StartupWarmupState()
    signal = _Signal()
    scheduled_reasons: list[str] = []

    ready_shell_controller.connect_ready_shell_restore_finalized_warmups(
        state=state,
        main_window=_RestoreFinalizedMainWindow(signal),
        schedule_warmups=scheduled_reasons.append,
        trace_fields=lambda: {"route": "ready"},
    )

    assert state.restore_finalized_warmups_connected is True
    assert signal.callbacks == [state.restore_finalized_warmups_callback]
    callback = cast(Callable[[], None], signal.callbacks[0])
    callback()
    assert scheduled_reasons == ["restore_finalized"]
    assert events == [
        (
            "post_comfy.nonessential_warmups.wait_restore_finalized",
            {"route": "ready"},
        ),
        (
            "post_comfy.nonessential_warmups.restore_finalized",
            {"route": "ready"},
        ),
    ]


def test_schedule_ready_shell_post_show_hydration_delegates_queueing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell post-show scheduling should delegate queue policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    scheduled = ready_shell_controller.schedule_ready_shell_post_show_hydration(
        startup_cancelled=False,
        hydration_started=False,
        mark_hydration_started=lambda: calls.append("mark_started"),
        queue_hydration_task=lambda: calls.append("queue_hydration"),
        start_queue=lambda: calls.append("start_queue"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert scheduled is True
    assert calls == ["mark_started", "queue_hydration", "start_queue"]
    assert events == [
        ("post_show.hydration.queued", {"route": "ready"}),
    ]


def test_schedule_ready_shell_post_show_hydration_skips_when_already_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell post-show scheduling should avoid duplicate hydration."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    scheduled = ready_shell_controller.schedule_ready_shell_post_show_hydration(
        startup_cancelled=False,
        hydration_started=True,
        mark_hydration_started=lambda: calls.append("mark_started"),
        queue_hydration_task=lambda: calls.append("queue_hydration"),
        start_queue=lambda: calls.append("start_queue"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert scheduled is False
    assert calls == []
    assert events == [
        ("post_show.hydration.skip", {"reason": "already_started"}),
    ]


def test_hydrate_ready_shell_initial_workspace_delegates_hydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell hydration task should delegate post-show hydration policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _HydrationMainWindow(calls)

    ready_shell_controller.hydrate_ready_shell_initial_workspace(
        startup_cancelled=False,
        shell_frame=shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        hidden_restore_runtime_prepared=False,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == [
        "mark:hydration_started",
        "span:start:post_show.hydration.full_hydrate",
        f"hydrate:{id(workspace)}",
        "span:end:post_show.hydration.full_hydrate",
        "mark:hydration_completed",
        "warmups:fallback_after_hydration",
        "summary",
    ]
    assert events[0] == ("post_show.hydration.start", {"route": "ready"})
    assert events[-1] == ("post_show.visible_startup_summary", {"delay_ms": 0})


def test_hydrate_ready_shell_initial_workspace_skips_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled startup should not inspect hydration collaborators."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)

    ready_shell_controller.hydrate_ready_shell_initial_workspace(
        startup_cancelled=True,
        shell_frame=object(),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=None,
        hidden_restore_runtime_prepared=False,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=lambda: calls.append("summary"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert calls == []
    assert events == [
        ("post_show.hydration.skip", {"reason": "startup_cancelled"}),
    ]


def test_emit_ready_shell_visible_startup_summary_delegates_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell visible summary task should delegate summary policy."""

    events: list[tuple[str, dict[str, object]]] = []
    logs: list[dict[str, object]] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_info",
        lambda _logger, message, **fields: logs.append({"message": message, **fields}),
    )
    timer = _marked_timer()

    ready_shell_controller.emit_ready_shell_visible_startup_summary(
        startup_timer=timer,
        workspace=None,
        trace_fields=lambda: {"route": "ready"},
    )

    summary_fields = {
        "session_restore_used": False,
        "workflow_count": 0,
        "active_cube_count": 0,
        "splash_close_to_shell_show_ms": "50.000",
        "splash_close_to_hydration_complete_ms": "150.000",
        "splash_close_to_restore_running_ms": "200.000",
    }
    assert logs == [
        {
            "message": "Startup visible loading summary",
            **summary_fields,
        }
    ]
    assert events == [
        (
            "startup.visible_loading.summary",
            {**summary_fields, "route": "ready"},
        )
    ]


def test_ready_shell_post_show_controller_projects_queues_and_hydrates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-show controller should own backend projection and hydration queue glue."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _PostShowMainWindow(calls)
    state = _HydrationState()
    queued_tasks: list[tuple[str, Callable[[], None]]] = []
    summary_callbacks: list[Callable[[], None]] = []

    controller = ready_shell_controller.ReadyShellPostShowController(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        state=state,
        queue_named_task=lambda name, callback: queued_tasks.append((name, callback)),
        start_queue=lambda: calls.append("start_queue"),
        workspace=lambda: workspace,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=cast(StartupTimer, _Timer(calls)),
        schedule_warmups=lambda reason: calls.append(f"warmups:{reason}"),
        schedule_visible_summary=summary_callbacks.append,
        trace_fields=lambda: {"route": "ready"},
    )

    updated = controller.update_backend_state("ready")
    scheduled = controller.schedule_hydration()
    queued_tasks[0][1]()

    assert updated is True
    assert scheduled is True
    assert main_window.generation_action_controller.states == ["ready"]
    assert state.hydration_started is True
    assert queued_tasks == [
        ("hydrate_initial_workspace", controller.hydrate_initial_workspace)
    ]
    assert summary_callbacks == [controller.log_visible_startup_summary]
    assert calls == [
        "start_queue",
        "mark:hydration_started",
        "span:start:post_show.hydration.full_hydrate",
        f"hydrate:{id(workspace)}",
        "span:end:post_show.hydration.full_hydrate",
        "mark:hydration_completed",
        "warmups:fallback_after_hydration",
    ]
    assert events[0] == (
        "shell_backend_state.update",
        {"state": "ready", "route": "ready"},
    )
    assert events[1] == ("post_show.hydration.queued", {"route": "ready"})


def test_ready_shell_post_show_controller_logs_visible_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-show controller should delegate visible startup summary logging."""

    events: list[tuple[str, dict[str, object]]] = []
    logs: list[dict[str, object]] = []
    _patch_trace(monkeypatch, events)
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "log_info",
        lambda _logger, message, **fields: logs.append({"message": message, **fields}),
    )

    controller = ready_shell_controller.ReadyShellPostShowController(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: object(),
        state=_HydrationState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=_marked_timer(),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {"route": "ready"},
    )

    controller.log_visible_startup_summary()

    assert logs[0]["message"] == "Startup visible loading summary"
    assert events == [
        (
            "startup.visible_loading.summary",
            {
                "session_restore_used": False,
                "workflow_count": 0,
                "active_cube_count": 0,
                "splash_close_to_shell_show_ms": "50.000",
                "splash_close_to_hydration_complete_ms": "150.000",
                "splash_close_to_restore_running_ms": "200.000",
                "route": "ready",
            },
        )
    ]


def test_create_ready_shell_post_show_controller_returns_controller() -> None:
    """Ready-shell post-show controller construction should live in its owner."""

    controller = ready_shell_controller.create_ready_shell_post_show_controller(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _frame: object(),
        state=_HydrationState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=_marked_timer(),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )

    assert isinstance(controller, ready_shell_controller.ReadyShellPostShowController)


def test_create_bound_ready_shell_post_show_controller_binds_backend_updater() -> None:
    """Bound post-show factory should connect backend-state projection."""

    main_window = _BackendStateMainWindow()
    updater = ready_shell_controller.ReadyShellBackendStateUpdater()
    controller = ready_shell_controller.create_bound_ready_shell_post_show_controller(
        backend_state_updater=updater,
        startup_cancelled=lambda: False,
        shell_frame=lambda: object(),
        main_window_for_shell=lambda _frame: main_window,
        state=_HydrationState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=_marked_timer(),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )

    updater.update("ready")

    assert isinstance(controller, ready_shell_controller.ReadyShellPostShowController)
    assert main_window.generation_action_controller.states == ["ready"]


def test_ready_shell_backend_state_updater_requires_binding() -> None:
    """Backend-state updater should fail before the post-show port is bound."""

    updater = ready_shell_controller.ReadyShellBackendStateUpdater()

    with pytest.raises(RuntimeError, match="updater is not bound"):
        updater.update("ready")


def test_ready_shell_backend_state_updater_forwards_to_bound_port() -> None:
    """Backend-state updater should forward states after binding."""

    states: list[str] = []
    updater = ready_shell_controller.ReadyShellBackendStateUpdater()

    def update_backend_state(state: str) -> None:
        """Record one backend state."""

        states.append(state)

    updater.bind(update_backend_state)

    updater.update("starting")
    updater.update("ready")
    assert states == ["starting", "ready"]


def test_prepare_ready_shell_hidden_restore_runtime_delegates_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell hidden runtime preparation should delegate restore policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    main_window = _HiddenRuntimeMainWindow(calls)

    prepared = ready_shell_controller.prepare_ready_shell_hidden_restore_runtime(
        main_window=main_window,
        comfy_http_ready=True,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
    )

    assert prepared is True
    assert calls == [
        "phase:start:startup.hidden_restore_runtime_prepare",
        "span:start:post_comfy.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "span:end:post_comfy.hidden_restore_runtime_prepare",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert events == []


def test_warm_ready_shell_restored_cube_definitions_runs_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell restored cube warmup should call the shell warmup port."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    workspace = object()
    main_window = _RestoreWarmupMainWindow(calls)

    warmed = ready_shell_controller.warm_ready_shell_restored_cube_definitions(
        main_window=main_window,
        workspace=workspace,
        comfy_http_ready=True,
        startup_timer=_Timer(calls),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is True
    assert calls == [
        "phase:start:startup.restore_cube_definition_warmup",
        "span:start:startup.restore_cube_definition_warmup",
        f"warm:{id(workspace)}",
        "span:end:startup.restore_cube_definition_warmup",
        "phase:end:startup.restore_cube_definition_warmup",
    ]
    assert events == []


def test_warm_ready_shell_restored_cube_definitions_skips_without_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell restored cube warmup should require ready backend."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []

    warmed = ready_shell_controller.warm_ready_shell_restored_cube_definitions(
        main_window=_RestoreWarmupMainWindow(calls),
        workspace=object(),
        comfy_http_ready=False,
        startup_timer=_Timer(calls),
        trace_fields=lambda: {"route": "ready"},
    )

    assert warmed is False
    assert calls == []
    assert events == [
        (
            "startup.restore_cube_definition_warmup.skip",
            {"reason": "backend_not_ready"},
        )
    ]


def test_prepare_ready_shell_hidden_restore_runtime_skips_without_prehydration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell hidden runtime preparation should require prehydration."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    main_window = _HiddenRuntimeMainWindow(calls)

    prepared = ready_shell_controller.prepare_ready_shell_hidden_restore_runtime(
        main_window=main_window,
        comfy_http_ready=True,
        prehydration_succeeded=False,
        startup_timer=_Timer(calls),
    )

    assert prepared is False
    assert calls == []
    assert events == [
        (
            "post_comfy.hidden_restore_runtime_prepare.skip",
            {"reason": "prehydration_not_succeeded"},
        )
    ]


def test_start_ready_shell_pre_show_restore_projection_delegates_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell pre-show projection should delegate projection policy."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    state = PreShowRestoreProjectionState()
    completions: list[Callable[[], None]] = []
    scheduled: list[tuple[int, Callable[[], None]]] = []
    reveals: list[str] = []

    deferred = ready_shell_controller.start_ready_shell_pre_show_restore_projection(
        state=state,
        hidden_restore_runtime_prepared=True,
        start_projection=_projection_starter_that_captures(completions),
        provisional_restore_projection=object(),
        fallback_workflow_id="wf-a",
        startup_cancelled=lambda: False,
        reveal_main_window=lambda: reveals.append("reveal"),
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
        trace_fields=lambda: {"route": "ready"},
    )

    assert deferred is True
    assert state.pending is True
    assert reveals == []
    assert len(completions) == 1
    assert len(scheduled) == 1
    assert events[0][0] == "main_shell.pre_show_restore_projection.start"
    assert events[-1][0] == "main_shell.pre_show_restore_projection.waiting"

    completions[0]()

    assert state.pending is False
    assert state.completion_handled is True
    assert reveals == ["reveal"]
    assert events[-1] == (
        "main_shell.pre_show_restore_projection.complete",
        {"reason": "surface_complete", "route": "ready"},
    )


def test_start_ready_shell_pre_show_restore_projection_skips_without_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell pre-show projection should require prepared runtime."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    state = PreShowRestoreProjectionState()
    reveals: list[str] = []
    scheduled: list[tuple[int, Callable[[], None]]] = []

    deferred = ready_shell_controller.start_ready_shell_pre_show_restore_projection(
        state=state,
        hidden_restore_runtime_prepared=False,
        start_projection=_projection_starter_that_returns(True),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled=lambda: False,
        reveal_main_window=lambda: reveals.append("reveal"),
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
        trace_fields=lambda: {"route": "ready"},
    )

    assert deferred is False
    assert state.pending is False
    assert reveals == []
    assert scheduled == []
    assert events == [
        (
            "main_shell.pre_show_restore_projection.skip",
            {
                "reason": "runtime_not_prepared",
                "cache_artifact_present": False,
                "restored_active_workflow_id": "wf-a",
                "route": "ready",
            },
        )
    ]


def test_try_reveal_ready_shell_blocks_until_all_gates_are_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should not inspect shell collaborators while blocked."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    state = _ShowGateState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=state,
        pre_show_projection_pending=False,
        minimum_shell_ready=False,
        comfy_http_ready=True,
        shell_frame=object(),
        comfy_state=None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=object(),
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _window: calls.append("reveal"),
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(revealed=False)
    assert state.main_window_shown is False
    assert calls == []
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("main_shell.try_show.blocked", {"route": "ready"}),
    ]


def test_try_reveal_ready_shell_reports_fatal_managed_incident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should fail closed on fatal managed startup incidents."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    incident = _FatalIncident(kind="startup_failed", severity="error")
    state = _ShowGateState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=state,
        pre_show_projection_pending=False,
        minimum_shell_ready=True,
        comfy_http_ready=True,
        shell_frame=object(),
        comfy_state=object(),
        fatal_incident_for_state=lambda _state: incident,
        handle_fatal_incident=lambda received: calls.append(
            "fatal" if received is incident else "fatal_wrong"
        ),
        main_window_for_shell=lambda _frame: calls.append("main_window"),
        workspace=None,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _window: calls.append("reveal"),
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(revealed=False)
    assert state.main_window_shown is False
    assert calls == ["fatal"]
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        (
            "main_shell.try_show.fatal_incident",
            {
                "incident_kind": "startup_failed",
                "incident_severity": "error",
                "route": "ready",
            },
        ),
    ]


def test_try_reveal_ready_shell_runs_restore_priority_and_reveals_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should warm restored state before immediate reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _ShowGateMainWindow(calls)
    revealed: list[object] = []
    state = _ShowGateState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=state,
        pre_show_projection_pending=False,
        minimum_shell_ready=True,
        comfy_http_ready=True,
        shell_frame=shell_frame,
        comfy_state=None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=workspace,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=revealed.append,
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=True,
        pre_show_projection_deferred=False,
    )
    assert state.main_window_shown is True
    assert revealed == [main_window]
    assert calls == [
        "phase:start:startup.restore_cube_definition_warmup",
        "span:start:startup.restore_cube_definition_warmup",
        f"warm:{id(workspace)}",
        "span:end:startup.restore_cube_definition_warmup",
        "phase:end:startup.restore_cube_definition_warmup",
        "phase:start:startup.hidden_restore_runtime_prepare",
        "span:start:post_comfy.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "span:end:post_comfy.hidden_restore_runtime_prepare",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("post_comfy.restore_priority.begin", {"route": "ready"}),
        ("post_comfy.restore_priority.end", {"route": "ready"}),
        (
            "main_shell.pre_show_restore_projection.skip",
            {
                "reason": "start_callable_missing",
                "cache_artifact_present": False,
                "restored_active_workflow_id": "wf-a",
                "route": "ready",
            },
        ),
    ]


def test_try_reveal_ready_shell_defers_reveal_for_pre_show_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show gate should wait for pre-show projection completion."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    projection_controller = _PreShowProjectionController(calls)
    main_window = _ShowGateMainWindow(
        calls,
        projection_controller=projection_controller,
    )
    projection_artifact = object()
    scheduled: list[tuple[int, Callable[[], None]]] = []
    revealed: list[object] = []
    show_state = _ShowGateState()
    projection_state = PreShowRestoreProjectionState()

    result = ready_shell_controller.try_reveal_ready_shell(
        startup_cancelled=False,
        state=show_state,
        pre_show_projection_pending=False,
        minimum_shell_ready=True,
        comfy_http_ready=True,
        shell_frame=shell_frame,
        comfy_state=None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=None,
        prehydration_succeeded=True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=projection_state,
        provisional_restore_projection=projection_artifact,
        fallback_workflow_id="wf-a",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=revealed.append,
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
        trace_fields=lambda: {"route": "ready"},
    )

    assert result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=True,
        pre_show_projection_deferred=True,
    )
    assert projection_state.pending is True
    assert show_state.main_window_shown is True
    assert revealed == []
    assert len(scheduled) == 1
    assert projection_controller.completions

    projection_controller.completions[0]()

    assert projection_state.pending is False
    assert revealed == [main_window]
    assert events[-1] == (
        "main_shell.pre_show_restore_projection.complete",
        {"reason": "surface_complete", "route": "ready"},
    )


def test_ready_shell_show_gate_task_uses_live_state_and_records_hidden_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell show-gate task should adapt live state through explicit ports."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    setattr(_patch_trace, "calls", calls)
    shell_frame = object()
    workspace = object()
    main_window = _ShowGateMainWindow(calls)
    state = _ShowGateState()
    minimum_shell_ready = False
    hidden_runtime_updates: list[bool] = []
    revealed: list[object] = []

    task = ready_shell_controller.ReadyShellShowGateTask(
        startup_cancelled=lambda: False,
        state=state,
        pre_show_projection_pending=lambda: False,
        minimum_shell_ready=lambda: minimum_shell_ready,
        comfy_http_ready=lambda: True,
        shell_frame=lambda: shell_frame,
        comfy_state=lambda: None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: calls.append("fatal"),
        main_window_for_shell=lambda frame: (
            main_window if frame is shell_frame else object()
        ),
        workspace=lambda: workspace,
        prehydration_succeeded=lambda: True,
        startup_timer=_Timer(calls),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=lambda: None,
        fallback_workflow_id=lambda: "wf-live",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=revealed.append,
        scheduler=lambda _delay, _callback: calls.append("schedule"),
        set_hidden_restore_runtime_prepared=hidden_runtime_updates.append,
        trace_fields=lambda: {"route": "ready"},
    )

    blocked_result = task.try_show()

    assert blocked_result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=False
    )
    assert state.main_window_shown is False
    assert hidden_runtime_updates == []
    assert revealed == []
    assert calls == []

    minimum_shell_ready = True
    revealed_result = task.try_show()

    assert revealed_result == ready_shell_controller.ReadyShellShowGateResult(
        revealed=True,
        hidden_restore_runtime_prepared=True,
        pre_show_projection_deferred=False,
    )
    assert state.main_window_shown is True
    assert hidden_runtime_updates == [True]
    assert revealed == [main_window]
    assert calls == [
        "phase:start:startup.restore_cube_definition_warmup",
        "span:start:startup.restore_cube_definition_warmup",
        f"warm:{id(workspace)}",
        "span:end:startup.restore_cube_definition_warmup",
        "phase:end:startup.restore_cube_definition_warmup",
        "phase:start:startup.hidden_restore_runtime_prepare",
        "span:start:post_comfy.hidden_restore_runtime_prepare",
        "prepare_runtime",
        "span:end:post_comfy.hidden_restore_runtime_prepare",
        "phase:end:startup.hidden_restore_runtime_prepare",
    ]
    assert events == [
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("main_shell.try_show.blocked", {"route": "ready"}),
        ("main_shell.try_show.enter", {"route": "ready"}),
        ("post_comfy.restore_priority.begin", {"route": "ready"}),
        ("post_comfy.restore_priority.end", {"route": "ready"}),
        (
            "main_shell.pre_show_restore_projection.skip",
            {
                "reason": "start_callable_missing",
                "cache_artifact_present": False,
                "restored_active_workflow_id": "wf-live",
                "route": "ready",
            },
        ),
    ]


def test_create_ready_shell_show_gate_task_returns_task() -> None:
    """Show-gate task construction should live in its owner."""

    task = ready_shell_controller.create_ready_shell_show_gate_task(
        startup_cancelled=lambda: False,
        state=_ShowGateState(),
        pre_show_projection_pending=lambda: False,
        minimum_shell_ready=lambda: False,
        comfy_http_ready=lambda: False,
        shell_frame=lambda: None,
        comfy_state=lambda: None,
        fatal_incident_for_state=lambda _state: None,
        handle_fatal_incident=lambda _incident: None,
        main_window_for_shell=lambda _frame: object(),
        workspace=lambda: None,
        prehydration_succeeded=lambda: False,
        startup_timer=_Timer([]),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=lambda: None,
        fallback_workflow_id=lambda: "wf-live",
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _window: None,
        scheduler=lambda _delay, _callback: None,
        set_hidden_restore_runtime_prepared=lambda _prepared: None,
        trace_fields=lambda: {"route": "ready"},
    )

    assert isinstance(task, ready_shell_controller.ReadyShellShowGateTask)


def test_ready_shell_controller_imports_no_forbidden_boundaries() -> None:
    """Ready-shell orchestration should stay behind explicit startup ports."""

    imported_modules = _imported_module_names(READY_SHELL_CONTROLLER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_shell_build_task() -> None:
    """Startup should delegate shell-build task internals to ready-shell owner."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")
    ready_launch_source = STARTUP_READY_SHELL_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "create_startup_ready_shell_launch_controller(" not in source
    assert "create_startup_managed_ready_shell_launcher(" not in source
    assert "create_startup_managed_ready_shell_launcher(" in ready_launch_source
    assert (
        "launch_managed_ready_shell=managed_ready_shell_launcher.launch"
        in ready_launch_source
    )
    assert "create_ready_shell_launch_controller(" not in source
    assert "ReadyShellLaunchController(" not in source
    assert "managed_ready_launch.create_failure_queue(" in launch_source
    assert "managed_ready_launch.create_failure_queue(" not in source
    assert "managed_ready_runtime.create_failure_queue(" not in launch_source
    assert "create_ready_shell_failure_queue(" not in source
    assert "ReadyShellFailureQueue(" not in source
    assert "managed_ready_launch.schedule_startup_tasks(" in launch_source
    assert "managed_ready_runtime.schedule_startup_tasks(" not in launch_source
    assert "schedule_ready_shell_controller_startup_tasks(" not in source
    assert "schedule_ready_shell_startup_tasks(" not in source
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launch_source
    assert (
        "managed_ready_runtime.create_local_editor_warmup_adapter(" not in launch_source
    )
    assert "create_ready_shell_local_editor_warmup_adapter(" not in source
    assert "ReadyShellLocalEditorWarmupAdapter(" not in source
    assert "managed_ready_launch.create_managed_startup_prelude(" in launch_source
    assert "managed_ready_runtime.create_managed_startup_prelude(" not in launch_source
    assert "create_ready_shell_managed_startup_prelude(" not in source
    assert "ReadyShellManagedStartupPrelude(" not in source
    assert "def launch_ready_shell" not in source
    assert "try_begin_ready_shell_launch(" not in source
    assert "launch_no_comfy_ready_shell(" not in source
    assert "publish_no_comfy_ready_shell_result(" not in source
    assert "StartupFailureController(" not in source
    assert "StartupFailClosedCleanupPortFactory(" not in source
    assert "GuiStartupTaskQueue(" not in source
    assert "start_local_editor_startup_warmup(" not in source
    assert (
        "startup_support_graph.startup_cancel_bridge.cancel_requested.connect"
        in shell_flow_source
    )
    assert (
        "startup_support_graph.startup_cancel_bridge.cancel_requested.emit"
        in shell_flow_source
    )
    assert "initial_splash_cancel_connector=initial_splash_cancel_connector" in source
    assert (
        "startup_splash_start_or_adopt=(\n"
        "            startup_support_graph.startup_splash_ports.start_or_adopt_launch_splash\n"
        "        )," in shell_flow_source
    )
    assert "initial_splash_cancel_connector(" not in source
    assert "start_or_adopt_launch_splash(" not in source
    assert "start_qpane_sam_startup_warmup(" not in source
    assert "managed_ready_launch.create_target_activation_task(" in launch_source
    assert "managed_ready_runtime.create_target_activation_task(" not in launch_source
    assert "create_ready_shell_target_activation_task(" not in source
    assert "ReadyShellTargetActivationTask(" not in source
    assert "def activate_target_task" not in source
    assert "activate_ready_shell_target_task(" not in source
    assert "activate_ready_shell_target(" not in source
    assert "activation_result.started" not in source
    assert "activation_result.comfy_state" not in source
    assert 'with trace_span("activate_target_task.activate")' not in source
    assert (
        "managed_ready_launch.create_target_activation_task(\n"
        "            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,"
        in launch_source
    )
    assert "mark_activation_started=" not in source
    assert "comfy_activation_started" not in source
    assert "managed_ready_launch.create_shell_build_task(" in launch_source
    assert "managed_ready_runtime.create_shell_build_task(" not in launch_source
    assert "create_ready_shell_build_task(" not in source
    assert "ReadyShellBuildTask(" not in source
    assert "def build_shell_task" not in source
    assert "build_ready_shell_skeleton_task(" not in source
    assert "build_ready_shell_skeleton(" not in source
    assert "built_shell_frame" not in source
    assert "managed_ready_launch.create_metadata_bridge_task(" in launch_source
    assert "managed_ready_runtime.create_metadata_bridge_task(" not in launch_source
    assert "create_ready_shell_metadata_bridge_task(" not in source
    assert "ReadyShellMetadataBridgeTask(" not in source
    assert "def wire_metadata_bridge_task" not in source
    assert "wire_ready_shell_metadata_bridge_task(" not in source
    assert "wire_ready_shell_metadata_bridge(" not in source
    assert "metadata_update_bridge = wire_ready_shell_metadata_bridge" not in source
    assert "managed_ready_launch.create_minimum_ready_task(" in launch_source
    assert "managed_ready_runtime.create_minimum_ready_task(" not in launch_source
    assert "create_ready_shell_minimum_ready_task(" not in source
    assert "ReadyShellMinimumReadyTask(" not in source
    assert "def mark_minimum_shell_ready_task" not in source
    assert "mark_ready_shell_minimum_ready_task(" not in source
    assert "            state=ready_state," not in source
    assert "mark_ready=lambda: setattr(" not in source
    assert "mark_ready_shell_minimum_ready(" not in source
    assert "managed_ready_launch.create_prompt_editor_warmup_task(" in launch_source
    assert (
        "managed_ready_runtime.create_prompt_editor_warmup_task(" not in launch_source
    )
    assert "create_ready_shell_prompt_editor_warmup_task(" not in source
    assert "ReadyShellPromptEditorWarmupTask(" not in source
    assert "def warm_prompt_editor_gui_task" not in source
    assert "warm_ready_shell_prompt_editor_gui(" not in source
    assert "warm_prompt_editor_gui_before_reveal(" not in source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task("
        not in launch_source
    )
    assert "create_ready_shell_initial_workspace_prehydration_task(" not in source
    assert "ReadyShellInitialWorkspacePrehydrationTask(" not in source
    assert "def prehydrate_initial_workspace_task" not in source
    assert "prehydrate_ready_shell_initial_workspace_task(" not in source
    assert " prehydrate_ready_shell_initial_workspace(" not in source
    assert "ready_state.prehydration_attempted = True" not in source
    assert "prehydration_result.attempted" not in source
    assert "prehydrate_initial_workspace_before_show(" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller(" not in launch_source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "ReadyShellPostShowController(" not in source
    assert (
        "backend_state_updater = managed_ready_state.backend_state_updater"
        not in source
    )
    assert "set_backend_state=backend_state_updater.update" not in source
    assert "update_backend_state=backend_state_updater.update" not in source
    assert "backend_state_updater=backend_state_updater" not in source
    assert "backend_state_updater.bind(" not in source
    assert "ReadyShellBackendStateUpdater(" not in source
    assert "def set_ready_shell_backend_state" not in source
    assert "project_ready_shell_backend_state(" not in source
    assert "update_built_shell_backend_state(" not in source
    assert "schedule_ready_shell_post_show_hydration(" not in source
    assert "schedule_post_show_hydration_after_reveal(" not in source
    assert " hydrate_ready_shell_initial_workspace(" not in source
    assert "hydrate_initial_workspace_after_show(" not in source
    assert "emit_ready_shell_visible_startup_summary(" not in source
    assert "emit_visible_startup_summary(" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task(" not in launch_source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "ReadyShellShowGateTask(" not in source
    assert "def try_show_main_window" not in source
    assert "try_reveal_ready_shell(" not in source
    assert "main_window_shown=ready_state.main_window_shown" not in source
    assert "mark_main_window_shown=lambda: setattr(" not in source
    assert "hydration_started=lambda: ready_state.hydration_started" not in source
    assert "mark_hydration_started=lambda: setattr(" not in source
    assert "prepare_ready_shell_hidden_restore_runtime(" not in source
    assert "prepare_hidden_restore_runtime_before_show(" not in source
    assert "warm_ready_shell_restored_cube_definitions(" not in source
    assert "shell_restore_warmup_controller" not in source
    assert "warm_restored_workspace_cube_definitions(" not in source
    assert "start_ready_shell_pre_show_restore_projection(" not in source
    assert "start_pre_show_restore_projection_if_available(" not in source
    assert '"main_shell.try_show.enter"' not in source
    assert '"main_shell.try_show.blocked"' not in source
    assert '"post_comfy.restore_priority.begin"' not in source
    assert "restore_projection_controller" not in source
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter"
        not in launch_source
    )
    assert "create_ready_shell_startup_diagnostics_update_adapter(" not in source
    assert "ReadyShellStartupDiagnosticsUpdateAdapter(" not in source
    assert "request_ready_shell_startup_diagnostics_update(" not in source
    assert '"post_show.diagnostics.async_requested"' not in source
    assert "managed_ready_launch.create_reveal_task(" in launch_source
    assert "managed_ready_runtime.create_reveal_task(" not in launch_source
    assert "create_ready_shell_reveal_task(" not in source
    assert "ReadyShellRevealTask(" not in source
    assert "def reveal_main_window" not in source
    assert "connect_ready_shell_restore_finalized_warmups(" not in source
    assert "connect_restore_finalized_warmups(" not in source
    assert "schedule_nonessential_startup_warmups(" not in source
    assert "reveal_ready_shell_main_window(" not in source
    assert 'with trace_span("launch_splash.close")' not in source
    assert 'with trace_span("main_shell.show")' not in source
    assert '"Main shell revealed"' not in source
    assert "wire_model_metadata_update_bridge(" not in source
    assert 'splash.append_log("Preparing the application interface.")' not in source
    assert 'with trace_span("build_shell_task.build_main_window")' not in source
    assert "attach_restore_asset_preload_to_shell(" not in source


def _patch_trace(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[str, dict[str, object]]],
) -> None:
    """Patch trace calls used by the ready-shell controller slice."""

    monkeypatch.setattr(
        ready_shell_controller,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        ready_shell_restore_controller,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        startup_model_metadata,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        startup_warmup_controller,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )
    monkeypatch.setattr(
        pre_show_restore_projection,
        "trace_mark",
        lambda event_name, **fields: events.append((event_name, fields)),
    )

    @contextmanager
    def fake_span(name: str, **_fields: object) -> Iterator[None]:
        calls = getattr(_patch_trace, "calls")
        calls.append(f"span:start:{name}")
        yield
        calls.append(f"span:end:{name}")

    monkeypatch.setattr(ready_shell_controller, "trace_span", fake_span)
    monkeypatch.setattr(ready_shell_restore_controller, "trace_span", fake_span)


def _marked_timer() -> StartupTimer:
    """Create a startup timer with visible loading milestones."""

    clock_values = iter([1.0, 1.1, 1.15, 1.25, 1.30])
    timer = StartupTimer(clock=lambda: next(clock_values))
    timer.mark("splash_closed")
    timer.mark("main_shell_shown")
    timer.mark("hydration_completed")
    timer.mark("restore_lifecycle_running")
    return timer


def _projection_starter_that_captures(
    completions: list[Callable[[], None]],
) -> Callable[..., bool]:
    """Return a projection starter that captures completion callbacks."""

    def start_projection(
        artifact: object | None,
        *,
        fallback_workflow_id: str,
        on_complete: Callable[[], None],
    ) -> bool:
        """Record the completion callback."""

        _ = artifact
        _ = fallback_workflow_id
        completions.append(on_complete)
        return True

    return start_projection


def _projection_starter_that_returns(started: bool) -> Callable[..., bool]:
    """Return a projection starter with a fixed result."""

    def start_projection(
        artifact: object | None,
        *,
        fallback_workflow_id: str,
        on_complete: Callable[[], None],
    ) -> bool:
        """Return the fixed projection-start result."""

        _ = artifact
        _ = fallback_workflow_id
        _ = on_complete
        return started

    return start_projection


class _Timer:
    """Record phase timing requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Record phase entry and exit."""

        self._calls.append(f"phase:start:{name}")
        setattr(_patch_trace, "calls", self._calls)
        yield
        self._calls.append(f"phase:end:{name}")

    def mark(self, name: str) -> None:
        """Record one startup milestone."""

        self._calls.append(f"mark:{name}")


class _Splash:
    """Record splash log lines."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def append_log(self, line: str) -> None:
        """Record one splash log line."""

        self._calls.append(f"splash_log:{line}")

    def close(self) -> None:
        """Record one splash close request."""

        self._calls.append("splash_close")


@dataclass(frozen=True)
class _LaunchEndpoint:
    """Minimal endpoint shape for ready-shell launch tests."""

    host: str = "127.0.0.1"
    port: int = 8188


@dataclass(frozen=True)
class _LaunchTarget:
    """Minimal target shape for ready-shell launch tests."""

    mode: str = "managed"
    endpoint: _LaunchEndpoint = _LaunchEndpoint()


@dataclass(frozen=True)
class _LaunchContext:
    """Minimal installation-context shape for ready-shell launch tests."""

    comfy_target: _LaunchTarget = _LaunchTarget()


class _CloseSplash:
    """Record close requests for reveal tests."""

    def __init__(self, calls: list[str], *, fail: bool = False) -> None:
        """Store the call recorder and failure mode."""

        self._calls = calls
        self._fail = fail

    def close(self) -> None:
        """Record and optionally fail a splash close."""

        self._calls.append("splash:close")
        if self._fail:
            raise RuntimeError("splash close failed")


class _ControllerTaskQueue:
    """Expose the queue protocol accepted by controller startup task scheduling."""

    def add(self, name: str, callback: Callable[[], None]) -> None:
        """Satisfy the queue protocol without recording unused calls."""

        _ = name
        _ = callback

    def start(self) -> None:
        """Satisfy the queue protocol without starting real work."""


class _Runnable:
    """Record a named task when its run port is invoked."""

    def __init__(self, name: str, calls: list[str]) -> None:
        """Store the task name and call recorder."""

        self._name = name
        self._calls = calls

    def run(self) -> None:
        """Record execution through the task run port."""

        self._calls.append(self._name)


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


class _WorkspaceRestoreController:
    """Record workspace prehydration requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def prehydrate_initial_workspace(self, workspace: object) -> bool:
        """Record one prehydration request."""

        self._calls.append(f"prehydrate:{id(workspace)}")
        return True

    def hydrate_initial_workspace(self, workspace: object | None = None) -> None:
        """Record one hydration request."""

        if workspace is None:
            self._calls.append("hydrate:blank")
        else:
            self._calls.append(f"hydrate:{id(workspace)}")


class _PrehydrationMainWindow:
    """Expose workspace restore collaborators for prehydration."""

    def __init__(self, calls: list[str]) -> None:
        """Create the workspace restore controller double."""

        self.workspace_restore_controller = _WorkspaceRestoreController(calls)


class _PrehydrationState:
    """Record ready-shell prehydration gate state."""

    def __init__(self) -> None:
        """Initialize prehydration gates as not attempted."""

        self.prehydration_attempted = False
        self.prehydration_succeeded = False


class _GenerationActionController:
    """Record projected backend states."""

    def __init__(self) -> None:
        """Initialize recorded backend states."""

        self.states: list[str] = []

    def set_backend_state(self, state: str) -> None:
        """Record one backend state projection."""

        self.states.append(state)


class _BackendStateMainWindow:
    """Expose generation action state collaborators."""

    def __init__(self) -> None:
        """Create the generation action controller double."""

        self.generation_action_controller = _GenerationActionController()


class _HydrationMainWindow:
    """Expose workspace restore collaborators for hydration."""

    def __init__(self, calls: list[str]) -> None:
        """Create the workspace restore controller double."""

        self.workspace_restore_controller = _WorkspaceRestoreController(calls)
        self.shell_prehydrated_restore_controller = None


class _PostShowMainWindow:
    """Expose backend-state and hydration collaborators for post-show tests."""

    def __init__(self, calls: list[str]) -> None:
        """Create post-show shell collaborator doubles."""

        self.generation_action_controller = _GenerationActionController()
        self.workspace_restore_controller = _WorkspaceRestoreController(calls)
        self.shell_prehydrated_restore_controller = None


class _PrehydratedRestoreController:
    """Record hidden restore runtime preparation requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def prepare_initial_workspace_restore_runtime(self) -> bool:
        """Record hidden runtime preparation."""

        self._calls.append("prepare_runtime")
        return True


class _HiddenRuntimeMainWindow:
    """Expose prehydrated restore collaborators for runtime preparation."""

    def __init__(self, calls: list[str]) -> None:
        """Create the prehydrated restore controller double."""

        self.shell_prehydrated_restore_controller = _PrehydratedRestoreController(calls)


class _ShowGateMainWindow:
    """Expose restore-priority collaborators for show-gate tests."""

    def __init__(
        self,
        calls: list[str],
        *,
        projection_controller: _PreShowProjectionController | None = None,
    ) -> None:
        """Create all collaborators used before ready-shell reveal."""

        self.shell_restore_warmup_controller = _RestoreWarmupController(calls)
        self.shell_prehydrated_restore_controller = _PrehydratedRestoreController(calls)
        self.restore_projection_controller = projection_controller


class _PreShowProjectionController:
    """Capture pre-show projection completion callbacks."""

    def __init__(self, calls: list[str]) -> None:
        """Store call and completion recorders."""

        self._calls = calls
        self.completions: list[Callable[[], None]] = []

    def start_pre_show_restore_projection(
        self,
        artifact: object | None,
        *,
        fallback_workflow_id: str,
        on_complete: Callable[[], None],
    ) -> bool:
        """Record one pre-show projection request."""

        self._calls.append(
            "projection:"
            f"{'artifact' if artifact is not None else 'none'}:"
            f"{fallback_workflow_id}"
        )
        self.completions.append(on_complete)
        return True


@dataclass(frozen=True)
class _FatalIncident:
    """Expose fatal incident fields used by the show-gate trace."""

    kind: str
    severity: str


@dataclass
class _MinimumReadyState:
    """Expose the ready-shell minimum-ready state field."""

    minimum_shell_ready: bool = False


@dataclass
class _ActivationState:
    """Expose the ready-shell activation-started state field."""

    comfy_activation_started: bool = False


@dataclass
class _HydrationState:
    """Expose the ready-shell post-show hydration state field."""

    hydration_started: bool = False


@dataclass
class _ShowGateState:
    """Expose the ready-shell show-gate state field."""

    main_window_shown: bool = False


class _RestoreWarmupController:
    """Record restored cube-definition warmup requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def warm_restored_workspace_cube_definitions(
        self, workspace: object | None
    ) -> None:
        """Record one restored workspace warmup."""

        if workspace is None:
            self._calls.append("warm:blank")
        else:
            self._calls.append(f"warm:{id(workspace)}")


class _RestoreWarmupMainWindow:
    """Expose restored cube-definition warmup collaborators."""

    def __init__(self, calls: list[str]) -> None:
        """Create the restore warmup controller double."""

        self.shell_restore_warmup_controller = _RestoreWarmupController(calls)


class _RestoreFinalizedMainWindow:
    """Expose a restore-finalized signal for warmup wiring."""

    def __init__(self, signal: _Signal) -> None:
        """Store the restore-finalized signal double."""

        self.restore_finalized = signal


class _Signal:
    """Record metadata signal connections."""

    def __init__(self) -> None:
        """Initialize connected callbacks."""

        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self.callbacks.append(callback)


class _SignalBridge:
    """Expose a metadata-updated signal."""

    def __init__(self) -> None:
        """Create the signal double."""

        self.model_updated = _Signal()

    def emit_model_updated(self, _event: object) -> None:
        """Satisfy the metadata bridge protocol."""


class _MetadataSurfaceRefreshController:
    """Expose the model metadata update callback."""

    def handle_model_metadata_updated(self, _event: object) -> None:
        """Accept one model metadata update event."""


class _MetadataMainWindow:
    """Expose the metadata surface refresh controller."""

    def __init__(
        self,
        controller: _MetadataSurfaceRefreshController,
    ) -> None:
        """Store the controller double."""

        self.model_metadata_surface_refresh_controller = controller


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules
