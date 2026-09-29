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

from collections.abc import Callable
from pathlib import Path
from typing import cast
from sugarsubstitute_shared.launch_splash.progress import SplashProgress

import pytest
from PySide6.QtWidgets import QWidget

from substitute.app.bootstrap import (
    ready_shell_reveal,
    startup_warmup_controller,
)
from substitute.app.bootstrap.splash_surface_handoff import SplashHandoffError

from ..support.restore_signals import _Signal
from ..support.shell_surfaces import _CloseSplash
from ..support.timing import _Timer
from ..support.trace import _patch_trace
from tests.support.qt.lifecycle import destroy_widget_roots, ensure_qt_application

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


class _VisibleSplash(QWidget):
    """Expose the real top-level visibility contract during shell reveal."""

    def set_progress(self, progress: SplashProgress, *, status: str) -> None:
        """Accept the final splash status without changing visibility."""

        _ = progress, status


def test_main_shell_never_appears_alongside_visible_splash() -> None:
    """Close the previous top-level surface before showing its replacement."""

    ensure_qt_application()
    splash = _VisibleSplash()
    main_window = QWidget()
    splash.show()
    calls: list[str] = []

    def show(frame: object, **_kwargs: object) -> QWidget:
        """Reject any replacement reveal while the splash remains visible."""

        assert frame is main_window
        assert not splash.isVisible()
        main_window.show()
        calls.append("main_shown")
        return main_window

    try:
        ready_shell_reveal.reveal_ready_shell_main_window(
            splash=splash,
            shell_frame=main_window,
            initial_shell_placement=None,
            comfy_http_ready=True,
            startup_timer=_Timer(calls),
            show_built_main_window=show,
            set_current_shell=lambda _frame: None,
            update_backend_state=lambda _state: None,
            connect_restore_finalized_warmups=lambda: None,
            request_startup_diagnostics_update=lambda: None,
            schedule_post_show_hydration=lambda: None,
            trace_fields=lambda: {},
        )

        assert calls.index("mark:splash_closed") < calls.index("main_shown")
        assert main_window.isVisible()
        assert not splash.isVisible()
    finally:
        destroy_widget_roots((main_window, splash))


def test_reveal_ready_shell_main_window_sequences_post_show_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell reveal should close splash before showing and fan out work."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    logs: list[dict[str, object]] = []
    paint_callbacks: list[Callable[[], None]] = []
    monkeypatch.setattr(
        "sugarsubstitute_shared.qt_surface_readiness.run_after_surface_paint",
        lambda _window, callback: paint_callbacks.append(callback),
    )
    monkeypatch.setattr(
        ready_shell_reveal,
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

    def schedule_readiness_receipt(
        window: object,
        *,
        before_publish: Callable[[], None] | None = None,
    ) -> bool:
        """Record readiness scheduling at the visible-shell boundary."""

        _ = window
        calls.append("schedule_readiness")
        if before_publish is not None:
            paint_callbacks.append(before_publish)
        return True

    result = ready_shell_reveal.reveal_ready_shell_main_window(
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
        schedule_readiness_receipt=schedule_readiness_receipt,
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
        "schedule_readiness",
        "backend:ready",
        "connect_warmups",
        "diagnostics",
        "schedule_hydration",
    ]
    assert events == [
        ("launch_splash.closed", {"route": "ready"}),
        ("main_shell.shown", {"route": "ready"}),
    ]
    assert paint_callbacks == []
    assert logs == [
        {
            "message": "Main shell revealed",
            "comfy_http_ready": True,
        }
    ]


def test_reveal_ready_shell_main_window_blocks_on_splash_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash close failure must block shell reveal and leave the old surface."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    monkeypatch.setattr(
        ready_shell_reveal,
        "log_info",
        lambda _logger, _message, **_fields: None,
    )
    shell_frame = object()
    splash = _CloseSplash(calls, fail=True)

    with pytest.raises(RuntimeError, match="splash close failed"):
        ready_shell_reveal.reveal_ready_shell_main_window(
            splash=splash,
            shell_frame=shell_frame,
            initial_shell_placement=None,
            comfy_http_ready=False,
            startup_timer=_Timer(calls),
            show_built_main_window=lambda _frame, **_kwargs: calls.append("show"),
            set_current_shell=lambda _frame: calls.append("set_current"),
            update_backend_state=lambda state: calls.append(f"backend:{state}"),
            connect_restore_finalized_warmups=lambda: calls.append("connect_warmups"),
            request_startup_diagnostics_update=lambda: calls.append("diagnostics"),
            schedule_post_show_hydration=lambda: calls.append("schedule_hydration"),
            trace_fields=lambda: {"route": "ready"},
        )

    assert calls == [
        "phase:start:startup.close_launch_splash",
        "span:start:launch_splash.close",
        "splash:close",
    ]
    assert events == []


def test_reveal_retains_splash_when_close_is_not_acknowledged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unconfirmed close must prevent shell reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    monkeypatch.setattr(
        ready_shell_reveal,
        "log_info",
        lambda _logger, _message, **_fields: None,
    )
    splash = _CloseSplash(calls, acknowledged=False)

    with pytest.raises(SplashHandoffError, match="not confirmed"):
        ready_shell_reveal.reveal_ready_shell_main_window(
            splash=splash,
            shell_frame=object(),
            initial_shell_placement=None,
            comfy_http_ready=True,
            startup_timer=_Timer(calls),
            show_built_main_window=lambda frame, **_kwargs: calls.append("show"),
            set_current_shell=lambda _frame: None,
            update_backend_state=lambda _state: None,
            connect_restore_finalized_warmups=lambda: None,
            request_startup_diagnostics_update=lambda: None,
            schedule_post_show_hydration=lambda: None,
            trace_fields=lambda: {"route": "ready"},
        )

    assert "mark:splash_closed" not in calls
    assert "show" not in calls
    assert events == []


def test_ready_shell_reveal_task_uses_live_shell_and_splash_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ready-shell reveal task should update live shell and splash references."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    calls: list[str] = []
    monkeypatch.setattr(
        ready_shell_reveal,
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

    task = ready_shell_reveal.ReadyShellRevealTask(
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
    assert result.splash is splash_state[0]
    assert shell_state == [shown_shell_frame]
    assert splash_state[0] is None
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
    assert splash_state == [None]
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

    task = ready_shell_reveal.create_ready_shell_reveal_task(
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

    assert isinstance(task, ready_shell_reveal.ReadyShellRevealTask)


@pytest.mark.parametrize("progress_fails", [False, True])
def test_real_shell_closes_splash_before_replacement_surface_paints(
    monkeypatch: pytest.MonkeyPatch,
    progress_fails: bool,
) -> None:
    """Close splash before show even when its optional progress update fails."""

    application = ensure_qt_application()
    monkeypatch.setattr(
        ready_shell_reveal,
        "log_info",
        lambda _logger, _message, **_fields: None,
    )
    calls: list[str] = []
    window = QWidget()
    splash = _CloseSplash(calls)
    if progress_fails:

        def fail_progress(progress: SplashProgress, *, status: str) -> None:
            """Simulate a unavailable completion presentation during handoff."""
            raise RuntimeError("completion presentation unavailable")

        monkeypatch.setattr(splash, "set_progress", fail_progress)

    def show(frame: object, **_kwargs: object) -> object:
        """Show the exact production-shaped QWidget without pumping events."""

        assert frame is window
        window.show()
        calls.append("show")
        return window

    ready_shell_reveal.reveal_ready_shell_main_window(
        splash=splash,
        shell_frame=window,
        initial_shell_placement=None,
        comfy_http_ready=True,
        startup_timer=_Timer(calls),
        show_built_main_window=show,
        set_current_shell=lambda _frame: None,
        update_backend_state=lambda _state: None,
        connect_restore_finalized_warmups=lambda: None,
        request_startup_diagnostics_update=lambda: None,
        schedule_post_show_hydration=lambda: None,
        trace_fields=lambda: {},
        schedule_readiness_receipt=lambda _window: True,
    )

    assert splash.progress == ([] if progress_fails else [SplashProgress(1, 1)])
    assert calls.index("splash:close") < calls.index("show")
    window.close()
    application.processEvents()


class _RestoreFinalizedMainWindow:
    """Expose a restore-finalized signal for warmup wiring."""

    def __init__(self, signal: _Signal) -> None:
        """Store the restore-finalized signal double."""

        self.restore_finalized = signal
