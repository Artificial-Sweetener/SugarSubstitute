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

"""Characterization tests for websocket listener behavior."""

from __future__ import annotations

import importlib
import json
import logging
import struct
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerSessionHandle,
    ListenerStartRequest,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    OutputSavePlan,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.errors import RuntimeReportContext
from substitute.infrastructure.comfy import (
    listener_event_runtime,
    listener_output_pipeline,
    output_image_persistence,
    output_source_identity_resolver,
)


def _import_listener_module(monkeypatch):
    """Import websocket listener with lightweight websocket/PIL/Qt stubs."""
    websocket_mod = types.ModuleType("websocket")
    websocket_mod.WebSocket = type("WebSocket", (), {})
    monkeypatch.setitem(sys.modules, "websocket", websocket_mod)

    pil_mod = types.ModuleType("PIL")
    pil_image_mod = types.ModuleType("PIL.Image")
    pil_image_mod.open = lambda *_a, **_k: None
    pil_pnginfo_mod = types.ModuleType("PIL.PngImagePlugin")
    pil_pnginfo_mod.PngInfo = type("PngInfo", (), {"add_text": lambda *_a, **_k: None})
    pil_mod.Image = pil_image_mod
    pil_mod.PngImagePlugin = pil_pnginfo_mod
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil_image_mod)
    monkeypatch.setitem(sys.modules, "PIL.PngImagePlugin", pil_pnginfo_mod)

    qtcore = types.ModuleType("PySide6.QtCore")

    class _QRect:
        """Minimal QRect test double for import-time thumbnail helpers."""

        def __init__(self, *args):
            self.args = args

    qtcore.QRect = _QRect
    qtcore.Qt = types.SimpleNamespace(
        AspectRatioMode=types.SimpleNamespace(KeepAspectRatio=object()),
        TransformationMode=types.SimpleNamespace(SmoothTransformation=object()),
    )
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)

    qtgui = types.ModuleType("PySide6.QtGui")

    class _QImage:
        Format_RGBA8888 = object()

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def copy(self):
            return self

    class _QImageReader:
        """Minimal QImageReader test double."""

        def __init__(self, *_args, **_kwargs):
            pass

        def setAutoTransform(self, *_args, **_kwargs):
            return None

        def read(self):
            return _QImage()

    class _QColor:
        """Minimal QColor test double for import-time image utilities."""

        def __init__(self, *_args, **_kwargs):
            pass

        def redF(self):
            return 0.0

        def greenF(self):
            return 0.0

        def blueF(self):
            return 0.0

        def hslSaturationF(self):
            return 0.0

    qtgui.QImage = _QImage
    qtgui.QImageReader = _QImageReader
    qtgui.QColor = _QColor
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    transport = importlib.import_module(
        "substitute.infrastructure.comfy.websocket_transport"
    )
    transport = importlib.reload(transport)
    module = importlib.import_module(
        "substitute.infrastructure.comfy.websocket_listener"
    )
    module = importlib.reload(module)
    module.websocket = transport.websocket
    module.decode_preview_image = lambda _image_bytes: object()
    module.Image = types.SimpleNamespace(open=lambda *_args, **_kwargs: object())
    module.QImage = qtgui.QImage
    return module


def _build_callbacks():
    """Create listener callbacks and mutable collectors for assertions."""
    progress_events: list[ProgressUpdate] = []
    preview_events: list[PreviewImageUpdate] = []
    output_events: list[OutputImageUpdate] = []
    failures: list[ListenerFailure] = []
    completed: list[ListenerCompleted] = []

    callbacks: Any = ListenerCallbacks(
        on_progress=lambda event: progress_events.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda event: preview_events.append(event),
        on_output_image=lambda event: output_events.append(event),
        on_failed=lambda event: failures.append(event),
        on_timing=lambda _event: None,
        on_completed=lambda event: completed.append(event),
    )
    return (
        callbacks,
        progress_events,
        preview_events,
        output_events,
        failures,
        completed,
    )


def _patch_listener_artifact_fetcher(
    monkeypatch: pytest.MonkeyPatch,
    image_bytes: bytes = b"fake-png-payload",
) -> None:
    """Patch listener output-pipeline artifact fetches for deterministic tests."""

    class _ArtifactFetcher:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def fetch(self, _artifact: object) -> bytes:
            return image_bytes

    monkeypatch.setattr(
        listener_output_pipeline,
        "ComfyArtifactFetcher",
        _ArtifactFetcher,
    )


def _build_request(
    *,
    output_dir: Path,
    workflow_payload: dict[str, object],
    workflow_id: str = "wf-1",
    workflow_name: str = "My Workflow",
    prompt_id: str = "pid-1",
    output_run_number: int | None = None,
    output_save_plan: OutputSavePlan | None = None,
) -> Any:
    """Build listener start request with deterministic defaults."""
    return ListenerStartRequest(
        prompt_id=prompt_id,
        generation_run_id="run-1",
        client_id="client",
        listener_session=ListenerSessionHandle(
            workflow_id=workflow_id,
            generation_run_id="run-1",
            client_id="client",
            session=object(),
        ),
        output_dir=output_dir,
        workflow_payload=workflow_payload,
        sugar_script="line one",
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        output_run_number=output_run_number,
        output_save_plan=output_save_plan,
    )


def _fallback_output_date() -> str:
    """Return the date folder used by fallback listener save plans."""

    return datetime.now().astimezone().strftime("%Y-%m-%d")


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


def _mutated_cube_output_message(**updates: object) -> str:
    """Build a cube-output message with targeted data payload mutations."""

    message = json.loads(_cube_output_message())
    data = message["data"]
    for key, value in updates.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return json.dumps(message)


def _mutated_cube_output_identity_message(**updates: object) -> str:
    """Build a cube-output message with targeted Substitute identity mutations."""

    message = json.loads(_cube_output_message())
    identity = message["data"]["substitute"]
    for key, value in updates.items():
        if value is None:
            identity.pop(key, None)
        else:
            identity[key] = value
    return json.dumps(message)


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
    """Build one Comfy PREVIEW_IMAGE_WITH_METADATA binary websocket frame."""

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


def _run_listener_messages(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workflow_payload: dict[str, object],
    messages: list[object],
    prompt_id: str = "pid-1",
) -> tuple[
    list[ProgressUpdate],
    list[ListenerFailure],
    list[ListenerCompleted],
]:
    """Run the listener against deterministic websocket messages."""

    module = _import_listener_module(monkeypatch)
    monkeypatch.setattr(
        listener_event_runtime,
        "fetch_runtime_report_context",
        lambda *_args, **_kwargs: RuntimeReportContext(
            comfy_version="0.3.1",
            substitute_version="source checkout",
            pytorch_version="2.8.0",
            devices=("NVIDIA GeForce RTX 5090 (cuda #0)",),
        ),
    )
    callbacks, progress, _, _, failures, completed = _build_callbacks()

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload=workflow_payload,
            prompt_id=prompt_id,
        ),
        callbacks=callbacks,
    )

    runnable.run()

    return progress, failures, completed


def _run_listener_messages_with_timing(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workflow_payload: dict[str, object],
    messages: list[object],
    prompt_id: str = "pid-1",
    clock_values: list[float] | None = None,
) -> tuple[
    list[ProgressUpdate],
    list[GenerationExecutionTiming],
    list[ListenerFailure],
    list[ListenerCompleted],
    list[str],
]:
    """Run the listener and collect timing events with deterministic clocks."""

    module = _import_listener_module(monkeypatch)
    if clock_values is not None:
        clock_iter = iter(clock_values)
        last_clock_value = clock_values[-1]

        def _next_clock_value() -> float:
            try:
                return next(clock_iter)
            except StopIteration:
                return last_clock_value

        monkeypatch.setattr(listener_event_runtime, "perf_counter", _next_clock_value)
    monkeypatch.setattr(
        listener_event_runtime,
        "fetch_runtime_report_context",
        lambda *_args, **_kwargs: RuntimeReportContext(
            comfy_version="0.3.1",
            substitute_version="source checkout",
            pytorch_version="2.8.0",
            devices=("NVIDIA GeForce RTX 5090 (cuda #0)",),
        ),
    )
    progress_events: list[ProgressUpdate] = []
    timing_events: list[GenerationExecutionTiming] = []
    failures: list[ListenerFailure] = []
    completed: list[ListenerCompleted] = []
    event_order: list[str] = []

    def _record_timing(event: GenerationExecutionTiming) -> None:
        timing_events.append(event)
        event_order.append("timing")

    def _record_completed(event: ListenerCompleted) -> None:
        completed.append(event)
        event_order.append("completed")

    callbacks: Any = ListenerCallbacks(
        on_progress=lambda event: progress_events.append(event),
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda event: failures.append(event),
        on_timing=_record_timing,
        on_completed=_record_completed,
    )

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload=workflow_payload,
            prompt_id=prompt_id,
        ),
        callbacks=callbacks,
    )

    runnable.run()

    return progress_events, timing_events, failures, completed, event_order


def _run_cube_output_visual_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    messages: list[object],
    workflow_payload: dict[str, object] | None = None,
    fetched_artifacts: list[object] | None = None,
    saved_paths: list[str] | None = None,
) -> tuple[list[OutputImageUpdate], list[ListenerFailure], list[ListenerCompleted]]:
    """Run cube-output listener messages with deterministic image persistence."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, completed = _build_callbacks()
    monkeypatch.setattr(
        output_image_persistence,
        "get_next_bucket_run_number",
        lambda *_a, **_k: 7,
    )

    class _Image:
        width = 640
        height = 480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, _path: str, pnginfo=None) -> None:
            _ = pnginfo
            if saved_paths is not None:
                saved_paths.append(_path)
            return None

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)
    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)

    class _ArtifactFetcher:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def fetch(self, artifact: object) -> bytes:
            if fetched_artifacts is not None:
                fetched_artifacts.append(artifact)
            return b"fake-png-payload"

    monkeypatch.setattr(
        listener_output_pipeline,
        "ComfyArtifactFetcher",
        _ArtifactFetcher,
    )
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload=workflow_payload
            or {
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                }
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    return output_events, failures, completed


def _run_preview_visual_messages(
    monkeypatch: pytest.MonkeyPatch,
    *,
    messages: list[object],
) -> tuple[list[PreviewImageUpdate], list[OutputImageUpdate], list[ListenerFailure]]:
    """Run preview listener messages and collect visual callbacks."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, output_events, failures, _completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"preview-node": {"class_type": "VAEDecode"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    return preview_events, output_events, failures


def test_runnable_collects_cube_output_nodes(monkeypatch) -> None:
    """Constructor should collect SugarCubes.CubeOutput node IDs from workflow graph."""
    module = _import_listener_module(monkeypatch)
    callbacks, *_ = _build_callbacks()
    workflow = {
        "1": {"class_type": "SugarCubes.CubeOutput"},
        "2": {"class_type": "KSampler"},
        "3": {"class_type": "SugarCubes.CubeOutput"},
    }
    runnable = module.ComfyWebsocketListener(
        request=_build_request(output_dir=Path("."), workflow_payload=workflow),
        callbacks=callbacks,
    )

    assert runnable.cube_output_node_ids == {"1", "3"}


def test_runnable_reports_execution_error_detail(monkeypatch) -> None:
    """Comfy execution_error messages should surface useful failure detail."""

    _progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "execution_error",
                    "data": {
                        "prompt_id": "pid-1",
                        "exception_type": "ModuleNotFoundError",
                        "exception_message": "No module named 'xformers'",
                        "node_id": "12",
                        "node_type": "KSampler",
                        "executed": ["1", "2"],
                        "traceback": ["Traceback line 1", "Traceback line 2"],
                        "current_inputs": {"seed": 123},
                        "current_outputs": {"samples": []},
                    },
                }
            )
        ],
    )

    assert len(failures) == 1
    assert failures[0].error == "ModuleNotFoundError: No module named 'xformers'"
    assert failures[0].detail == "Traceback line 1\nTraceback line 2"
    assert failures[0].error_report is not None
    assert render_source_application_text(failures[0].error_report.title) == (
        "KSampler failed"
    )
    assert failures[0].error_report.runtime.comfy_version == "0.3.1"
    assert failures[0].error_report.runtime.pytorch_version == "2.8.0"
    assert failures[0].error_report.runtime.devices == (
        "NVIDIA GeForce RTX 5090 (cuda #0)",
    )
    assert failures[0].error_report.node is not None
    assert failures[0].error_report.node.node_id == "12"
    assert failures[0].error_report.node.current_inputs == {"seed": 123}
    assert completed[0].prompt_id == "pid-1"


def test_run_reports_progress_and_completion(monkeypatch) -> None:
    """Run loop should publish progress and emit completion on node=None execution."""
    module = _import_listener_module(monkeypatch)
    callbacks, progress, _, _, failures, completed = _build_callbacks()

    messages = [
        json.dumps({"type": "progress", "data": {"node": "1", "value": 1, "max": 2}}),
        json.dumps({"type": "execution_cached", "data": {"nodes": ["2"]}}),
        json.dumps({"type": "executing", "data": {"node": "1", "prompt_id": "pid-1"}}),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "1": {"class_type": "KSampler"},
                "2": {"class_type": "KSampler"},
            },
        ),
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


def test_run_emits_prompt_and_cube_timing_before_completion(monkeypatch) -> None:
    """Listener should emit Comfy prompt timing and summed cube node durations."""

    _progress, timing, failures, completed, event_order = (
        _run_listener_messages_with_timing(
            monkeypatch,
            workflow_payload={
                "1": {"class_type": "KSampler", "_meta": {"title": "CubeA.KSampler"}},
                "2": {
                    "class_type": "VAEDecode",
                    "_meta": {"title": "CubeA.Decode"},
                    "inputs": {"samples": ["1", 0]},
                },
                "3": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.Output"},
                    "inputs": {"image": ["2", 0]},
                },
            },
            messages=[
                json.dumps(
                    {
                        "type": "execution_start",
                        "data": {"prompt_id": "pid-1", "timestamp": 10000},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executed",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executed",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "execution_success",
                        "data": {"prompt_id": "pid-1", "timestamp": 13080},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": None, "prompt_id": "pid-1"},
                    }
                ),
            ],
            clock_values=[1.0, 2.0, 3.0, 4.0, 5.5, 6.0],
        )
    )

    assert failures == []
    assert len(completed) == 1
    assert event_order == ["timing", "completed"]
    assert len(timing) == 1
    assert timing[0].job_duration_ms == 3080.0
    assert [
        (item.cube_alias, item.source_key, item.duration_ms)
        for item in timing[0].cube_timings
    ] == [("CubeA", "wf-1:3", 2500.0)]


def test_run_excludes_cached_nodes_from_cube_timing(monkeypatch) -> None:
    """Cached nodes should not contribute execution duration."""

    _progress, timing, failures, completed, _event_order = (
        _run_listener_messages_with_timing(
            monkeypatch,
            workflow_payload={
                "1": {"class_type": "KSampler", "_meta": {"title": "CubeA.KSampler"}},
                "2": {"class_type": "VAEDecode", "_meta": {"title": "CubeB.Decode"}},
            },
            messages=[
                json.dumps(
                    {
                        "type": "execution_cached",
                        "data": {"prompt_id": "pid-1", "nodes": ["1"]},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executed",
                        "data": {"node": "2", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": None, "prompt_id": "pid-1"},
                    }
                ),
            ],
            clock_values=[1.0, 2.0, 3.0],
        )
    )

    assert failures == []
    assert len(completed) == 1
    assert len(timing) == 1
    assert [(item.cube_alias, item.duration_ms) for item in timing[0].cube_timings] == [
        ("CubeB", 1000.0)
    ]


def test_run_uses_listener_fallback_duration_without_prompt_timestamps(
    monkeypatch,
) -> None:
    """Listener-observed timing should fill job duration when Comfy omits timestamps."""

    _progress, timing, failures, completed, _event_order = (
        _run_listener_messages_with_timing(
            monkeypatch,
            workflow_payload={
                "1": {"class_type": "KSampler", "_meta": {"title": "CubeA.KSampler"}},
            },
            messages=[
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "1", "prompt_id": "pid-1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": None, "prompt_id": "pid-1"},
                    }
                ),
            ],
            clock_values=[1.0, 1.0, 2.25, 2.25],
        )
    )

    assert failures == []
    assert len(completed) == 1
    assert timing[0].job_duration_ms == 1250.0
    assert timing[0].cube_timings[0].duration_ms == 1250.0


def test_run_uses_wrapped_prompt_nodes_for_workflow_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped prompt payloads should not shrink the workflow denominator."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "prompt": {
                "1": {"class_type": "KSampler"},
                "2": {"class_type": "KSampler"},
            }
        },
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "pid-1", "nodes": ["1", "2"]},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress
    assert all(
        event.workflow_percent is None or event.workflow_percent <= 100.0
        for event in progress
    )
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]
    assert progress[0].workflow_id == "wf-1"
    assert progress[0].generation_run_id == "run-1"
    assert progress[0].prompt_id == "pid-1"
    assert progress[0].client_id == "client"


def test_run_ignores_other_prompt_cached_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cached-node events for another prompt must not mutate this prompt."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "other", "nodes": ["1", "2", "3"]},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]


def test_run_ignores_other_prompt_sampler_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler progress for another prompt must not emit a local update."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "other",
                        "node": "1",
                        "value": 1,
                        "max": 2,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]


def test_run_marks_previous_executing_node_complete_on_next_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executing events should represent node start, not immediate completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "1", "prompt_id": "pid-1"},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": "2", "prompt_id": "pid-1"},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.workflow_percent for event in progress] == [0.0, 50.0, 100.0]


def test_run_ignores_unknown_cached_node_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown cached node ids should not inflate workflow completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "pid-1", "nodes": ["1", "2", "3"]},
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None)
    ]
    assert all(
        event.workflow_percent is None or event.workflow_percent <= 100.0
        for event in progress
    )


def test_run_excludes_partial_cached_nodes_from_remaining_work_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Partially cached workflows should not jump by cached-node weight."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "execution_cached",
                    "data": {"prompt_id": "pid-1", "nodes": ["1"]},
                }
            ),
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "pid-1",
                        "node": "2",
                        "value": 1,
                        "max": 2,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.workflow_percent for event in progress] == [50.0, 100.0]


def test_run_clamps_sampler_progress_percent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler progress should stay within UI percentage bounds."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "pid-1",
                        "node": "1",
                        "value": 120,
                        "max": 100,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "pid-1",
                        "node": "1",
                        "value": -1,
                        "max": 100,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "progress",
                    "data": {
                        "prompt_id": "pid-1",
                        "node": "1",
                        "value": 1,
                        "max": 0,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.sampler_percent for event in progress[:3]] == [100.0, 0.0, None]


def test_run_uses_progress_state_for_workflow_and_sampler_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Progress_state should drive workflow progress and active sampler percent."""

    monkeypatch.setenv("SUGAR_COMFY_WS_TRACE", "1")
    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "CheckpointLoaderSimple"},
            "2": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "running", "value": 3, "max": 10},
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress[0].workflow_percent == pytest.approx(30.0)
    assert progress[0].sampler_percent == 30.0
    assert (progress[1].workflow_percent, progress[1].sampler_percent) == (
        100.0,
        None,
    )


def test_run_normalizes_progress_state_dotted_child_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dynamic child node ids should count through their display owner."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "21": {"class_type": "PCLazyTextEncode"},
            "24": {"class_type": "KSampler"},
        },
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "21.0.0.1": {
                                "node_id": "21.0.0.1",
                                "display_node_id": "21",
                                "state": "finished",
                                "value": 1,
                                "max": 1,
                            },
                            "24": {
                                "node_id": "24",
                                "display_node_id": "24",
                                "state": "running",
                                "value": 5,
                                "max": 10,
                            },
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress[0].workflow_percent == pytest.approx(75.0)
    assert progress[0].sampler_percent == 50.0
    assert (progress[1].workflow_percent, progress[1].sampler_percent) == (
        100.0,
        None,
    )


def test_run_advances_workflow_progress_during_sampler_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler progress should keep workflow/taskbar progress from stalling low."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={
            "1": {"class_type": "CheckpointLoaderSimple"},
            "2": {"class_type": "CLIPTextEncode"},
            "3": {"class_type": "KSampler"},
            "4": {"class_type": "VAEDecode"},
            "5": {"class_type": "SugarCubes.CubeOutput"},
        },
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "finished", "value": 1, "max": 1},
                            "3": {"state": "running", "value": 14, "max": 28},
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "finished", "value": 1, "max": 1},
                            "3": {"state": "running", "value": 28, "max": 28},
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert progress[0].workflow_percent == pytest.approx(37.5)
    assert progress[0].sampler_percent == 50.0
    assert progress[1].workflow_percent == pytest.approx(50.0)
    assert progress[1].sampler_percent == 100.0
    assert (progress[2].workflow_percent, progress[2].sampler_percent) == (
        100.0,
        None,
    )


def test_run_ignores_malformed_progress_state_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed progress_state entries should not affect progress or completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": "bad", "max": 1},
                            "2": "bad",
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [(event.workflow_percent, event.sampler_percent) for event in progress] == [
        (100.0, None),
    ]


def test_run_progress_state_cannot_exceed_one_hundred_percent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown progress_state nodes must not inflate workflow completion."""

    progress, failures, completed = _run_listener_messages(
        monkeypatch,
        workflow_payload={"1": {"class_type": "KSampler"}},
        messages=[
            json.dumps(
                {
                    "type": "progress_state",
                    "data": {
                        "prompt_id": "pid-1",
                        "nodes": {
                            "1": {"state": "finished", "value": 1, "max": 1},
                            "2": {"state": "finished", "value": 1, "max": 1},
                            "2.0.0.1": {
                                "state": "finished",
                                "value": 1,
                                "max": 1,
                            },
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "type": "executing",
                    "data": {"node": None, "prompt_id": "pid-1"},
                }
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert [event.workflow_percent for event in progress] == [100.0, 100.0]
    assert all(
        event.workflow_percent is None or event.workflow_percent <= 100.0
        for event in progress
    )


def test_run_forwards_valid_model_load_progress_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend model-load telemetry should be forwarded through its own callback."""

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

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"24": {"class_type": "CheckpointLoaderSimple"}},
        ),
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
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    """Model-load telemetry should route through structured node metadata."""

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

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "4": {"class_type": "KSampler", "inputs": {"model": ["2", 0]}},
                "2": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "example.safetensors"},
                    "_meta": {
                        "title": "Cube.checkpoint",
                        "substitute": {
                            "cube_alias": "Cube",
                            "node_name": "checkpoint",
                        },
                    },
                },
            },
        ),
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed backend model-load telemetry should not affect completion."""

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

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"24": {"class_type": "CheckpointLoaderSimple"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert model_load_events == []


def test_run_saves_cube_output_artifact_to_project_image(monkeypatch, tmp_path) -> None:
    """Cube-output image artifacts should be fetched and saved."""
    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, completed = _build_callbacks()
    monkeypatch.setattr(
        output_source_identity_resolver,
        "safe_component",
        lambda value: value,
    )
    monkeypatch.setattr(
        output_image_persistence,
        "get_next_bucket_run_number",
        lambda *_a, **_k: 7,
    )

    saved: list[tuple[str, object]] = []
    png_text: list[tuple[str, str]] = []

    class _Image:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            saved.append((path, pnginfo))

    class _PngInfo:
        def add_text(self, key: str, value: str) -> None:
            png_text.append((key, value))

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "ws-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_preview_image_message(b"fake-png-payload"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    ui_workflow = {
        "version": 0.4,
        "nodes": [{"id": 1, "type": "SugarCubes.CubeOutput"}],
    }
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "prompt": {
                    "output-node": {
                        "class_type": "SugarCubes.CubeOutput",
                        "_meta": {"title": "CubeA.CubeOutput"},
                    }
                },
                "workflow": ui_workflow,
            },
        ),
        callbacks=callbacks,
    )
    messages = [
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    output_date = _fallback_output_date()
    runnable.run()

    expected_path = tmp_path / output_date / "007_01_my_workflow_cubea.png"
    assert failures == []
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"
    assert len(output_events) == 1
    assert output_events[0].file_path == expected_path
    assert output_events[0].node_id == "output-node"
    assert output_events[0].source_key == "wf-1:output-node"
    assert output_events[0].source_label == "CubeA"
    assert saved and str(saved[0][0]) == str(expected_path)
    assert png_text == [
        ("sugar_script", "# Project: My Workflow\n\nline one"),
        ("workflow", json.dumps(ui_workflow, separators=(",", ":"))),
    ]


def test_run_saves_prefixed_cube_output_with_short_source_label(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cube-output labels and filenames should omit model-prefix aliases."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, completed = _build_callbacks()
    monkeypatch.setattr(
        output_image_persistence,
        "get_next_bucket_run_number",
        lambda *_a, **_k: 7,
    )

    saved: list[tuple[str, object]] = []

    class _Image:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            saved.append((path, pnginfo))

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "SDXL/Text to Image.CubeOutput"},
                }
            },
        ),
        callbacks=callbacks,
    )
    messages = [
        _cube_output_message(
            node_id="output-node",
            instance_alias="SDXL/Text to Image",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    output_date = _fallback_output_date()
    runnable.run()

    expected_path = tmp_path / output_date / "007_01_my_workflow_text_to_image.png"
    assert failures == []
    assert len(completed) == 1
    assert output_events[0].file_path == expected_path
    assert output_events[0].source_key == "wf-1:output-node"
    assert output_events[0].source_label == "Text to Image"
    assert saved and str(saved[0][0]) == str(expected_path)
    assert "sdxl_text_to_image" not in str(expected_path)


def test_run_preserves_cube_output_source_scene_and_list_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 0 - listener DTO preserves backend final routing metadata."""

    message = json.loads(_cube_output_message(node_id="output-node"))
    message["data"]["list_index"] = 5
    message["data"]["substitute"]["sceneRunId"] = "scene-run-1"
    message["data"]["substitute"]["sceneKey"] = "scene-b"
    message["data"]["substitute"]["sceneTitle"] = "Scene B"
    message["data"]["substitute"]["sceneOrder"] = 2
    message["data"]["substitute"]["sceneCount"] = 4

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            json.dumps(message),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert len(output_events) == 1
    assert output_events[0].source_key == "wf-1:output-node"
    assert output_events[0].source_label == "CubeA"
    assert output_events[0].scene_run_id == "scene-run-1"
    assert output_events[0].scene_key == "scene-b"
    assert output_events[0].scene_title == "Scene B"
    assert output_events[0].scene_order == 2
    assert output_events[0].scene_count == 4
    assert output_events[0].list_index == 5


@pytest.mark.parametrize(
    ("message", "case_name"),
    [
        (_cube_output_message(prompt_id="other-prompt"), "prompt"),
        (_cube_output_message(workflow_id="wf-other"), "workflow"),
        (_cube_output_message(generation_run_id="run-other"), "generation_run"),
        (_cube_output_message(client_id="client-other"), "client"),
    ],
)
def test_run_rejects_stale_and_mismatched_cube_output_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    message: str,
    case_name: str,
) -> None:
    """Phase 0 - stale/mismatched final backend identity is rejected before IO."""

    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            message,
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == [], case_name
    assert len(completed) == 1
    assert output_events == []
    assert fetched_artifacts == []
    assert saved_paths == []


def test_run_hydrates_missing_artifact_dimensions_from_fetched_image_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 0 - missing artifact dimensions are hydrated before strict DTOs."""

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _cube_output_message(node_id="output-node"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert getattr(output_events[0], "artifact_width") == 640
    assert getattr(output_events[0], "artifact_height") == 480


@pytest.mark.parametrize(
    ("message", "case_name"),
    [
        (_mutated_cube_output_message(list_index=None), "missing"),
        (_mutated_cube_output_message(list_index="0"), "non_integer"),
        (_mutated_cube_output_message(list_index=-1), "negative"),
    ],
)
def test_run_rejects_cube_output_without_list_index_before_registration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    message: str,
    case_name: str,
) -> None:
    """Phase 0 - live final events without a usable list_index fail closed."""

    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []

    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            message,
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == [], case_name
    assert len(completed) == 1
    assert output_events == []
    assert fetched_artifacts == []
    assert saved_paths == []


def test_run_rejects_non_image_final_media_and_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 0 - non-image final media/artifacts do not create Output images."""

    non_image_artifact = json.loads(_cube_output_message())
    non_image_artifact["data"]["artifacts"][0]["media_kind"] = "text"
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _mutated_cube_output_message(media_kind="text"),
            json.dumps(non_image_artifact),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events == []


def test_run_rejects_cube_output_without_required_v2_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 0 - final cube-output events without backend identity are ignored."""

    fetched_artifacts: list[object] = []
    saved_paths: list[str] = []
    output_events, failures, completed = _run_cube_output_visual_messages(
        monkeypatch,
        tmp_path,
        messages=[
            _mutated_cube_output_message(substitute=None),
            _mutated_cube_output_identity_message(sourceKey=None),
            _mutated_cube_output_identity_message(sourceLabel=None),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
        fetched_artifacts=fetched_artifacts,
        saved_paths=saved_paths,
    )

    assert failures == []
    assert len(completed) == 1
    assert output_events == []
    assert fetched_artifacts == []
    assert saved_paths == []


def test_run_ignores_comfy_binary_text_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comfy TEXT binary frames should not be decoded as preview images."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, output_events, failures, completed = (
        _build_callbacks()
    )
    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "26", "prompt_id": "pid-1"},
            }
        ),
        _binary_text_message(node_id="26"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"26": {"class_type": "GetImageSize"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert output_events == []
    assert preview_events == []
    assert len(completed) == 1
    assert completed[0].prompt_id == "pid-1"


def test_run_persists_cube_output_after_comfy_binary_text_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Binary text frames before cube outputs should not stop output persistence."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, output_events, failures, completed = (
        _build_callbacks()
    )
    saved: list[str] = []

    class _Image:
        width = 640
        height = 480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            del pnginfo
            saved.append(path)

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)
    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "26", "prompt_id": "pid-1"},
            }
        ),
        _binary_text_message(node_id="26"),
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "26": {"class_type": "GetImageSize"},
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                },
            },
            output_run_number=7,
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert preview_events == []
    assert len(output_events) == 1
    assert output_events[0].node_id == "output-node"
    assert len(saved) == 1
    assert len(completed) == 1


def test_run_emits_preview_with_source_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preview frames should include the executing node's output source identity."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, _output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "preview-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_metadata_preview_image_message(
            metadata={"node_id": "preview-node", "prompt_id": "pid-1"},
            source_label="CubeA",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "preview-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "CubeA.KSampler"},
                }
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].workflow_id == "wf-1"
    assert preview_events[0].node_id == "preview-node"
    assert preview_events[0].source_key == "wf-1:preview-node"
    assert preview_events[0].source_label == "CubeA"


def test_run_uses_comfy_binary_preview_metadata_node_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata-bearing preview frames should use Comfy's node identity."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, _output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "running-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_metadata_preview_image_message(
            metadata={
                "node_id": "preview-node",
                "display_node_id": "display-node",
                "parent_node_id": "parent-node",
                "real_node_id": "real-node",
                "prompt_id": "pid-1",
            },
            source_label="Preview",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "running-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "Running.KSampler"},
                },
                "preview-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "Preview.KSampler"},
                },
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].node_id == "preview-node"
    assert preview_events[0].metadata_node_id == "preview-node"
    assert preview_events[0].display_node_id == "display-node"
    assert preview_events[0].parent_node_id == "parent-node"
    assert preview_events[0].real_node_id == "real-node"
    assert preview_events[0].source_key == "wf-1:preview-node"
    assert preview_events[0].source_label == "Preview"


def test_run_uses_comfy_binary_preview_display_node_without_node_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata-bearing previews should route from alternate backend node fields."""

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


def test_run_emits_preview_with_short_prefixed_source_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy node-title source labels should omit model-prefix aliases."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, _output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "preview-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_metadata_preview_image_message(
            metadata={"node_id": "preview-node", "prompt_id": "pid-1"},
            source_label="Text to Image",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "preview-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "SDXL/Text to Image.KSampler"},
                }
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].source_key == "wf-1:preview-node"
    assert preview_events[0].source_label == "Text to Image"


def test_run_maps_preview_source_to_downstream_cube_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preview frames should group under the downstream cube output source."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, _output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "sampler-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_metadata_preview_image_message(
            metadata={"node_id": "sampler-node", "prompt_id": "pid-1"},
            source_key="wf-1:output-node",
            source_label="CubeA",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "sampler-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "Sampler.KSampler"},
                },
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                    "inputs": {"value": ["sampler-node", 0]},
                },
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].workflow_id == "wf-1"
    assert preview_events[0].node_id == "sampler-node"
    assert preview_events[0].source_key == "wf-1:output-node"
    assert preview_events[0].source_label == "CubeA"


def test_run_maps_preview_source_to_nearest_downstream_cube_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preview sources feeding multiple outputs should use the nearest output."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, _output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "sampler-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_metadata_preview_image_message(
            metadata={"node_id": "sampler-node", "prompt_id": "pid-1"},
            source_key="wf-1:near-output",
            source_label="Text to Image",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "sampler-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "Sampler.KSampler"},
                },
                "near-output": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "Text to Image.CubeOutput"},
                    "inputs": {"value": ["sampler-node", 0]},
                },
                "upscale-node": {
                    "class_type": "KSampler",
                    "inputs": {"image": ["sampler-node", 0]},
                },
                "far-output": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "Diffusion Upscale.CubeOutput"},
                    "inputs": {"value": ["upscale-node", 0]},
                },
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].node_id == "sampler-node"
    assert preview_events[0].source_key == "wf-1:near-output"
    assert preview_events[0].source_label == "Text to Image"


def test_run_uses_node_source_when_preview_maps_to_multiple_cube_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambiguous preview sources should fall back to their executing node identity."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, _output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 32
        height = 16

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args: object) -> bytes:
            return b"\x00" * self.width * self.height * 4

    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "shared-node", "prompt_id": "pid-1"},
            }
        ),
        _binary_metadata_preview_image_message(
            metadata={"node_id": "shared-node", "prompt_id": "pid-1"},
            source_label="Shared",
        ),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={
                "shared-node": {
                    "class_type": "KSampler",
                    "_meta": {"title": "Shared.KSampler"},
                },
                "output-a": {
                    "class_type": "SugarCubes.CubeOutput",
                    "inputs": {"value": ["shared-node", 0]},
                },
                "output-b": {
                    "class_type": "SugarCubes.CubeOutput",
                    "inputs": {"value": ["shared-node", 0]},
                },
            },
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert len(preview_events) == 1
    assert preview_events[0].node_id == "shared-node"
    assert preview_events[0].source_key == "wf-1:shared-node"
    assert preview_events[0].source_label == "Shared"


def test_run_saves_cube_output_artifact_with_reserved_output_number(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reserved output run numbers should be used without lazy file scanning."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, _completed = _build_callbacks()
    counter_calls: list[object] = []

    def _unexpected_counter_call(*_args: object, **_kwargs: object) -> int:
        counter_calls.append((_args, _kwargs))
        return 99

    monkeypatch.setattr(
        output_source_identity_resolver,
        "safe_component",
        lambda value: value,
    )
    monkeypatch.setattr(
        output_image_persistence,
        "get_next_bucket_run_number",
        _unexpected_counter_call,
    )

    saved: list[str] = []

    class _Image:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            del pnginfo
            saved.append(path)

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)

    messages = [
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                }
            },
            output_run_number=12,
        ),
        callbacks=callbacks,
    )

    output_date = _fallback_output_date()
    runnable.run()

    expected_path = tmp_path / output_date / "012_01_my_workflow_cubea.png"
    assert failures == []
    assert output_events[0].file_path == expected_path
    assert [str(path) for path in saved] == [str(expected_path)]
    assert counter_calls == []


def test_run_saves_cube_output_artifact_with_custom_output_save_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Output save plans should control root, folder pattern, and filename pattern."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, _completed = _build_callbacks()
    monkeypatch.setattr(
        output_source_identity_resolver,
        "safe_component",
        lambda value: value,
    )
    saved: list[str] = []

    class _Image:
        width = 640
        height = 480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            del pnginfo
            saved.append(path)

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)

    messages = [
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    output_root = tmp_path / "external"
    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                }
            },
            output_run_number=12,
            output_save_plan=OutputSavePlan(
                output_root=output_root,
                path_pattern=(
                    "{workflow}\\{date}\\{run}_{time}_{source}_{width}x{height}_{set}"
                ),
                workflow_name="My Workflow",
                output_run_number=12,
                job_started_at=datetime(2026, 5, 1, 14, 32, 9),
            ),
        ),
        callbacks=callbacks,
    )

    runnable.run()

    expected_path = (
        output_root / "My Workflow" / "2026-05-01" / "012_14-32-09_cubea_640x480_1.png"
    )
    assert failures == []
    assert output_events[0].file_path == expected_path
    assert [str(path) for path in saved] == [str(expected_path)]


def test_run_saves_cube_output_artifact_with_seed_output_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Listener output rendering should consume the immutable save-plan seed."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, _completed = _build_callbacks()
    monkeypatch.setattr(
        output_source_identity_resolver,
        "safe_component",
        lambda value: value,
    )
    saved: list[str] = []

    class _Image:
        width = 640
        height = 480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            del pnginfo
            saved.append(path)

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)

    messages = [
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    output_root = tmp_path / "external"
    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                }
            },
            output_run_number=12,
            output_save_plan=OutputSavePlan(
                output_root=output_root,
                path_pattern="{workflow}\\{seed}_{source}",
                workflow_name="My Workflow",
                output_run_number=12,
                job_started_at=datetime(2026, 5, 1, 14, 32, 9),
                seed="1234",
            ),
        ),
        callbacks=callbacks,
    )

    runnable.run()

    expected_path = output_root / "My Workflow" / "1234_cubea.png"
    assert failures == []
    assert output_events[0].file_path == expected_path
    assert [str(path) for path in saved] == [str(expected_path)]


def test_run_saves_cube_output_artifact_with_folder_image_number_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Folder image numbers should increment independently from the run number."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, _completed = _build_callbacks()
    saved: list[str] = []

    class _Image:
        width = 640
        height = 480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            del pnginfo
            saved.append(path)

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)

    messages = [
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    output_root = tmp_path / "external"
    existing = output_root / "2026-05-01" / "image_01_cubea.png"
    existing.parent.mkdir(parents=True)
    existing.write_text("", encoding="utf-8")
    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                }
            },
            output_run_number=12,
            output_save_plan=OutputSavePlan(
                output_root=output_root,
                path_pattern="{date}\\Image {image#}_{source}",
                workflow_name="My Workflow",
                output_run_number=12,
                job_started_at=datetime(2026, 5, 1, 14, 32, 9),
            ),
        ),
        callbacks=callbacks,
    )

    runnable.run()

    expected_path = output_root / "2026-05-01" / "image_02_cubea.png"
    assert failures == []
    assert output_events[0].file_path == expected_path
    assert [str(path) for path in saved] == [str(expected_path)]


def test_run_saves_cube_output_artifact_without_overwriting_existing_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Output save plans should suffix colliding filenames instead of overwriting."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, output_events, failures, _completed = _build_callbacks()
    monkeypatch.setattr(
        output_source_identity_resolver,
        "safe_component",
        lambda value: value,
    )
    output_date = _fallback_output_date()
    existing = tmp_path / output_date / "012_01_my_workflow_cubea.png"
    existing.parent.mkdir()
    existing.write_text("", encoding="utf-8")
    saved: list[str] = []

    class _Image:
        width = 640
        height = 480

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def save(self, path: str, pnginfo=None) -> None:
            del pnginfo
            saved.append(path)

    class _PngInfo:
        def add_text(self, _key: str, _value: str) -> None:
            return None

    monkeypatch.setattr(
        output_image_persistence.Image, "open", lambda _stream: _Image()
    )
    monkeypatch.setattr(output_image_persistence.PngImagePlugin, "PngInfo", _PngInfo)

    messages = [
        _cube_output_message(node_id="output-node"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    _patch_listener_artifact_fetcher(monkeypatch)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=tmp_path,
            workflow_payload={
                "output-node": {
                    "class_type": "SugarCubes.CubeOutput",
                    "_meta": {"title": "CubeA.CubeOutput"},
                }
            },
            output_run_number=12,
        ),
        callbacks=callbacks,
    )

    runnable.run()

    expected_path = tmp_path / output_date / "012_01_my_workflow_cubea_002.png"
    assert failures == []
    assert output_events[0].file_path == expected_path
    assert [str(path) for path in saved] == [str(expected_path)]


def test_run_drops_metadata_less_binary_preview(monkeypatch) -> None:
    """Legacy binary preview frames should fail closed instead of guessing a source."""
    module = _import_listener_module(monkeypatch)
    callbacks, _, preview_events, output_events, failures, completed = (
        _build_callbacks()
    )

    class _PreviewImage:
        width = 16
        height = 8

        def convert(self, _mode: str):
            return self

        def tobytes(self, *_args, **_kwargs):
            return b"x" * (self.width * self.height * 4)

    class _QImage:
        Format_RGBA8888 = object()

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def copy(self):
            return self

    monkeypatch.setattr(module, "QImage", _QImage)
    monkeypatch.setattr(module.Image, "open", lambda _stream: _PreviewImage())

    messages = [
        json.dumps(
            {
                "type": "executing",
                "data": {"node": "ksampler", "prompt_id": "pid-1"},
            }
        ),
        _binary_preview_image_message(b"preview-data"),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
    ]

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return messages.pop(0)

        def close(self):
            return None

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"save-node": {"class_type": "SugarCubes.CubeOutput"}},
            workflow_id="wf-preview",
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert failures == []
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-preview"
    assert completed[0].prompt_id == "pid-1"
    assert output_events == []
    assert preview_events == []


def test_run_rejects_stale_and_mismatched_preview_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 0 - stale/mismatched backend preview identity is ignored."""

    def _preview_with_identity(**identity_updates: object) -> bytes:
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
            _preview_with_identity(workflowId="wf-other"),
            _preview_with_identity(generationRunId="run-other"),
            _preview_with_identity(clientId="client-other"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ],
    )

    assert failures == []
    assert output_events == []
    assert preview_events == []


def test_run_rejects_preview_metadata_without_normalized_source_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 0 - preview metadata without a normalized source node fails closed."""

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


def test_run_emits_failure_and_completion_when_recv_raises(monkeypatch) -> None:
    """Socket errors should emit failure and completion exactly once."""
    module = _import_listener_module(monkeypatch)
    callbacks, _, _, _, failures, completed = _build_callbacks()
    closed: list[bool] = []

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            raise RuntimeError("network down")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"1": {"class_type": "KSampler"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert closed == [True]
    assert len(failures) == 1
    assert failures[0].workflow_id == "wf-1"
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_handles_malformed_json_and_still_completes(monkeypatch) -> None:
    """Malformed text payloads should emit failure and completion without crashing."""
    module = _import_listener_module(monkeypatch)
    callbacks, _, _, _, failures, completed = _build_callbacks()
    closed: list[bool] = []

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            return "{not-json"

        def close(self):
            closed.append(True)

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"1": {"class_type": "KSampler"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert closed == [True]
    assert len(failures) == 1
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_ignores_short_binary_frame_and_completes(monkeypatch) -> None:
    """Malformed binary frames should be ignored without failing generation."""
    module = _import_listener_module(monkeypatch)
    callbacks, _, _, _, failures, completed = _build_callbacks()
    closed: list[bool] = []

    class _FakeWebSocket:
        def __init__(self) -> None:
            self._step = 0

        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            self._step += 1
            if self._step == 1:
                return json.dumps(
                    {
                        "type": "executing",
                        "data": {"node": "N1", "prompt_id": "pid-1"},
                    }
                )
            if self._step == 2:
                return b"\x00\x01"
            return json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            )

        def close(self):
            closed.append(True)

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    monkeypatch.setattr(
        module.Image,
        "open",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad image")),
    )
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"N1": {"class_type": "SugarCubes.CubeOutput"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert closed == [True]
    assert failures == []
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_emits_failure_when_idle_prompt_is_verified_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idle prompts absent from queue and history should fail deterministically."""
    module = _import_listener_module(monkeypatch)
    callbacks, _, _, _, failures, completed = _build_callbacks()

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            raise TimeoutError("socket timeout")

        def close(self):
            return None

    class _EmptyResponse:
        """Return an empty Comfy queue or history payload."""

        def raise_for_status(self) -> None:
            """Accept the fake HTTP response."""

        def json(self) -> dict[str, object]:
            """Return an empty queue or history object."""

            return {}

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.prompt_liveness.requests.get",
        lambda *_args, **_kwargs: _EmptyResponse(),
    )
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"1": {"class_type": "KSampler"}},
        ),
        callbacks=callbacks,
        receive_timeout_seconds=1.0,
    )

    runnable.run()

    assert len(failures) == 1
    assert "could not be found" in failures[0].error
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert completed[0].prompt_id == "pid-1"


def test_run_reports_connection_reset_without_exception_traceback(
    monkeypatch,
    caplog,
) -> None:
    """Remote websocket resets should become clean listener failures."""

    module = _import_listener_module(monkeypatch)
    callbacks, _, _, _, failures, completed = _build_callbacks()
    closed: list[bool] = []

    class _FakeWebSocket:
        def connect(self, _url):
            return None

        def send(self, _payload):
            return None

        def recv(self):
            raise ConnectionResetError(
                10054,
                "An existing connection was forcibly closed by the remote host",
            )

        def close(self):
            closed.append(True)

    monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.infrastructure.comfy.websocket_listener",
    )
    runnable = module.ComfyWebsocketListener(
        request=_build_request(
            output_dir=Path("."),
            workflow_payload={"1": {"class_type": "KSampler"}},
        ),
        callbacks=callbacks,
    )

    runnable.run()

    assert closed == [True]
    assert len(failures) == 1
    assert failures[0].error == (
        "Comfy websocket connection closed before generation completed."
    )
    assert len(completed) == 1
    assert completed[0].workflow_id == "wf-1"
    assert "reason=websocket_disconnected" in caplog.text


def test_run_sanitizes_workflow_name_path_tokens(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Workflow names that resemble traversal should stay within output root."""

    expected_names = {
        "../escape": "001_01_escape_cubea.png",
        "..": "001_01_cubea.png",
    }
    for workflow_name, expected_name in expected_names.items():
        module = _import_listener_module(monkeypatch)
        callbacks, _, _, output_events, failures, completed = _build_callbacks()
        monkeypatch.setattr(
            output_source_identity_resolver,
            "safe_component",
            lambda value: value,
        )
        monkeypatch.setattr(
            output_image_persistence,
            "get_next_bucket_run_number",
            lambda *_a, **_k: 1,
        )

        class _Image:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def save(self, path: str, pnginfo=None) -> None:
                _ = path, pnginfo
                return None

        monkeypatch.setattr(
            output_image_persistence.Image,
            "open",
            lambda _stream: _Image(),
        )

        messages = [
            _cube_output_message(node_id="output-node"),
            json.dumps(
                {"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}
            ),
        ]

        class _FakeWebSocket:
            def connect(self, _url):
                return None

            def send(self, _payload):
                return None

            def recv(self):
                return messages.pop(0)

            def close(self):
                return None

        monkeypatch.setattr(module.websocket, "WebSocket", _FakeWebSocket)
        _patch_listener_artifact_fetcher(monkeypatch)
        runnable = module.ComfyWebsocketListener(
            request=_build_request(
                output_dir=tmp_path,
                workflow_payload={
                    "output-node": {
                        "class_type": "SugarCubes.CubeOutput",
                        "_meta": {"title": "CubeA.CubeOutput"},
                    }
                },
                workflow_name=workflow_name,
            ),
            callbacks=callbacks,
        )

        runnable.run()

        output_date = _fallback_output_date()
        assert output_events[0].file_path == tmp_path / output_date / expected_name
        assert failures == []
        assert len(completed) == 1
