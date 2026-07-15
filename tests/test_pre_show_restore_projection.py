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

"""Tests for pre-show restore projection startup coordination."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

from substitute.app.bootstrap import pre_show_restore_projection
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionStarter,
    PreShowRestoreProjectionState,
    start_pre_show_restore_projection_if_available,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRE_SHOW_RESTORE_PROJECTION_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "pre_show_restore_projection.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
FORBIDDEN_PRE_SHOW_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_pre_show_restore_projection_skips_when_runtime_is_not_prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime preparation should gate pre-show projection startup."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    reveals: list[str] = []
    scheduled: list[tuple[int, Callable[[], None]]] = []
    state = PreShowRestoreProjectionState()

    deferred = start_pre_show_restore_projection_if_available(
        state=state,
        hidden_restore_runtime_prepared=False,
        start_projection=_starter_that_fails,
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
    assert events[0] == (
        "main_shell.pre_show_restore_projection.skip",
        {
            "reason": "runtime_not_prepared",
            "cache_artifact_present": False,
            "restored_active_workflow_id": "wf-a",
            "route": "ready",
        },
    )


def test_pre_show_restore_projection_waits_for_async_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Started pre-show projection should defer shell reveal until completion."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    completions: list[Callable[[], None]] = []
    reveals: list[str] = []
    scheduled: list[tuple[int, Callable[[], None]]] = []
    state = PreShowRestoreProjectionState()

    deferred = start_pre_show_restore_projection_if_available(
        state=state,
        hidden_restore_runtime_prepared=True,
        start_projection=_starter_that_captures(completions),
        provisional_restore_projection=object(),
        fallback_workflow_id="wf-a",
        startup_cancelled=lambda: False,
        reveal_main_window=lambda: reveals.append("reveal"),
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
        trace_fields=lambda: {"route": "ready"},
        timeout_ms=25,
    )

    assert deferred is True
    assert state.pending is True
    assert reveals == []
    assert len(completions) == 1
    assert len(scheduled) == 1
    assert scheduled[0][0] == 25
    assert events[0][0] == "main_shell.pre_show_restore_projection.start"
    assert events[0][1]["projection_source"] == "cache"
    assert events[-1][0] == "main_shell.pre_show_restore_projection.waiting"

    completions[0]()

    assert state.pending is False
    assert state.completion_handled is True
    assert reveals == ["reveal"]
    assert events[-1] == (
        "main_shell.pre_show_restore_projection.complete",
        {"reason": "surface_complete", "route": "ready"},
    )


def test_pre_show_restore_projection_timeout_reveals_and_late_completion_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout should fail open and suppress a later projection completion."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    completions: list[Callable[[], None]] = []
    scheduled: list[tuple[int, Callable[[], None]]] = []
    reveals: list[str] = []
    state = PreShowRestoreProjectionState()

    deferred = start_pre_show_restore_projection_if_available(
        state=state,
        hidden_restore_runtime_prepared=True,
        start_projection=_starter_that_captures(completions),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled=lambda: False,
        reveal_main_window=lambda: reveals.append("reveal"),
        scheduler=lambda delay, callback: scheduled.append((delay, callback)),
        trace_fields=lambda: {"route": "ready"},
        timeout_ms=10,
    )

    assert deferred is True
    scheduled[0][1]()
    completions[0]()

    assert reveals == ["reveal"]
    assert state.pending is False
    assert (
        "main_shell.pre_show_restore_projection.late_completion",
        {"reason": "surface_complete", "route": "ready"},
    ) in events


def test_pre_show_restore_projection_completion_after_cancel_does_not_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup cancellation should clear the pending projection without reveal."""

    events: list[tuple[str, dict[str, object]]] = []
    _patch_trace(monkeypatch, events)
    completions: list[Callable[[], None]] = []
    reveals: list[str] = []
    state = PreShowRestoreProjectionState()

    start_pre_show_restore_projection_if_available(
        state=state,
        hidden_restore_runtime_prepared=True,
        start_projection=_starter_that_captures(completions),
        provisional_restore_projection=None,
        fallback_workflow_id="wf-a",
        startup_cancelled=lambda: True,
        reveal_main_window=lambda: reveals.append("reveal"),
        scheduler=lambda _delay, _callback: None,
        trace_fields=lambda: {"route": "ready"},
    )
    completions[0]()

    assert state.pending is False
    assert reveals == []
    assert events[-1] == (
        "main_shell.pre_show_restore_projection.cancelled",
        {"reason": "surface_complete", "route": "ready"},
    )


def test_pre_show_restore_projection_imports_no_forbidden_boundaries() -> None:
    """Pre-show restore projection orchestration should stay Qt-free."""

    imported_modules = _imported_module_names(PRE_SHOW_RESTORE_PROJECTION_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_PRE_SHOW_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_pre_show_restore_projection_logic() -> None:
    """Startup should delegate pre-show projection timeout/completion sequencing."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    ready_shell_controller_source = READY_SHELL_CONTROLLER_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "PRE_SHOW_RESTORE_PROJECTION_TIMEOUT_MS" not in source
    assert "def finish_pre_show_projection" not in source
    assert "def timeout_pre_show_projection" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task(" not in source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "ReadyShellShowGateTask(" not in source
    assert "try_reveal_ready_shell(" not in source
    assert "start_ready_shell_pre_show_restore_projection(" not in source
    assert (
        "start_ready_shell_pre_show_restore_projection("
        in ready_shell_controller_source
    )
    assert "start_pre_show_restore_projection_if_available(" not in source
    assert "PreShowRestoreProjectionState()" not in source
    assert "managed_ready_state.pre_show_restore_projection_state" not in source


def _starter_that_captures(
    completions: list[Callable[[], None]],
) -> PreShowRestoreProjectionStarter:
    """Return a projection starter that captures completion callbacks."""

    def start_projection(
        artifact: object | None,
        *,
        fallback_workflow_id: str,
        on_complete: Callable[[], None],
    ) -> bool:
        """Record one completion callback."""

        _ = artifact
        _ = fallback_workflow_id
        completions.append(on_complete)
        return True

    return start_projection


def _starter_that_fails(
    artifact: object | None,
    *,
    fallback_workflow_id: str,
    on_complete: Callable[[], None],
) -> bool:
    """Return a projection start failure."""

    _ = artifact
    _ = fallback_workflow_id
    _ = on_complete
    return False


def _patch_trace(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple[str, dict[str, object]]],
) -> None:
    """Patch trace recording for deterministic assertions."""

    def trace(event_name: str, **fields: object) -> None:
        """Record one trace event."""

        events.append((event_name, fields))

    monkeypatch.setattr(pre_show_restore_projection, "trace_mark", trace)


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
