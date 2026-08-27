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

"""Provide deterministic import and callback boundaries for listener contracts."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any

from _pytest.monkeypatch import MonkeyPatch

from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerSessionHandle,
    ListenerStartRequest,
    OutputImageUpdate,
    OutputSavePlan,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.errors import RuntimeReportContext
from substitute.domain.common import JsonObject
from substitute.infrastructure.comfy import listener_event_runtime


def _import_listener_module(monkeypatch: MonkeyPatch) -> Any:
    """Import the listener behind deterministic external-boundary doubles."""

    websocket_mod: Any = types.ModuleType("websocket")
    websocket_mod.WebSocket = type("WebSocket", (), {})
    monkeypatch.setitem(sys.modules, "websocket", websocket_mod)

    pil_mod: Any = types.ModuleType("PIL")
    pil_image_mod: Any = types.ModuleType("PIL.Image")
    pil_image_mod.open = lambda *_args, **_kwargs: None
    pil_pnginfo_mod: Any = types.ModuleType("PIL.PngImagePlugin")
    pil_pnginfo_mod.PngInfo = type(
        "PngInfo",
        (),
        {"add_text": lambda *_args, **_kwargs: None},
    )
    pil_mod.Image = pil_image_mod
    pil_mod.PngImagePlugin = pil_pnginfo_mod
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil_image_mod)
    monkeypatch.setitem(sys.modules, "PIL.PngImagePlugin", pil_pnginfo_mod)

    qtcore: Any = types.ModuleType("PySide6.QtCore")

    class QRectDouble:
        """Model the import-time QRect constructor used by thumbnail helpers."""

        def __init__(self, *args: object) -> None:
            """Store the requested rectangle arguments."""

            self.args = args

    qtcore.QRect = QRectDouble
    qtcore.Qt = types.SimpleNamespace(
        AspectRatioMode=types.SimpleNamespace(KeepAspectRatio=object()),
        TransformationMode=types.SimpleNamespace(SmoothTransformation=object()),
    )
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)

    qtgui: Any = types.ModuleType("PySide6.QtGui")

    class QImageDouble:
        """Model the QImage surface needed while importing listener helpers."""

        Format_RGBA8888 = object()

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Store construction arguments for contract assertions."""

            self.args = args
            self.kwargs = kwargs

        def copy(self) -> "QImageDouble":
            """Return a stable copied image double."""

            return self

    class QImageReaderDouble:
        """Model image-reader calls needed by import-time thumbnail helpers."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the production reader constructor surface."""

        def setAutoTransform(self, *_args: object, **_kwargs: object) -> None:
            """Accept the production auto-transform call."""

        def read(self) -> QImageDouble:
            """Return a deterministic image double."""

            return QImageDouble()

    class QColorDouble:
        """Model color-channel reads needed by import-time image helpers."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            """Accept the production color constructor surface."""

        def redF(self) -> float:
            """Return a deterministic red channel."""

            return 0.0

        def greenF(self) -> float:
            """Return a deterministic green channel."""

            return 0.0

        def blueF(self) -> float:
            """Return a deterministic blue channel."""

            return 0.0

        def hslSaturationF(self) -> float:
            """Return a deterministic saturation channel."""

            return 0.0

    qtgui.QImage = QImageDouble
    qtgui.QImageReader = QImageReaderDouble
    qtgui.QColor = QColorDouble
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    transport = importlib.reload(
        importlib.import_module("substitute.infrastructure.comfy.websocket_transport")
    )
    module: Any = importlib.reload(
        importlib.import_module("substitute.infrastructure.comfy.websocket_listener")
    )
    module.websocket = transport.websocket
    module.decode_preview_image = lambda _image_bytes: object()
    module.Image = types.SimpleNamespace(open=lambda *_args, **_kwargs: object())
    module.QImage = qtgui.QImage
    return module


def _build_callbacks() -> tuple[
    ListenerCallbacks,
    list[ProgressUpdate],
    list[PreviewImageUpdate],
    list[OutputImageUpdate],
    list[ListenerFailure],
    list[ListenerCompleted],
]:
    """Create listener callbacks and their observable event collectors."""

    progress_events: list[ProgressUpdate] = []
    preview_events: list[PreviewImageUpdate] = []
    output_events: list[OutputImageUpdate] = []
    failures: list[ListenerFailure] = []
    completed: list[ListenerCompleted] = []
    callbacks = ListenerCallbacks(
        on_progress=progress_events.append,
        on_model_load_progress=lambda _event: None,
        on_preview=preview_events.append,
        on_output_image=output_events.append,
        on_failed=failures.append,
        on_timing=lambda _event: None,
        on_completed=completed.append,
    )
    return (
        callbacks,
        progress_events,
        preview_events,
        output_events,
        failures,
        completed,
    )


def _build_request(
    *,
    output_dir: Path,
    workflow_payload: JsonObject,
    workflow_id: str = "wf-1",
    workflow_name: str = "My Workflow",
    prompt_id: str = "pid-1",
    output_run_number: int | None = None,
    output_save_plan: OutputSavePlan | None = None,
) -> ListenerStartRequest:
    """Build one deterministic listener start request."""

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


def _patch_runtime_report_context(monkeypatch: MonkeyPatch) -> None:
    """Stabilize runtime-report facts published by listener failures."""

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


def _run_listener_messages(
    monkeypatch: MonkeyPatch,
    *,
    workflow_payload: JsonObject,
    messages: list[object],
    prompt_id: str = "pid-1",
    receive_error: Exception | None = None,
    close_events: list[bool] | None = None,
) -> tuple[list[ProgressUpdate], list[ListenerFailure], list[ListenerCompleted]]:
    """Run the listener against deterministic websocket messages."""

    module = _import_listener_module(monkeypatch)
    _patch_runtime_report_context(monkeypatch)
    callbacks, progress, _, _, failures, completed = _build_callbacks()

    class FakeWebSocket:
        """Serve the prescribed sequence and record no transport state."""

        def connect(self, _url: str) -> None:
            """Accept the listener connection."""

        def send(self, _payload: str) -> None:
            """Accept the listener handshake payload."""

        def recv(self) -> object:
            """Return the next deterministic event."""

            if receive_error is not None:
                raise receive_error
            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

            if close_events is not None:
                close_events.append(True)

    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
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
    monkeypatch: MonkeyPatch,
    *,
    workflow_payload: JsonObject,
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
    """Run the listener with deterministic timing and event-order collection."""

    module = _import_listener_module(monkeypatch)
    if clock_values is not None:
        clock_iter = iter(clock_values)
        last_clock_value = clock_values[-1]

        def next_clock_value() -> float:
            """Advance the injected clock without overflowing the supplied samples."""

            return next(clock_iter, last_clock_value)

        monkeypatch.setattr(listener_event_runtime, "perf_counter", next_clock_value)
    _patch_runtime_report_context(monkeypatch)
    progress_events: list[ProgressUpdate] = []
    timing_events: list[GenerationExecutionTiming] = []
    failures: list[ListenerFailure] = []
    completed: list[ListenerCompleted] = []
    event_order: list[str] = []

    def record_timing(event: GenerationExecutionTiming) -> None:
        """Record timing before completion for ordering assertions."""

        timing_events.append(event)
        event_order.append("timing")

    def record_completed(event: ListenerCompleted) -> None:
        """Record completion after all terminal timing callbacks."""

        completed.append(event)
        event_order.append("completed")

    callbacks = ListenerCallbacks(
        on_progress=progress_events.append,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=failures.append,
        on_timing=record_timing,
        on_completed=record_completed,
    )

    class FakeWebSocket:
        """Serve the prescribed sequence and record no transport state."""

        def connect(self, _url: str) -> None:
            """Accept the listener connection."""

        def send(self, _payload: str) -> None:
            """Accept the listener handshake payload."""

        def recv(self) -> object:
            """Return the next deterministic event."""

            return messages.pop(0)

        def close(self) -> None:
            """Accept listener cleanup."""

    monkeypatch.setattr(module.websocket, "WebSocket", FakeWebSocket)
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
