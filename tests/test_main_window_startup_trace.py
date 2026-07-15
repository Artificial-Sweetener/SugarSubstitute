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

"""Tests for MainWindow startup trace helpers."""

from __future__ import annotations

import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

from substitute.presentation.shell.main_window_startup_trace import (
    mark_startup_milestone,
    snapshot_trace_fields,
    startup_phase,
    workflow_snapshot_trace_fields,
)

_FORBIDDEN_IMPORT_ROOTS = {
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.app",
    "substitute.infrastructure",
}


def test_startup_phase_uses_timer_phase_context_when_available() -> None:
    """Delegate startup phase timing to a duck-typed timer."""

    events: list[str] = []

    class _Timer:
        """Record phase context entry and exit."""

        @contextmanager
        def phase(self, name: str) -> Iterator[None]:
            """Record one named phase context."""

            events.append(f"enter:{name}")
            yield
            events.append(f"exit:{name}")

    with startup_phase(_Timer(), "mainwindow.test"):
        events.append("inside")

    assert events == ["enter:mainwindow.test", "inside", "exit:mainwindow.test"]


def test_startup_phase_is_noop_without_timer_phase() -> None:
    """Provide a no-op context when no startup timer is available."""

    with startup_phase(None, "mainwindow.test"):
        value = "inside"

    assert value == "inside"


def test_mark_startup_milestone_uses_timer_mark_when_available() -> None:
    """Delegate startup milestone recording to a duck-typed timer."""

    marks: list[str] = []
    timer = SimpleNamespace(mark=marks.append)

    mark_startup_milestone(timer, "minimum_shell_ready")

    assert marks == ["minimum_shell_ready"]


def test_snapshot_trace_fields_project_compact_workspace_context() -> None:
    """Return prompt-safe workspace snapshot context for startup traces."""

    snapshot = SimpleNamespace(
        workflows=(object(), object()),
        active_workflow_id="wf-1",
        active_route="editor",
        shell_layout=object(),
    )

    assert snapshot_trace_fields(snapshot) == {
        "workspace_present": True,
        "workflow_count": 2,
        "active_workflow_id": "wf-1",
        "active_route": "editor",
        "shell_layout_present": True,
    }


def test_workflow_snapshot_trace_fields_project_compact_workflow_context() -> None:
    """Return prompt-safe workflow snapshot context for startup traces."""

    workflow = SimpleNamespace(cubes={"a": object(), "b": object()}, stack_order=("a",))
    snapshot = SimpleNamespace(
        workflow=workflow,
        workflow_id="wf-1",
        tab_label="Tab",
        active_cube_alias="a",
        input_images=(object(),),
        input_masks=(),
        output_images=(object(), object()),
    )

    assert workflow_snapshot_trace_fields(snapshot) == {
        "workflow_id": "wf-1",
        "tab_label": "Tab",
        "active_cube_alias": "a",
        "cube_count": 2,
        "stack_order_length": 1,
        "input_image_count": 1,
        "input_mask_count": 0,
        "output_image_count": 2,
    }


def test_main_window_startup_trace_has_no_qt_or_adapter_imports() -> None:
    """Keep startup trace field projection independent of Qt and adapters."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "presentation"
        / "shell"
        / "main_window_startup_trace.py"
    )
    syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    offenders = sorted(
        imported_module
        for imported_module in imported_modules
        if any(
            imported_module == forbidden_root
            or imported_module.startswith(f"{forbidden_root}.")
            for forbidden_root in _FORBIDDEN_IMPORT_ROOTS
        )
    )

    assert offenders == []
