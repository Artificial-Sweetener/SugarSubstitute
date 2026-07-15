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

"""Tests for ready-shell GUI startup task queue ownership."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTasks,
    enqueue_ready_shell_startup_tasks,
    schedule_ready_shell_startup_tasks,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
READY_SHELL_TASKS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_startup_tasks.py"
)
FORBIDDEN_READY_SHELL_TASK_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_ready_shell_startup_tasks_are_queued_in_canonical_order() -> None:
    """Ready-shell GUI tasks should retain the observed startup ordering."""

    calls: list[str] = []
    queue = _Queue(calls)

    schedule_ready_shell_startup_tasks(
        queue=queue,
        activate_target=lambda: calls.append("run:activate_target"),
        start_readiness_timer=lambda: calls.append("run:start_readiness_timer"),
        build_main_window=lambda: calls.append("run:build_main_window"),
        wire_metadata_bridge=lambda: calls.append("run:wire_metadata_bridge"),
        warm_prompt_editor_gui=lambda: calls.append("run:warm_prompt_editor_gui"),
        prehydrate_initial_workspace=lambda: calls.append(
            "run:prehydrate_initial_workspace"
        ),
        mark_minimum_shell_ready=lambda: calls.append("run:mark_minimum_shell_ready"),
    )

    assert calls == [
        "add:activate_target",
        "add:start_readiness_timer",
        "add:build_main_window",
        "add:wire_metadata_bridge",
        "add:warm_prompt_editor_gui",
        "add:prehydrate_initial_workspace",
        "add:mark_minimum_shell_ready",
        "start",
        "run:activate_target",
        "run:start_readiness_timer",
        "run:build_main_window",
        "run:wire_metadata_bridge",
        "run:warm_prompt_editor_gui",
        "run:prehydrate_initial_workspace",
        "run:mark_minimum_shell_ready",
    ]


def test_ready_shell_startup_tasks_import_no_forbidden_boundaries() -> None:
    """Ready-shell task ordering should remain free of concrete UI and IO adapters."""

    imported_modules = _imported_module_names(READY_SHELL_TASKS_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_SHELL_TASK_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_enqueue_ready_shell_startup_tasks_accepts_explicit_task_bundle() -> None:
    """Ready-shell task owner should still expose the explicit ordered bundle port."""

    calls: list[str] = []

    enqueue_ready_shell_startup_tasks(
        _Queue(calls),
        ReadyShellStartupTasks(
            activate_target=lambda: calls.append("run:activate_target"),
            start_readiness_timer=lambda: calls.append("run:start_readiness_timer"),
            build_main_window=lambda: calls.append("run:build_main_window"),
            wire_metadata_bridge=lambda: calls.append("run:wire_metadata_bridge"),
            warm_prompt_editor_gui=lambda: calls.append("run:warm_prompt_editor_gui"),
            prehydrate_initial_workspace=lambda: calls.append(
                "run:prehydrate_initial_workspace"
            ),
            mark_minimum_shell_ready=lambda: calls.append(
                "run:mark_minimum_shell_ready"
            ),
        ),
    )

    assert calls[:8] == [
        "add:activate_target",
        "add:start_readiness_timer",
        "add:build_main_window",
        "add:wire_metadata_bridge",
        "add:warm_prompt_editor_gui",
        "add:prehydrate_initial_workspace",
        "add:mark_minimum_shell_ready",
        "start",
    ]


def test_startup_facade_delegates_ready_shell_task_ordering() -> None:
    """Startup should not own the ready-shell GUI queue task-name sequence."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "managed_ready_launch.schedule_startup_tasks(" in launch_source
    assert "managed_ready_runtime.schedule_startup_tasks(" not in source
    assert "schedule_ready_shell_controller_startup_tasks(" not in source
    assert "schedule_ready_shell_startup_tasks(" not in source
    assert "ReadyShellStartupTasks(" not in source
    assert "enqueue_ready_shell_startup_tasks(" not in source
    assert 'gui_queue.add("activate_target"' not in source
    assert 'gui_queue.add("start_readiness_timer"' not in source
    assert 'gui_queue.add("build_main_window"' not in source
    assert 'gui_queue.add("wire_metadata_bridge"' not in source
    assert 'gui_queue.add("warm_prompt_editor_gui"' not in source
    assert 'gui_queue.add("prehydrate_initial_workspace"' not in source
    assert 'gui_queue.add("mark_minimum_shell_ready"' not in source


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


class _Queue:
    """Record queued tasks and run them when started."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records and an empty task queue."""

        self._calls = calls
        self._tasks: list[Callable[[], None]] = []

    def add(self, name: str, callback: Callable[[], None]) -> None:
        """Record and append one task."""

        self._calls.append(f"add:{name}")
        self._tasks.append(callback)

    def start(self) -> None:
        """Record queue start and execute queued callbacks."""

        self._calls.append("start")
        for task in self._tasks:
            task()
