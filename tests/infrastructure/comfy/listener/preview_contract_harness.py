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

"""Provide deterministic binary preview runs for listener preview contracts."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from substitute.application.ports import (
    ListenerCompleted,
    ListenerFailure,
    OutputImageUpdate,
    PreviewImageUpdate,
)
from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import (
    _build_callbacks,
    _build_request,
    _import_listener_module,
)


def _binary_preview_image_message(
    payload: bytes = b"fake-preview-payload",
    *,
    image_type: int = 1,
) -> bytes:
    """Build one Comfy PREVIEW_IMAGE binary websocket frame."""

    return struct.pack(">II", 1, image_type) + payload


def _binary_metadata_preview_image_message(
    payload: bytes = b"fake-preview-payload",
    *,
    metadata: dict[str, object] | None = None,
    source_key: str | None = None,
    source_label: str | None = None,
) -> bytes:
    """Build one Comfy preview frame carrying Substitute source metadata."""

    metadata_payload_object = dict(metadata or {})
    if "substitute" not in metadata_payload_object:
        node_id = metadata_payload_object.get("node_id")
        prompt_id = metadata_payload_object.get("prompt_id")
        if isinstance(node_id, str) and isinstance(prompt_id, str):
            metadata_payload_object["substitute"] = {
                "schemaVersion": 1,
                "workflowId": "wf-1",
                "generationRunId": "run-1",
                "clientId": "client",
                "sourceKey": source_key or f"wf-1:{node_id}",
                "sourceLabel": source_label or node_id,
            }
    metadata_payload = json.dumps(metadata_payload_object).encode("utf-8")
    return struct.pack(">II", 4, len(metadata_payload)) + metadata_payload + payload


def _run_preview_visual_messages(
    monkeypatch: MonkeyPatch,
    *,
    messages: list[object],
) -> tuple[list[PreviewImageUpdate], list[OutputImageUpdate], list[ListenerFailure]]:
    """Run preview messages and collect their visual callback contracts."""

    preview_events, output_events, failures, _completed = _run_preview_messages(
        monkeypatch,
        messages=messages,
        workflow_payload={"preview-node": {"class_type": "VAEDecode"}},
    )
    return preview_events, output_events, failures


def _run_preview_messages(
    monkeypatch: MonkeyPatch,
    *,
    messages: list[object],
    workflow_payload: JsonObject,
    workflow_id: str = "wf-1",
) -> tuple[
    list[PreviewImageUpdate],
    list[OutputImageUpdate],
    list[ListenerFailure],
    list[ListenerCompleted],
]:
    """Run one preview workflow and collect all visual terminal contracts."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, output_events, failures, completed = (
        _build_callbacks()
    )

    class PreviewImageDouble:
        """Provide decoded RGBA preview bytes at a fixed portable size."""

        width = 32
        height = 16

        def convert(self, _mode: str) -> "PreviewImageDouble":
            """Return the deterministic image surface."""

            return self

        def tobytes(self, *_args: object) -> bytes:
            """Return opaque RGBA bytes for the configured dimensions."""

            return b"\x00" * self.width * self.height * 4

    class FakeWebSocket:
        """Serve deterministic preview frames."""

        def connect(self, _url: str) -> None:
            """Accept listener connection."""

        def send(self, _payload: str) -> None:
            """Accept listener handshake payload."""

        def recv(self) -> object:
            """Return the next prescribed listener event."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
    monkeypatch.setattr(module.Image, "open", lambda _stream: PreviewImageDouble())
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload=workflow_payload,
            workflow_id=workflow_id,
        ),
        callbacks=callbacks,
    )
    runnable.run()
    return preview_events, output_events, failures, completed
