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

"""Tests for startup Qt timer adapters."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.app.bootstrap import startup_qt_timers

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIMER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_qt_timers.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
READINESS_RUNTIME_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_readiness_runtime.py"
)
FORBIDDEN_TIMER_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_qtimer_factory_uses_qtimer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup timer factory should create one concrete Qt timer."""

    calls: list[str] = []

    class _Timer:
        """Record construction of one fake timer."""

        def __init__(self) -> None:
            """Record construction."""

            calls.append("created")

    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_qt_timers.QtCore.QTimer",
        _Timer,
    )

    assert isinstance(startup_qt_timers.create_startup_qtimer(), _Timer)
    assert calls == ["created"]


def test_startup_single_shot_delegates_to_qtimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup single-shot scheduler should delegate delay and callback to Qt."""

    callbacks: list[tuple[int, object]] = []

    class _TimerFactory:
        """Expose one recording Qt single-shot replacement."""

        @staticmethod
        def singleShot(delay_ms: int, callback: object) -> None:
            """Record the scheduled callback."""

            callbacks.append((delay_ms, callback))

    def callback() -> None:
        """No-op scheduled callback."""

    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_qt_timers.QtCore.QTimer",
        _TimerFactory,
    )

    startup_qt_timers.startup_single_shot(25, callback)

    assert callbacks == [(25, callback)]


def test_schedule_visible_startup_summary_uses_zero_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Visible startup summary scheduler should use the startup timer adapter."""

    scheduled: list[tuple[int, object]] = []

    def schedule(delay_ms: int, callback: object) -> None:
        """Record one scheduled visible-summary callback."""

        scheduled.append((delay_ms, callback))

    def callback() -> None:
        """No-op visible summary callback."""

    monkeypatch.setattr(startup_qt_timers, "startup_single_shot", schedule)

    startup_qt_timers.schedule_visible_startup_summary(callback)

    assert scheduled == [(0, callback)]


def test_create_startup_qt_scheduler_ports_groups_timer_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup scheduler ports should expose the concrete Qt timer adapters."""

    single_shot_calls: list[tuple[int, object]] = []
    visible_summary_calls: list[object] = []

    def single_shot(delay_ms: int, callback: object) -> None:
        """Record one single-shot scheduling request."""

        single_shot_calls.append((delay_ms, callback))

    def visible_summary(callback: object) -> None:
        """Record one visible-summary scheduling request."""

        visible_summary_calls.append(callback)

    def callback() -> None:
        """No-op scheduled callback."""

    monkeypatch.setattr(startup_qt_timers, "startup_single_shot", single_shot)
    monkeypatch.setattr(
        startup_qt_timers,
        "schedule_visible_startup_summary",
        visible_summary,
    )

    ports = startup_qt_timers.create_startup_qt_scheduler_ports()
    ports.single_shot(50, callback)
    ports.visible_summary(callback)

    assert single_shot_calls == [(50, callback)]
    assert visible_summary_calls == [callback]


def test_startup_qt_timers_imports_no_forbidden_boundaries() -> None:
    """Qt timer adapter should avoid UI widgets, infrastructure, and subprocess."""

    imported_modules = _imported_module_names(TIMER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_TIMER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_qtimer_adaptation() -> None:
    """Startup should not import or call QTimer directly."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    readiness_runtime_source = READINESS_RUNTIME_SOURCE.read_text(encoding="utf-8")

    assert "from PySide6.QtCore import QTimer" not in source
    assert "QTimer.singleShot" not in source
    assert "QTimer()" not in source
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "create_startup_qtimer" in readiness_runtime_source
    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_startup_qt_scheduler_ports()" not in source
    assert "create_startup_qt_scheduler_ports()" in support_graph_source
    assert "scheduler=self.startup_qt_schedulers.single_shot" in launch_source
    assert (
        "schedule_visible_summary=self.startup_qt_schedulers.visible_summary"
        in launch_source
    )
    assert "scheduler=startup_single_shot" not in source
    assert "schedule_visible_summary=schedule_visible_startup_summary" not in source
    assert "schedule_visible_summary=lambda" not in source


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
