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

"""Prove compatibility with workspace payloads emitted by released writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from substitute.application.workspace_state import SnapshotNormalizationService
from substitute.domain.workspace_snapshot.codecs import (
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)

_FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures"
    / "workspace_snapshots"
    / "v0.9.0-workflow.json"
)
_PROMPT = "[SEP|left] α é 🧁 שלום"


def test_v090_writer_payload_preserves_identity_graph_prompt_and_missing_assets() -> (
    None
):
    """The exact v0.9.0 writer shape must decode without losing authored state."""

    payload = cast(dict[str, object], json.loads(_FIXTURE.read_text(encoding="utf-8")))

    decoded = workspace_snapshot_from_json(payload)
    result = SnapshotNormalizationService().normalize(decoded)
    workflow_snapshot = result.snapshot.workflows[0]
    cube = workflow_snapshot.workflow.cubes["Region"]
    nodes = cast(dict[str, object], cube.buffer["nodes"])
    prompt_node = cast(dict[str, object], nodes["prompt"])
    prompt_inputs = cast(dict[str, object], prompt_node["inputs"])

    assert workflow_snapshot.workflow_id == "workflow_57157"
    assert result.snapshot.tab_order == ("workflow_57157",)
    assert len(workflow_snapshot.input_images) == 1
    assert len(workflow_snapshot.input_masks) == 1
    assert workflow_snapshot.input_masks[0].mask_id == (
        "22222222-2222-4222-8222-222222222222"
    )
    assert cast(str, prompt_inputs["text"]).encode("utf-8") == _PROMPT.encode("utf-8")
    assert any("Retained unresolved input mask" in item for item in result.warnings)

    redecoded = workspace_snapshot_from_json(
        workspace_snapshot_to_json(result.snapshot)
    )
    assert redecoded.workflows[0].workflow_id == "workflow_57157"
    assert redecoded.workflows[0].input_masks == workflow_snapshot.input_masks
