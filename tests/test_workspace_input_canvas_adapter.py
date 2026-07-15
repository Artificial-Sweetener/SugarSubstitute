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

"""Tests for workspace Input canvas adapter ownership."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from substitute.presentation.shell.workspace_input_canvas_adapter import (
    handle_input_canvas_image_loaded_for_view,
    handle_input_image_changed_for_view,
    handle_input_image_clicked_for_view,
    handle_input_mask_changed_for_view,
    handle_input_mask_clicked_for_view,
    handle_mask_save_completed_for_view,
    input_canvas_presenter_for_view,
    materialize_loaded_cube_input_canvas_for_view,
    reconcile_active_input_canvas_image_for_view,
    refresh_active_mask_pickers_for_view,
    rehydrate_duplicated_workflow_input_canvas,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_input_canvas_adapter.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


def test_adapter_has_no_qt_or_controller_imports() -> None:
    """Input canvas adapter should remain free of concrete Qt/controller imports."""

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


def test_input_canvas_presenter_for_view_requires_presenter() -> None:
    """Presenter lookup should fail closed when the shell has no presenter."""

    with pytest.raises(RuntimeError, match="InputCanvasPresenter is required"):
        input_canvas_presenter_for_view(SimpleNamespace())


def test_input_canvas_intents_delegate_to_presenter() -> None:
    """Input canvas shell intents should route through presenter ownership."""

    calls: list[tuple[str, tuple[object, ...]]] = []
    presenter = SimpleNamespace(
        handle_input_image_changed=lambda *args: calls.append(("image_changed", args)),
        handle_input_image_clicked=lambda *args: calls.append(("image_clicked", args)),
        handle_input_canvas_image_loaded=lambda *args: calls.append(
            ("image_loaded", args)
        ),
        refresh_active_mask_pickers=lambda: calls.append(("mask_pickers", ())),
        handle_input_mask_changed=lambda *args: calls.append(("mask_changed", args)),
        handle_input_mask_clicked=lambda *args: calls.append(("mask_clicked", args)),
        handle_mask_save_completed=lambda *args: calls.append(("mask_saved", args)),
        reconcile_active_input_canvas_image=lambda: calls.append(("reconcile", ())),
        materialize_loaded_cube_input_canvas=lambda *args: calls.append(
            ("materialize", args)
        ),
    )
    view = SimpleNamespace(input_canvas_presenter=presenter)

    handle_input_image_changed_for_view(view, "CubeA", "ImageNode", "input.png")
    handle_input_image_clicked_for_view(view, "CubeA", "ImageNode", "input.png")
    handle_input_canvas_image_loaded_for_view(view, object(), "loaded.png")
    refresh_active_mask_pickers_for_view(view)
    handle_input_mask_changed_for_view(view, "CubeA", "MaskNode", "mask.png")
    handle_input_mask_clicked_for_view(view, "CubeA", "MaskNode", "mask.png")
    handle_mask_save_completed_for_view(view, "mask-id", "saved.png")
    reconcile_active_input_canvas_image_for_view(view)
    materialize_loaded_cube_input_canvas_for_view(view, "wf-a", "CubeA")

    assert calls[0] == ("image_changed", ("CubeA", "ImageNode", "input.png"))
    assert calls[1] == ("image_clicked", ("CubeA", "ImageNode", "input.png"))
    assert calls[2][0] == "image_loaded"
    assert calls[2][1][1] == "loaded.png"
    assert calls[3:] == [
        ("mask_pickers", ()),
        ("mask_changed", ("CubeA", "MaskNode", "mask.png")),
        ("mask_clicked", ("CubeA", "MaskNode", "mask.png")),
        ("mask_saved", ("mask-id", "saved.png")),
        ("reconcile", ()),
        ("materialize", ("wf-a", "CubeA")),
    ]


def test_rehydrate_duplicated_workflow_input_canvas_materializes_stack_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicated workflow rehydration should materialize each copied cube alias."""

    workflow = SimpleNamespace(stack_order=["CubeA", "CubeB"])
    materialized: list[tuple[str, str]] = []
    scheduled_callbacks: list[object] = []
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.workspace_input_canvas_adapter",
    )

    rehydrate_duplicated_workflow_input_canvas(
        workflow_session_service=SimpleNamespace(
            get_workflow=lambda workflow_id: (
                workflow if workflow_id == "wf-copy" else None
            )
        ),
        workflow_id="wf-copy",
        materialize_loaded_cube_input_canvas=lambda workflow_id, cube_alias: (
            materialized.append((workflow_id, cube_alias))
        ),
        schedule_next=scheduled_callbacks.append,
    )
    while scheduled_callbacks:
        callback = scheduled_callbacks.pop(0)
        assert callable(callback)
        callback()

    assert materialized == [("wf-copy", "CubeA"), ("wf-copy", "CubeB")]
    assert "Workflow duplicate input canvas rehydration started" in caplog.text
    assert "Workflow duplicate input canvas cube rehydration started" in caplog.text
    assert "Workflow duplicate input canvas cube rehydration completed" in caplog.text
    assert "Workflow duplicate input canvas rehydration completed" in caplog.text


def test_rehydrate_duplicated_workflow_input_canvas_missing_workflow_logs_skip(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing duplicated workflow state should fail closed without materializing."""

    materialized: list[tuple[str, str]] = []
    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.shell.workspace_input_canvas_adapter",
    )

    rehydrate_duplicated_workflow_input_canvas(
        workflow_session_service=SimpleNamespace(
            get_workflow=lambda _workflow_id: None
        ),
        workflow_id="missing",
        materialize_loaded_cube_input_canvas=lambda workflow_id, cube_alias: (
            materialized.append((workflow_id, cube_alias))
        ),
        schedule_next=lambda callback: callback(),
    )

    assert materialized == []
    assert (
        "Workflow duplicate input canvas rehydration skipped because workflow was missing"
        in caplog.text
    )
