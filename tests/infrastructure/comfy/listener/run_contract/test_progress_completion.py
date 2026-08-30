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

"""Verify run-loop terminal progress and completion publication."""

from __future__ import annotations

import json
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import (
    _build_callbacks,
    _build_request,
    _import_listener_module,
)


def test_run_reports_progress_and_completion(monkeypatch: MonkeyPatch) -> None:
    """Publish terminal workflow progress before completing node-less execution."""

    module = _import_listener_module(monkeypatch)
    callbacks, progress, _, _, failures, completed = _build_callbacks()
    messages = [
        json.dumps({"type": "progress", "data": {"node": "1", "value": 1, "max": 2}}),
        json.dumps({"type": "execution_cached", "data": {"nodes": ["2"]}}),
        json.dumps({"type": "executing", "data": {"node": "1", "prompt_id": "pid-1"}}),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class FakeWebSocket:
        """Serve the bounded progress sequence to the listener."""

        def connect(self, _url: str) -> None:
            """Accept the listener connection."""

        def send(self, _payload: str) -> None:
            """Accept the listener handshake payload."""

        def recv(self) -> str:
            """Return the next websocket message."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    workflow: JsonObject = {
        "1": {"class_type": "KSampler"},
        "2": {"class_type": "KSampler"},
    }
    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(output_dir=Path("."), workflow_payload=workflow),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"
    assert progress
    assert progress[-1].workflow_percent == 100.0
    assert progress[-1].sampler_percent is None
