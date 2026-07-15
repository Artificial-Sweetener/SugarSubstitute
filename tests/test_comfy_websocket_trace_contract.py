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

"""Contract tests for focused Comfy websocket trace logging."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pytest import LogCaptureFixture

from substitute.infrastructure.comfy.websocket_trace import ComfyWebsocketTrace


def _prompt_nodes() -> dict[str, object]:
    """Return prompt nodes with model-ish fields for trace tests."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "_meta": {"title": "Base.Checkpoint"},
            "inputs": {"ckpt_name": "D:\\models\\sdxl\\base.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "_meta": {"title": "Sampler.KSampler"},
            "inputs": {"steps": 28},
        },
        "3": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "Output.CubeOutput"},
            "inputs": {},
        },
    }


def test_disabled_trace_emits_no_logs(caplog: LogCaptureFixture) -> None:
    """Disabled tracing should be silent."""
    caplog.set_level(logging.DEBUG)
    trace = ComfyWebsocketTrace(enabled=False)

    trace.trace_message(
        message={"type": "executing", "data": {"prompt_id": "pid", "node": "1"}},
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert caplog.text == ""


def test_enabled_trace_logs_executing_node_context(
    caplog: LogCaptureFixture,
) -> None:
    """Executing summaries should include node and model-loader context."""
    caplog.set_level(logging.DEBUG)
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={
            "type": "executing",
            "data": {"prompt_id": "pid", "node": "1", "display_node": "1"},
        },
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert "event_type=executing" in caplog.text
    assert "node_id=1" in caplog.text
    assert "class_type=CheckpointLoaderSimple" in caplog.text
    assert "is_model_loader_candidate=True" in caplog.text
    assert "model_inputs=ckpt_name=base.safetensors" in caplog.text


def test_trace_ignores_other_prompt_ids(caplog: LogCaptureFixture) -> None:
    """Prompt-scoped tracing should not log unrelated prompt events."""
    caplog.set_level(logging.INFO)
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={"type": "executing", "data": {"prompt_id": "other", "node": "1"}},
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert caplog.text == ""


def test_progress_summary_includes_derived_percent(
    caplog: LogCaptureFixture,
) -> None:
    """Scalar progress summaries should include derived bounded percentages."""
    caplog.set_level(logging.DEBUG)
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={
            "type": "progress",
            "data": {"prompt_id": "pid", "node": "2", "value": 14, "max": 28},
        },
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert "event_type=progress" in caplog.text
    assert "node_id=2" in caplog.text
    assert "class_type=KSampler" in caplog.text
    assert "percent=50.0" in caplog.text


def test_progress_state_summary_includes_running_and_finished_nodes(
    caplog: LogCaptureFixture,
) -> None:
    """progress_state summaries should compactly expose node states."""
    caplog.set_level(logging.INFO)
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={
            "type": "progress_state",
            "data": {
                "prompt_id": "pid",
                "nodes": {
                    "1": {"state": "finished", "value": 1, "max": 1},
                    "2": {"state": "running", "value": 7, "max": 28},
                },
            },
        },
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert "event_type=progress_state" in caplog.text
    assert "running_nodes=2:KSampler:running:25.0" in caplog.text
    assert "finished_nodes=1:CheckpointLoaderSimple:finished:100.0" in caplog.text


def test_model_load_progress_summary_is_not_unknown(
    caplog: LogCaptureFixture,
) -> None:
    """Backend model-load telemetry should log as a focused known event."""
    caplog.set_level(logging.INFO)
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={
            "type": "substitute_model_load_progress",
            "data": {
                "prompt_id": "pid",
                "display_node_id": "1",
                "phase": "dynamic_vram_staging",
                "state": "running",
                "percent": 42.5,
                "model_class": "SDXL",
                "model_name": "example.safetensors",
                "source_node_id": "1",
                "source_input_key": "ckpt_name",
            },
        },
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert "Comfy websocket model-load progress" in caplog.text
    assert "Comfy websocket unknown event" not in caplog.text
    assert "event_type=substitute_model_load_progress" in caplog.text
    assert "node_id=1" in caplog.text
    assert "percent=42.5" in caplog.text
    assert "model_name=example.safetensors" in caplog.text
    assert "source_node_id=1" in caplog.text
    assert "source_input_key=ckpt_name" in caplog.text


def test_progress_rate_limiting_suppresses_same_bucket(
    caplog: LogCaptureFixture,
) -> None:
    """Repeated progress in the same bucket should not flood logs."""
    caplog.set_level(logging.DEBUG)
    current_time = 100.0
    trace = ComfyWebsocketTrace(enabled=True, clock=lambda: current_time)

    for value in (1, 2, 3, 11):
        trace.trace_message(
            message={
                "type": "progress",
                "data": {"prompt_id": "pid", "node": "2", "value": value, "max": 100},
            },
            active_prompt_id="pid",
            prompt_nodes=_prompt_nodes(),
        )

    assert caplog.text.count("Comfy websocket progress") == 2
    assert "percent=1.0" in caplog.text
    assert "percent=11.0" in caplog.text


def test_unknown_event_summary_logs_keys_not_payload(
    caplog: LogCaptureFixture,
) -> None:
    """Unknown event summaries should expose shape without dumping values."""
    caplog.set_level(logging.INFO)
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={
            "type": "new_custom_event",
            "data": {"prompt_id": "pid", "secret_path": "D:\\models\\secret.ckpt"},
        },
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert "event_type=new_custom_event" in caplog.text
    assert "data_keys=prompt_id,secret_path" in caplog.text
    assert "secret.ckpt" not in caplog.text


def test_from_environment_uses_trace_flag(
    monkeypatch: pytest.MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    """The trace helper should honor SUGAR_COMFY_WS_TRACE truthy values."""
    monkeypatch.setenv("SUGAR_COMFY_WS_TRACE", "yes")
    caplog.set_level(logging.INFO)

    trace = ComfyWebsocketTrace.from_environment()
    trace.trace_message(
        message={"type": "execution_start", "data": {"prompt_id": "pid"}},
        active_prompt_id="pid",
        prompt_nodes=_prompt_nodes(),
    )

    assert "event_type=execution_start" in caplog.text


def test_path_like_model_values_are_sanitized(
    caplog: LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Path-like model inputs should be reduced to basenames."""
    caplog.set_level(logging.INFO)
    prompt_nodes = _prompt_nodes()
    prompt_nodes["1"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": str(tmp_path / "nested" / "private.safetensors")},
    }
    trace = ComfyWebsocketTrace(enabled=True)

    trace.trace_message(
        message={"type": "executing", "data": {"prompt_id": "pid", "node": "1"}},
        active_prompt_id="pid",
        prompt_nodes=prompt_nodes,
    )

    assert "model_inputs=ckpt_name=private.safetensors" in caplog.text
    assert str(tmp_path) not in caplog.text
