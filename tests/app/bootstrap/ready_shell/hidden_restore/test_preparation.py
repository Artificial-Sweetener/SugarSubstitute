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

import pytest

from substitute.app.bootstrap import (
    ready_shell_controller,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)

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
