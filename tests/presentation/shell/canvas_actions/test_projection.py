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

"""Test workspace output projection actions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from substitute.application.ports import OutputImageUpdate

from tests.presentation.shell.canvas_actions.support import (
    _import_module,
)


def test_update_canvas_callback_submits_output_update_to_pipeline(
    tmp_path: Path,
) -> None:
    """Generated output callbacks should delegate to the async output pipeline."""

    mod = _import_module()

    submitted: list[OutputImageUpdate] = []
    image_path = tmp_path / "007_output.png"
    image_path.write_text("x")
    view = SimpleNamespace(
        output_image_pipeline=SimpleNamespace(
            submit_legacy_output_update=lambda update: submitted.append(update)
        ),
    )
    actions = mod.WorkspaceCanvasActions(view)

    actions.update_canvas_callback(
        workflow_id="wf-1",
        workflow={"save-node": {"_meta": {"title": "LocalCube.CubeOutput"}}},
        file_path=str(image_path),
        node_id="save-node",
        source_key="wf-1:websocket-node",
        source_label="Resolved Output",
        scene_run_id="run-1",
        scene_key="portrait",
        scene_title="Portrait",
        scene_order=0,
        scene_count=2,
    )

    assert len(submitted) == 1
    update = submitted[0]
    assert update.workflow_id == "wf-1"
    assert update.workflow_payload == {
        "save-node": {"_meta": {"title": "LocalCube.CubeOutput"}}
    }
    assert update.file_path == image_path
    assert update.node_id == "save-node"
    assert update.source_key == "wf-1:websocket-node"
    assert update.source_label == "Resolved Output"
    assert update.scene_run_id == "run-1"
    assert update.scene_key == "portrait"
    assert update.scene_title == "Portrait"
    assert update.scene_order == 0
    assert update.scene_count == 2


def test_output_image_preparation_failure_reports_error(
    tmp_path: Path,
) -> None:
    """Generated output load failures should use the unified error modal presenter."""

    mod = _import_module()
    from substitute.presentation.shell.output_image_commit_pipeline import (
        FailedOutputImagePreparation,
        OutputImageCommitRequest,
    )

    image_path = tmp_path / "missing.png"
    reports: list[Any] = []
    critical_calls: list[object] = []
    actions = mod.WorkspaceCanvasActions(
        SimpleNamespace(),
        error_presenter=SimpleNamespace(
            show_error_report=lambda report: reports.append(report)
        ),
    )

    actions.handle_output_image_preparation_failed(
        FailedOutputImagePreparation(
            request=OutputImageCommitRequest(
                workflow_id="wf-1",
                file_path=image_path,
                node_id="save-node",
                node_meta_title="",
                workflow_name="Workflow",
                source_key="wf-1:websocket-node",
                source_label="Resolved Output",
                scene_run_id="run-1",
                scene_key="portrait",
                scene_title="Portrait",
                scene_order=0,
                scene_count=2,
            ),
            message="failed",
        ),
        message_box=SimpleNamespace(
            critical=lambda *args, **_kwargs: critical_calls.append(args)
        ),
    )

    assert critical_calls == []
    report = reports[0]
    assert report.kind.value == "substitute_internal"
    assert report.title == "Generated image load failed"
    assert report.stage == "canvas"
    assert report.workflow_id == "wf-1"
    assert report.operation_context.operation == "load_generated_output_image"
    assert report.operation_context.node_id == "save-node"
    assert report.operation_context.path == str(image_path)
    assert report.operation_context.values["source_key"] == "wf-1:websocket-node"
    assert report.operation_context.values["scene_key"] == "portrait"
