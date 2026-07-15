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

"""Tests for shell workflow duplicate controller ownership."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.presentation.shell.workflow_duplicate_controller import (
    duplicate_workflow_tab_for_view,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workflow_duplicate_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


def test_duplicate_controller_has_no_qt_or_workspace_controller_imports() -> None:
    """Duplicate controller should remain free of Qt and controller imports."""

    tree = ast.parse(SOURCE_PATH.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = {
        name for name in imported if name.startswith(FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden == set()


def test_duplicate_workflow_tab_clones_registers_and_schedules_rehydration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicating a workflow tab should clone state and schedule rehydration."""

    workflow = SimpleNamespace(cubes={"CubeA": object()}, stack_order=["CubeA"])
    cloned_workflow = SimpleNamespace(stack_order=["CubeA", "CubeB"], cubes={})
    duplicate_calls: list[object] = []
    workspace_calls: list[dict[str, object]] = []
    materialized: list[tuple[str, str]] = []
    scheduled_callbacks: list[object] = []

    def duplicate_workflow(candidate: object) -> object:
        """Record the clone candidate and return cloned workflow state."""

        duplicate_calls.append(candidate)
        return cloned_workflow

    def register_workflow(
        source_workflow_id: str,
        cloned: object,
        *,
        base_label: str,
    ) -> str:
        """Record the shell registration request and return a duplicate id."""

        workspace_calls.append(
            {
                "source_workflow_id": source_workflow_id,
                "cloned_workflow": cloned,
                "base_label": base_label,
            }
        )
        return "wf-copy"

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_duplicate_controller",
    )

    duplicate_workflow_tab_for_view(
        view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(
                get_workflow=lambda workflow_id: (
                    workflow
                    if workflow_id == "wf-a"
                    else cloned_workflow
                    if workflow_id == "wf-copy"
                    else None
                )
            ),
            workflow_tabbar=SimpleNamespace(
                itemMap={"wf-a": SimpleNamespace(text=lambda: "Recipe")}
            ),
        ),
        workflow_duplicate_service=SimpleNamespace(
            duplicate_workflow=duplicate_workflow
        ),
        workflow_workspace=SimpleNamespace(duplicate_workflow=register_workflow),
        workflow_id="wf-a",
        materialize_loaded_cube_input_canvas=lambda workflow_id, cube_alias: (
            materialized.append((workflow_id, cube_alias))
        ),
        schedule_rehydration=scheduled_callbacks.append,
    )

    assert duplicate_calls == [workflow]
    assert workspace_calls == [
        {
            "source_workflow_id": "wf-a",
            "cloned_workflow": cloned_workflow,
            "base_label": "Recipe",
        }
    ]
    assert materialized == []
    assert len(scheduled_callbacks) == 1
    callback = scheduled_callbacks.pop(0)
    assert callable(callback)
    callback()
    while scheduled_callbacks:
        next_callback = scheduled_callbacks.pop(0)
        assert callable(next_callback)
        next_callback()
    assert materialized == [("wf-copy", "CubeA"), ("wf-copy", "CubeB")]
    assert "Workflow duplicate requested" in caplog.text
    assert "Workflow duplicate clone phase completed" in caplog.text
    assert "Workflow duplicate registration completed" in caplog.text
    assert "Workflow duplicate input canvas rehydration scheduled" in caplog.text
    assert "Workflow duplicate request completed" in caplog.text


def test_duplicate_workflow_tab_missing_workflow_is_noop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicating a missing workflow should not clone or register UI state."""

    clone_calls: list[object] = []
    workspace_calls: list[object] = []
    scheduled_callbacks: list[object] = []
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workflow_duplicate_controller",
    )

    duplicate_workflow_tab_for_view(
        view=SimpleNamespace(
            workflow_session_service=SimpleNamespace(
                get_workflow=lambda _workflow_id: None
            ),
            workflow_tabbar=SimpleNamespace(itemMap={}),
        ),
        workflow_duplicate_service=SimpleNamespace(
            duplicate_workflow=lambda candidate: clone_calls.append(candidate)
        ),
        workflow_workspace=SimpleNamespace(
            duplicate_workflow=lambda *_args, **_kwargs: workspace_calls.append(
                "duplicate"
            )
        ),
        workflow_id="missing",
        materialize_loaded_cube_input_canvas=lambda *_args: None,
        schedule_rehydration=scheduled_callbacks.append,
    )

    assert clone_calls == []
    assert workspace_calls == []
    assert scheduled_callbacks == []
    assert (
        "Workflow duplicate skipped because source workflow was missing" in caplog.text
    )
    assert "source_workflow_id=missing" in caplog.text
