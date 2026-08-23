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

"""Verify listener preview identity fails closed before visual publication."""

from __future__ import annotations

import json

from _pytest.monkeypatch import MonkeyPatch

from tests.infrastructure.comfy.listener.preview_contract_harness import (
    _binary_metadata_preview_image_message,
    _run_preview_visual_messages,
)


def test_run_rejects_stale_and_mismatched_preview_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    """Reject stale prompt, workflow, generation, and client preview identities."""

    def preview_with_identity(**identity_updates: object) -> bytes:
        """Build one preview frame with a targeted Substitute identity mutation."""

        identity: dict[str, object] = {
            "schemaVersion": 1,
            "workflowId": "wf-1",
            "generationRunId": "run-1",
            "clientId": "client",
            "sourceKey": "wf-1:preview-node",
            "sourceLabel": "Preview",
        }
        identity.update(identity_updates)
        return _binary_metadata_preview_image_message(
            metadata={
                "node_id": "preview-node",
                "prompt_id": "pid-1",
                "substitute": identity,
            }
        )

    preview_events, output_events, failures = _run_preview_visual_messages(
        monkeypatch,
        messages=[
            _binary_metadata_preview_image_message(
                metadata={
                    "node_id": "preview-node",
                    "prompt_id": "other-prompt",
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
            preview_with_identity(workflowId="wf-other"),
            preview_with_identity(generationRunId="run-other"),
            preview_with_identity(clientId="client-other"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert output_events == []
    assert preview_events == []


def test_run_rejects_preview_metadata_without_normalized_source_node(
    monkeypatch: MonkeyPatch,
) -> None:
    """Reject preview metadata lacking a normalized source-node identifier."""

    preview_events, output_events, failures = _run_preview_visual_messages(
        monkeypatch,
        messages=[
            _binary_metadata_preview_image_message(
                metadata={
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
    assert preview_events == []
