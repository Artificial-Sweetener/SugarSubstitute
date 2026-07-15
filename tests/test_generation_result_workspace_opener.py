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

"""Tests for generation result workspace opening."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.application.generation import GenerationJobSnapshot
from substitute.presentation.shell.generation_result_workspace_opener import (
    legacy_generation_snapshot_for_job,
    open_generation_job_as_workflow_for_view,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "generation_result_workspace_opener.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


def test_opener_has_no_qt_or_workspace_controller_imports() -> None:
    """Generation result opener should stay free of Qt and controller imports."""

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


def test_open_generation_job_as_workflow_uses_legacy_captured_snapshot() -> None:
    """Older queue snapshots should route through file actions."""

    opened: list[dict[str, str]] = []
    snapshot = GenerationJobSnapshot(
        workflow_id="wf-a",
        workflow_name="Queued Recipe",
        sugar_script_text="# queued",
    )

    open_generation_job_as_workflow_for_view(
        generation_view=SimpleNamespace(
            generation_job_queue_service=SimpleNamespace(
                snapshot_for_job=lambda job_id: snapshot if job_id == "job-1" else None
            )
        ),
        file_actions=SimpleNamespace(
            open_sugar_snapshot_as_new_workflow=lambda **kwargs: opened.append(kwargs)
        ),
        job_id="job-1",
    )

    assert opened == [
        {
            "workflow_name": "Queued Recipe",
            "sugar_script_text": "# queued",
        }
    ]


def test_open_generation_job_as_workflow_uses_result_snapshot_materializer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Live result snapshots should restore result workspaces before fallback."""

    workspace = object()
    materialized: list[object] = []
    opened: list[dict[str, str]] = []

    def materialize_workspace(snapshot: object) -> tuple[str, ...]:
        """Record live workspace materialization and return restore warnings."""

        materialized.append(snapshot)
        return ("repair-a",)

    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.shell.generation_result_workspace_opener",
    )

    open_generation_job_as_workflow_for_view(
        generation_view=SimpleNamespace(
            generation_result_snapshot_service=SimpleNamespace(
                build_for_live_job=lambda job_id: SimpleNamespace(
                    snapshot=SimpleNamespace(workspace=workspace)
                    if job_id == "job-1"
                    else None,
                )
            ),
            generation_job_queue_service=SimpleNamespace(
                snapshot_for_job=lambda _job_id: pytest.fail(
                    "result snapshot path should not use Sugar fallback"
                )
            ),
            generation_result_workspace_materializer=SimpleNamespace(
                materialize_generation_result_workspace=materialize_workspace
            ),
        ),
        file_actions=SimpleNamespace(
            open_sugar_snapshot_as_new_workflow=lambda **kwargs: opened.append(kwargs)
        ),
        job_id="job-1",
    )

    assert materialized == [workspace]
    assert opened == []
    assert "Opened generation job with restore warning" in caplog.text
    assert "job_id=job-1" in caplog.text
    assert "repair=repair-a" in caplog.text


def test_open_generation_job_as_workflow_falls_back_when_live_snapshot_missing() -> (
    None
):
    """Missing live result snapshots should fall back to queued Sugar snapshots."""

    opened: list[dict[str, str]] = []
    snapshot = GenerationJobSnapshot(
        workflow_id="wf-a",
        workflow_name="Queued Recipe",
        sugar_script_text="# queued",
    )

    open_generation_job_as_workflow_for_view(
        generation_view=SimpleNamespace(
            generation_result_snapshot_service=SimpleNamespace(
                build_for_live_job=lambda _job_id: SimpleNamespace(snapshot=None)
            ),
            generation_result_workspace_materializer=SimpleNamespace(
                materialize_generation_result_workspace=lambda _snapshot: pytest.fail(
                    "missing live snapshot should not materialize"
                )
            ),
            generation_job_queue_service=SimpleNamespace(
                snapshot_for_job=lambda job_id: snapshot if job_id == "job-1" else None
            ),
        ),
        file_actions=SimpleNamespace(
            open_sugar_snapshot_as_new_workflow=lambda **kwargs: opened.append(kwargs)
        ),
        job_id="job-1",
    )

    assert opened == [
        {
            "workflow_name": "Queued Recipe",
            "sugar_script_text": "# queued",
        }
    ]


def test_legacy_generation_snapshot_for_job_rejects_unknown_snapshot_type() -> None:
    """Legacy fallback should return only generation job snapshots."""

    snapshot = legacy_generation_snapshot_for_job(
        generation_view=SimpleNamespace(
            generation_job_queue_service=SimpleNamespace(
                snapshot_for_job=lambda _job_id: object()
            )
        ),
        job_id="job-1",
    )

    assert snapshot is None
