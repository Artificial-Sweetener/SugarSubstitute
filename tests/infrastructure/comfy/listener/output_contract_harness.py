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

"""Provide deterministic artifact-persistence runs for listener output contracts."""

from __future__ import annotations

import json
import struct
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any, Literal, cast

from _pytest.monkeypatch import MonkeyPatch

from substitute.application.ports import (
    ListenerCompleted,
    ListenerFailure,
    OutputImageUpdate,
    OutputSavePlan,
)
from substitute.domain.common import JsonObject
from substitute.infrastructure.comfy import (
    listener_output_pipeline,
    output_image_persistence,
)
from tests.infrastructure.comfy.listener.contract_harness import (
    _build_callbacks,
    _build_request,
    _import_listener_module,
)


def _run_cube_output_visual_messages(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    *,
    messages: list[object],
    workflow_payload: JsonObject | None = None,
    fetched_artifacts: list[object] | None = None,
    saved_paths: list[str] | None = None,
    png_text: list[tuple[str, str]] | None = None,
    output_run_number: int | None = None,
    output_save_plan: OutputSavePlan | None = None,
    bucket_run_number: Callable[..., int] | None = None,
    fallback_job_started_at: datetime | None = None,
    workflow_name: str = "My Workflow",
) -> tuple[list[OutputImageUpdate], list[ListenerFailure], list[ListenerCompleted]]:
    """Run cube-output messages against deterministic artifact persistence."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, completed = _build_callbacks()
    persistence: Any = output_image_persistence
    monkeypatch.setattr(
        persistence,
        "get_next_bucket_run_number",
        bucket_run_number or (lambda *_args: 7),
    )
    if fallback_job_started_at is not None:
        fixed_started_at = fallback_job_started_at

        class FixedDateTime:
            """Provide the controlled default-plan construction clock."""

            @staticmethod
            def now() -> datetime:
                """Return the fixed local output-plan timestamp."""

                return fixed_started_at

        monkeypatch.setattr(listener_output_pipeline, "datetime", FixedDateTime)

    class ImageDouble:
        """Provide a fixed-size image surface for persisted output artifacts."""

        width = 640
        height = 480

        def __enter__(self) -> "ImageDouble":
            """Return the opened image surface."""

            return self

        def __exit__(
            self,
            _exception_type: object,
            _exception: object,
            _traceback: object,
        ) -> Literal[False]:
            """Keep persistence exceptions unhandled."""

            return False

        def save(self, path: str | Path, pnginfo: object = None) -> None:
            """Persist deterministic content and record the requested destination."""

            _ = pnginfo
            Path(path).write_bytes(b"persisted-png")
            if saved_paths is not None:
                saved_paths.append(str(path))

    class PngInfoDouble:
        """Accept metadata added by the output encoder."""

        def add_text(self, key: str, value: str) -> None:
            """Record image metadata requested by the output encoder."""

            if png_text is not None:
                png_text.append((key, value))

    class FakeWebSocket:
        """Serve deterministic listener messages."""

        def connect(self, _url: str) -> None:
            """Accept listener connection."""

        def send(self, _payload: str) -> None:
            """Accept listener handshake payload."""

        def recv(self) -> object:
            """Return the next prescribed listener event."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    monkeypatch.setattr(persistence.Image, "open", lambda _stream: ImageDouble())
    monkeypatch.setattr(persistence.PngImagePlugin, "PngInfo", PngInfoDouble)
    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)

    class ArtifactFetcher:
        """Return stable bytes for every requested Comfy artifact."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the production fetcher constructor surface."""

        def fetch(self, artifact: object) -> bytes:
            """Record and return one deterministic image payload."""

            if fetched_artifacts is not None:
                fetched_artifacts.append(artifact)
            return b"fake-png-payload"

    monkeypatch.setattr(
        listener_output_pipeline,
        "ComfyArtifactFetcher",
        ArtifactFetcher,
    )
    default_workflow: JsonObject = {
        "output-node": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "CubeA.CubeOutput"},
        }
    }
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload=workflow_payload or default_workflow,
            output_run_number=output_run_number,
            output_save_plan=output_save_plan,
            workflow_name=workflow_name,
        ),
        callbacks=callbacks,
    )
    runnable.run()
    return output_events, failures, completed


def _cube_output_message(
    *,
    node_id: str = "output-node",
    prompt_id: str = "pid-1",
    instance_alias: str = "CubeA",
    workflow_id: str = "wf-1",
    generation_run_id: str = "run-1",
    client_id: str = "client",
) -> str:
    """Build a Substitute cube-output websocket event message."""

    source_label = instance_alias.rsplit("/", 1)[-1]
    return json.dumps(
        {
            "type": "substitute_cube_output",
            "data": {
                "version": 2,
                "prompt_id": prompt_id,
                "node_id": node_id,
                "list_index": 0,
                "cube_id": "owner/repo/demo.cube",
                "default_alias": instance_alias,
                "instance_alias": instance_alias,
                "instance_id": "instance-1",
                "media_kind": "image",
                "value_type": "torch.Tensor",
                "substitute": {
                    "schemaVersion": 1,
                    "workflowId": workflow_id,
                    "generationRunId": generation_run_id,
                    "clientId": client_id,
                    "sourceKey": f"{workflow_id}:{node_id}",
                    "sourceLabel": source_label,
                },
                "artifacts": [
                    {
                        "filename": "ComfyUI_temp_demo_00001_.png",
                        "subfolder": "",
                        "type": "temp",
                        "media_kind": "image",
                        "mime_type": "image/png",
                    }
                ],
            },
        }
    )


def _binary_text_message(
    *,
    node_id: str = "26",
    text: str = "width: 1024, height: 1024\n batch size: 1",
) -> bytes:
    """Build one Comfy TEXT binary websocket frame."""

    node_id_payload = node_id.encode("utf-8")
    return (
        struct.pack(">II", 3, len(node_id_payload))
        + node_id_payload
        + text.encode("utf-8")
    )


def _mutated_cube_output_message(**updates: object) -> str:
    """Build a cube-output message with targeted data-payload mutations."""

    message: Any = json.loads(_cube_output_message())
    data: dict[str, object] = message["data"]
    for key, value in updates.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return json.dumps(message)


def _mutated_cube_output_identity_message(**updates: object) -> str:
    """Build a cube-output message with targeted Substitute identity mutations."""

    message: Any = json.loads(_cube_output_message())
    data: dict[str, object] = message["data"]
    identity = cast(dict[str, object], data["substitute"])
    for key, value in updates.items():
        if value is None:
            identity.pop(key, None)
        else:
            identity[key] = value
    return json.dumps(message)
