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

"""Tests for WorkspaceController canvas action facade behavior."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tests.workspace_controller_test_support import import_workspace_controller_module


def test_update_canvas_callback_submits_to_output_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Controller canvas actions should expose output pipeline delegation."""

    mod = import_workspace_controller_module(monkeypatch)

    submitted: list[object] = []
    view = SimpleNamespace(
        output_image_pipeline=SimpleNamespace(
            submit_legacy_output_update=lambda update: submitted.append(update)
        )
    )
    controller = mod.WorkspaceController(view)

    image_path = tmp_path / "007_cube_preview.png"
    image_path.write_text("x")
    workflow_payload = {"N1": {"_meta": {"title": "CubeA.KSampler"}}}

    controller.canvas_actions.update_canvas_callback(
        workflow_id="wf-1",
        workflow=workflow_payload,
        file_path=str(image_path),
        node_id="N1",
        source_key="wf-1:ws-node",
        source_label="Output Source",
    )

    assert len(submitted) == 1
    update = cast(Any, submitted[0])
    assert update.workflow_id == "wf-1"
    assert update.workflow_payload == workflow_payload
    assert update.file_path == image_path
    assert update.node_id == "N1"
    assert update.source_key == "wf-1:ws-node"
    assert update.source_label == "Output Source"
