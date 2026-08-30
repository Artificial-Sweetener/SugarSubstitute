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

"""Verify metadata preview routing when Comfy omits a primary node ID."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.preview_contract_harness import (
    _binary_metadata_preview_image_message,
    _run_preview_visual_messages,
)


def test_run_uses_comfy_binary_preview_display_node_without_node_id(
    monkeypatch: MonkeyPatch,
) -> None:
    """Route metadata previews by display-node identity when primary ID is absent."""

    preview_events, output_events, failures = _run_preview_visual_messages(
        monkeypatch,
        messages=[
            _binary_metadata_preview_image_message(
                metadata={
                    "display_node_id": "preview-node",
                    "prompt_id": "pid-1",
                    "substitute": {
                        "schemaVersion": 1,
                        "workflowId": "wf-1",
                        "generationRunId": "run-1",
                        "clientId": "client",
                        "sourceKey": "wf-1:preview-node",
                        "sourceLabel": "Preview",
                    },
                }
            ),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert output_events == []
    assert len(preview_events) == 1
    assert preview_events[0].node_id == "preview-node"
    assert preview_events[0].metadata_node_id is None
    assert preview_events[0].display_node_id == "preview-node"
    assert preview_events[0].source_key == "wf-1:preview-node"
