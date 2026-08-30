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

"""Verify listener model-load progress adaptation and source enrichment."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from substitute.application.ports import ModelLoadProgressUpdate
from substitute.domain.common import JsonObject
from tests.infrastructure.comfy.listener.contract_harness import (
    _build_callbacks,
    _build_request,
    _import_listener_module,
)


def test_run_forwards_valid_model_load_progress_event(
    monkeypatch: MonkeyPatch,
) -> None:
    """Forward valid model-load telemetry through its dedicated callback."""

    module = _import_listener_module(monkeypatch)
    model_load_events: list[ModelLoadProgressUpdate] = []
    callbacks, _, _, _, failures, completed = _build_callbacks()
    callbacks.on_model_load_progress = model_load_events.append
    messages = [
        json.dumps(
            {
                "type": "substitute_model_load_progress",
                "data": {
                    "version": 1,
                    "prompt_id": "pid-1",
                    "node_id": "24.0.0.1",
                    "display_node_id": "24",
                    "phase": "dynamic_vram_staging",
                    "state": "running",
                    "percent": 140,
                    "value": 2048,
                    "max": 4897,
                    "unit": "mb",
                    "model_class": "SDXL",
                    "detail": "2048MB of 4897MB staged",
                },
            }
        ),
        json.dumps(
            {
                "type": "executing",
                "data": {"node": None, "prompt_id": "pid-1"},
            }
        ),
    ]

    class FakeWebSocket:
        """Serve a finite model-load progress sequence."""

        def connect(self, _url: str) -> None:
            """Accept listener connection."""

        def send(self, _payload: str) -> None:
            """Accept listener handshake payload."""

        def recv(self) -> str:
            """Return the next listener message."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    workflow: JsonObject = {"24": {"class_type": "CheckpointLoaderSimple"}}
    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(output_dir=Path("."), workflow_payload=workflow),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(model_load_events) == 1
    event = model_load_events[0]
    assert event.workflow_id == "wf-1"
    assert event.prompt_id == "pid-1"
    assert event.node_id == "24.0.0.1"
    assert event.display_node_id == "24"
    assert event.phase == "dynamic_vram_staging"
    assert event.state == "running"
    assert event.percent == 100.0
    assert event.value == 2048.0
    assert event.maximum == 4897.0
    assert event.unit == "mb"
    assert event.model_class == "SDXL"
    assert event.model_name is None
    assert event.source_node_id is None
    assert event.source_input_key is None
    assert event.source_cube_alias is None
    assert event.source_workflow_node_name is None
    assert event.detail == "2048MB of 4897MB staged"


def test_run_enriches_model_load_source_metadata(
    monkeypatch: MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    """Resolve source-node and cube metadata for model-load telemetry."""

    caplog.set_level(logging.INFO)
    module = _import_listener_module(monkeypatch)
    model_load_events: list[ModelLoadProgressUpdate] = []
    callbacks, _, _, _, failures, completed = _build_callbacks()
    callbacks.on_model_load_progress = model_load_events.append
    messages = [
        json.dumps(
            {
                "type": "substitute_model_load_progress",
                "data": {
                    "version": 1,
                    "prompt_id": "pid-1",
                    "node_id": "4",
                    "display_node_id": "4",
                    "source_node_id": "2",
                    "source_input_key": "ckpt_name",
                    "phase": "dynamic_vram_staging",
                    "state": "running",
                    "percent": 42,
                    "value": 2048,
                    "max": 4897,
                    "model_name": "example.safetensors",
                },
            }
        ),
        json.dumps(
            {
                "type": "executing",
                "data": {"node": None, "prompt_id": "pid-1"},
            }
        ),
    ]

    class FakeWebSocket:
        """Serve a finite model-load enrichment sequence."""

        def connect(self, _url: str) -> None:
            """Accept listener connection."""

        def send(self, _payload: str) -> None:
            """Accept listener handshake payload."""

        def recv(self) -> str:
            """Return the next listener message."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    workflow: JsonObject = {
        "4": {"class_type": "KSampler", "inputs": {"model": ["2", 0]}},
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "example.safetensors"},
            "_meta": {
                "title": "Cube.checkpoint",
                "substitute": {"cube_alias": "Cube", "node_name": "checkpoint"},
            },
        },
    }
    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(output_dir=Path("."), workflow_payload=workflow),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(model_load_events) == 1
    event = model_load_events[0]
    assert event.workflow_id == "wf-1"
    assert event.source_node_id == "2"
    assert event.source_input_key == "ckpt_name"
    assert event.source_cube_alias == "Cube"
    assert event.source_workflow_node_name == "checkpoint"
    assert "Model-load source metadata resolved" in caplog.text
    assert "source_node_id=2" in caplog.text
    assert "cube_alias=Cube" in caplog.text


def test_run_ignores_malformed_model_load_progress_event(
    monkeypatch: MonkeyPatch,
) -> None:
    """Ignore malformed telemetry while retaining normal terminal completion."""

    module = _import_listener_module(monkeypatch)
    model_load_events: list[ModelLoadProgressUpdate] = []
    callbacks, _, _, _, failures, completed = _build_callbacks()
    callbacks.on_model_load_progress = model_load_events.append
    messages = [
        json.dumps(
            {
                "type": "substitute_model_load_progress",
                "data": {
                    "version": 99,
                    "prompt_id": "pid-1",
                    "phase": "dynamic_vram_staging",
                    "state": "running",
                },
            }
        ),
        json.dumps(
            {
                "type": "executing",
                "data": {"node": None, "prompt_id": "pid-1"},
            }
        ),
    ]

    class FakeWebSocket:
        """Serve a finite malformed telemetry sequence."""

        def connect(self, _url: str) -> None:
            """Accept listener connection."""

        def send(self, _payload: str) -> None:
            """Accept listener handshake payload."""

        def recv(self) -> str:
            """Return the next listener message."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    workflow: JsonObject = {"24": {"class_type": "CheckpointLoaderSimple"}}
    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(output_dir=Path("."), workflow_payload=workflow),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert model_load_events == []
