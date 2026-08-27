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

"""Test startup-warmup behavior owners."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.app.bootstrap.startup_warmup_controller import (
    NonessentialStartupWarmupScheduler,
    StartupWarmupState,
    connect_restore_finalized_warmups,
    create_nonessential_startup_warmup_scheduler,
    schedule_nonessential_startup_warmups,
)


from .support import (
    _Signal,
)

PROJECT_ROOT = Path(__file__).resolve().parents[6]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_WARMUP_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_warmup_controller.py"
)
FORBIDDEN_STARTUP_WARMUP_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_schedule_nonessential_startup_warmups_defers_with_reason() -> None:
    """Nonessential warmup scheduling should delegate to the injected scheduler."""

    scheduled: list[tuple[int, object]] = []
    started: list[str] = []

    schedule_nonessential_startup_warmups(
        reason="restore_finalized",
        delay_ms=2000,
        scheduler=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        start_warmups=lambda: started.append("start"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )

    assert scheduled == [(2000, scheduled[0][1])]
    callback = scheduled[0][1]
    assert callable(callback)
    callback()
    assert started == ["start"]


def test_nonessential_startup_warmup_scheduler_binds_delay_and_ports() -> None:
    """Nonessential warmup scheduler should expose one reusable schedule port."""

    scheduled: list[tuple[int, Callable[[], None]]] = []
    calls: list[dict[str, object]] = []
    started: list[str] = []

    def schedule_warmups(**kwargs: object) -> None:
        """Record scheduling inputs and use the supplied scheduler."""

        calls.append(kwargs)
        scheduler = cast(
            Callable[[int, Callable[[], None]], None],
            kwargs["scheduler"],
        )
        start_warmups = cast(Callable[[], None], kwargs["start_warmups"])
        scheduler(cast(int, kwargs["delay_ms"]), start_warmups)

    scheduler = NonessentialStartupWarmupScheduler(
        scheduler=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        start_warmups=lambda: started.append("start"),
        trace_fields=lambda: {"workflow_id": "wf-a"},
        delay_ms=2400,
        schedule_warmups=schedule_warmups,
    )

    scheduler.schedule("restore_finalized")

    assert calls[0]["reason"] == "restore_finalized"
    assert calls[0]["delay_ms"] == 2400
    trace_fields = cast(Callable[[], dict[str, object]], calls[0]["trace_fields"])
    assert trace_fields() == {"workflow_id": "wf-a"}
    assert scheduled == [(2400, scheduled[0][1])]
    scheduled[0][1]()
    assert started == ["start"]


def test_create_nonessential_startup_warmup_scheduler_returns_scheduler() -> None:
    """Nonessential warmup scheduler construction should live in its owner."""

    scheduler = create_nonessential_startup_warmup_scheduler(
        scheduler=lambda _delay_ms, _callback: None,
        start_warmups=lambda: None,
        trace_fields=lambda: {},
    )

    assert isinstance(scheduler, NonessentialStartupWarmupScheduler)


def test_connect_restore_finalized_warmups_schedules_after_signal() -> None:
    """Restore-finalized wiring should retain and connect one callback."""

    state = StartupWarmupState()
    signal = _Signal()
    scheduled_reasons: list[str] = []
    main_window = SimpleNamespace(restore_finalized=signal)

    connect_restore_finalized_warmups(
        state=state,
        main_window=main_window,
        schedule_warmups=scheduled_reasons.append,
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )
    connect_restore_finalized_warmups(
        state=state,
        main_window=main_window,
        schedule_warmups=scheduled_reasons.append,
        trace_fields=lambda: {"workflow_id": "wf-a"},
    )

    assert state.restore_finalized_warmups_connected is True
    assert state.restore_finalized_warmups_callback is signal.callback
    assert signal.connect_count == 1
    signal.emit()
    assert scheduled_reasons == ["restore_finalized"]


def test_connect_restore_finalized_warmups_skips_missing_signal() -> None:
    """Restore-finalized wiring should be optional for shell-like test doubles."""

    state = StartupWarmupState()

    connect_restore_finalized_warmups(
        state=state,
        main_window=SimpleNamespace(),
        schedule_warmups=lambda _reason: None,
        trace_fields=lambda: {},
    )

    assert state.restore_finalized_warmups_connected is False
    assert state.restore_finalized_warmups_callback is None
