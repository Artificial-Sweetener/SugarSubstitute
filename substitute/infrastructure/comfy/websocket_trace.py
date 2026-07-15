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

"""Emit focused Comfy websocket diagnostics for model-loading investigation."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any

from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
    log_debug,
)

_LOGGER = get_logger("infrastructure.comfy.websocket_trace")
_TRACE_ENV = "SUGAR_COMFY_WS_TRACE"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_PROGRESS_BUCKET_SIZE = 10
_PROGRESS_HEARTBEAT_SECONDS = 5.0
_KNOWN_EVENT_TYPES = {
    "execution_start",
    "execution_cached",
    "executing",
    "executed",
    "progress",
    "progress_state",
    "substitute_model_load_progress",
    "execution_success",
    "execution_error",
    "execution_interrupted",
}
_MODEL_INPUT_FRAGMENTS = (
    "model",
    "ckpt",
    "checkpoint",
    "lora",
    "vae",
    "clip",
    "unet",
    "diffusion",
)
_MODEL_CLASS_FRAGMENTS = (
    "loader",
    "checkpoint",
    "lora",
    "vae",
    "clip",
    "unet",
    "diffusion",
)


@dataclass
class _ProgressTraceState:
    """Track the last emitted progress summary for one prompt/node/event key."""

    state: str | None
    bucket: int | None
    emitted_at: float


class ComfyWebsocketTrace:
    """Emit env-gated summaries of Comfy websocket events."""

    def __init__(self, *, enabled: bool, clock: Any = time.monotonic) -> None:
        """Initialize trace state and progress rate-limiting dependencies."""
        self._enabled = enabled
        self._clock = clock
        self._progress_state: dict[tuple[str, str, str], _ProgressTraceState] = {}

    @classmethod
    def from_environment(cls) -> ComfyWebsocketTrace:
        """Create a trace helper using SUGAR_COMFY_WS_TRACE."""
        enabled = os.environ.get(_TRACE_ENV, "").strip().lower() in _TRUE_VALUES
        return cls(enabled=enabled)

    def trace_message(
        self,
        *,
        message: dict[str, object],
        active_prompt_id: str,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log a compact summary for one text websocket message when enabled."""
        if not self._enabled:
            return

        event_type = message.get("type")
        if not isinstance(event_type, str) or not event_type:
            log_warning(_LOGGER, "Comfy websocket trace ignored malformed event")
            return

        data = message.get("data", {})
        if not isinstance(data, dict):
            data = {}

        prompt_id = _string_or_none(data.get("prompt_id"))
        if prompt_id is not None and prompt_id != active_prompt_id:
            return

        if event_type == "execution_start":
            self._trace_lifecycle(event_type, prompt_id)
        elif event_type == "execution_cached":
            self._trace_execution_cached(data, prompt_id, prompt_nodes)
        elif event_type == "executing":
            self._trace_executing(data, prompt_id, prompt_nodes)
        elif event_type == "executed":
            self._trace_executed(data, prompt_id, prompt_nodes)
        elif event_type == "progress":
            self._trace_progress(data, prompt_id, prompt_nodes)
        elif event_type == "progress_state":
            self._trace_progress_state(data, prompt_id, prompt_nodes)
        elif event_type == "substitute_model_load_progress":
            self._trace_model_load_progress(data, prompt_id, prompt_nodes)
        elif event_type in {
            "execution_success",
            "execution_error",
            "execution_interrupted",
        }:
            self._trace_terminal_event(event_type, data, prompt_id, prompt_nodes)
        else:
            self._trace_unknown(event_type, data, prompt_id)

    def trace_estimator_progress(
        self,
        *,
        source_event: str,
        prompt_id: str,
        workflow_percent: float | None,
        sampler_percent: float | None,
    ) -> None:
        """Log the app-side workflow estimate produced from websocket events."""

        if not self._enabled:
            return
        log_info(
            _LOGGER,
            "Comfy websocket progress estimator",
            event_type="progress_estimator",
            source_event=source_event,
            prompt_id=prompt_id,
            workflow_percent=workflow_percent,
            sampler_percent=sampler_percent,
        )

    def _trace_lifecycle(self, event_type: str, prompt_id: str | None) -> None:
        """Log a prompt lifecycle event summary."""
        log_info(
            _LOGGER,
            "Comfy websocket event",
            event_type=event_type,
            prompt_id=prompt_id,
        )

    def _trace_execution_cached(
        self,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log cached-node summary for a prompt."""
        node_ids = [str(node_id) for node_id in _list_or_empty(data.get("nodes"))]
        cached_nodes = ",".join(
            _format_node_reference(node_id, prompt_nodes) for node_id in node_ids[:12]
        )
        log_info(
            _LOGGER,
            "Comfy websocket event",
            event_type="execution_cached",
            prompt_id=prompt_id,
            cached_count=len(node_ids),
            cached_nodes=cached_nodes,
        )

    def _trace_executing(
        self,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log the node Comfy is starting or the final completion marker."""
        node_id = _string_or_none(data.get("node"))
        if node_id is None:
            log_info(
                _LOGGER,
                "Comfy websocket event",
                event_type="executing",
                prompt_id=prompt_id,
                node_id=None,
                phase="complete",
            )
            return

        node_context = _node_context(node_id, prompt_nodes)
        log_info(
            _LOGGER,
            "Comfy websocket event",
            event_type="executing",
            prompt_id=prompt_id,
            display_node_id=_string_or_none(data.get("display_node")),
            is_model_loader_candidate=is_model_loader_candidate(
                node_context.class_type,
                node_context.node_data,
            ),
            model_inputs=_format_model_inputs(node_context.model_inputs),
            **node_context.log_fields(),
        )

    def _trace_executed(
        self,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log a compact executed-node event summary."""
        node_id = _string_or_none(data.get("node"))
        node_context = _node_context(node_id, prompt_nodes)
        log_info(
            _LOGGER,
            "Comfy websocket event",
            event_type="executed",
            prompt_id=prompt_id,
            has_output=data.get("output") is not None,
            **node_context.log_fields(),
        )

    def _trace_progress(
        self,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log a rate-limited scalar progress event summary."""
        node_id = _string_or_none(data.get("node"))
        value = _float_or_none(data.get("value"))
        maximum = _float_or_none(data.get("max"))
        percent = _percent(value, maximum)
        if not self._should_log_progress(
            event_type="progress",
            prompt_id=prompt_id,
            node_id=node_id,
            state=None,
            percent=percent,
        ):
            return

        node_context = _node_context(node_id, prompt_nodes)
        log_debug(
            _LOGGER,
            "Comfy websocket progress",
            event_type="progress",
            prompt_id=prompt_id,
            value=value,
            max=maximum,
            percent=percent,
            **node_context.log_fields(),
        )

    def _trace_progress_state(
        self,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log a rate-limited progress_state snapshot summary."""
        nodes = data.get("nodes", {})
        if not isinstance(nodes, dict):
            log_warning(
                _LOGGER,
                "Comfy websocket trace ignored malformed progress_state",
                prompt_id=prompt_id,
            )
            return

        running: list[str] = []
        finished: list[str] = []
        should_log = False
        for node_id, raw_state in nodes.items():
            if not isinstance(raw_state, dict):
                continue
            node_id_str = str(node_id)
            state = _string_or_none(raw_state.get("state"))
            value = _float_or_none(raw_state.get("value"))
            maximum = _float_or_none(raw_state.get("max"))
            percent = _percent(value, maximum)
            if self._should_log_progress(
                event_type="progress_state",
                prompt_id=prompt_id,
                node_id=node_id_str,
                state=state,
                percent=percent,
            ):
                should_log = True
            summary = _format_node_progress(
                node_id=node_id_str,
                state=state,
                value=value,
                maximum=maximum,
                prompt_nodes=prompt_nodes,
            )
            if state == "running":
                running.append(summary)
            elif state == "finished":
                finished.append(summary)

        if not should_log:
            return

        log_info(
            _LOGGER,
            "Comfy websocket progress_state",
            event_type="progress_state",
            prompt_id=prompt_id,
            node_count=len(nodes),
            running_nodes=";".join(running[:8]),
            finished_nodes=";".join(finished[:12]),
        )

    def _trace_model_load_progress(
        self,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log rate-limited Substitute BackEnd model-loading telemetry."""
        node_id = _string_or_none(data.get("display_node_id")) or _string_or_none(
            data.get("node_id")
        )
        state = _string_or_none(data.get("state"))
        percent = _bounded_percent_value(_float_or_none(data.get("percent")))
        if not self._should_log_progress(
            event_type="substitute_model_load_progress",
            prompt_id=prompt_id,
            node_id=node_id,
            state=state,
            percent=percent,
        ):
            return

        node_context = _node_context(node_id, prompt_nodes)
        log_info(
            _LOGGER,
            "Comfy websocket model-load progress",
            event_type="substitute_model_load_progress",
            prompt_id=prompt_id,
            phase=_string_or_none(data.get("phase")),
            state=state,
            percent=percent,
            model_class=_string_or_none(data.get("model_class")),
            model_name=_string_or_none(data.get("model_name")),
            source_node_id=_string_or_none(data.get("source_node_id")),
            source_input_key=_string_or_none(data.get("source_input_key")),
            **node_context.log_fields(),
        )

    def _trace_terminal_event(
        self,
        event_type: str,
        data: dict[str, object],
        prompt_id: str | None,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Log execution terminal events and compact error details."""
        node_id = _string_or_none(data.get("node_id"))
        node_context = _node_context(node_id, prompt_nodes)
        log_info(
            _LOGGER,
            "Comfy websocket event",
            event_type=event_type,
            prompt_id=prompt_id,
            exception_type=_string_or_none(data.get("exception_type")),
            exception_message=_truncate(_string_or_none(data.get("exception_message"))),
            **node_context.log_fields(),
        )

    def _trace_unknown(
        self,
        event_type: str,
        data: dict[str, object],
        prompt_id: str | None,
    ) -> None:
        """Log an unknown text event without dumping its payload."""
        if event_type in _KNOWN_EVENT_TYPES:
            return
        log_info(
            _LOGGER,
            "Comfy websocket unknown event",
            event_type=event_type,
            prompt_id=prompt_id,
            data_keys=",".join(sorted(str(key) for key in data.keys())),
        )

    def _should_log_progress(
        self,
        *,
        event_type: str,
        prompt_id: str | None,
        node_id: str | None,
        state: str | None,
        percent: float | None,
    ) -> bool:
        """Return whether one noisy progress event should be emitted."""
        key = (prompt_id or "", node_id or "", event_type)
        now = float(self._clock())
        bucket = None if percent is None else int(percent // _PROGRESS_BUCKET_SIZE)
        previous = self._progress_state.get(key)
        if previous is None:
            self._progress_state[key] = _ProgressTraceState(state, bucket, now)
            return True
        if state != previous.state or bucket != previous.bucket or bucket == 10:
            self._progress_state[key] = _ProgressTraceState(state, bucket, now)
            return True
        if now - previous.emitted_at >= _PROGRESS_HEARTBEAT_SECONDS:
            self._progress_state[key] = _ProgressTraceState(state, bucket, now)
            return True
        return False


@dataclass(frozen=True)
class _NodeContext:
    """Summarize prompt node metadata used by trace log fields."""

    node_id: str | None
    class_type: str
    title: str | None
    node_data: dict[str, object]
    model_inputs: dict[str, str]

    def log_fields(self) -> dict[str, object]:
        """Return structured log fields for this node context."""
        return {
            "node_id": self.node_id,
            "class_type": self.class_type,
            "title": self.title,
        }


def is_model_loader_candidate(class_type: str, node_data: dict[str, object]) -> bool:
    """Return whether a node appears likely to load or mutate model state."""
    lowered_class_type = class_type.lower()
    if any(fragment in lowered_class_type for fragment in _MODEL_CLASS_FRAGMENTS):
        return True
    return bool(_model_inputs(node_data))


def _node_context(
    node_id: str | None,
    prompt_nodes: dict[str, object],
) -> _NodeContext:
    """Build log context for one prompt node id."""
    node_data = prompt_nodes.get(node_id or "")
    if not isinstance(node_data, dict):
        return _NodeContext(
            node_id=node_id,
            class_type="",
            title=None,
            node_data={},
            model_inputs={},
        )
    class_type = node_data.get("class_type")
    meta = node_data.get("_meta")
    title = meta.get("title") if isinstance(meta, dict) else None
    return _NodeContext(
        node_id=node_id,
        class_type=class_type if isinstance(class_type, str) else "",
        title=title if isinstance(title, str) else None,
        node_data=node_data,
        model_inputs=_model_inputs(node_data),
    )


def _model_inputs(node_data: dict[str, object]) -> dict[str, str]:
    """Return sanitized model-ish node inputs for trace output."""
    inputs = node_data.get("inputs", {})
    if not isinstance(inputs, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in inputs.items():
        key_str = str(key)
        lowered = key_str.lower()
        if not any(fragment in lowered for fragment in _MODEL_INPUT_FRAGMENTS):
            continue
        sanitized = _sanitize_input_value(raw_value)
        if sanitized is not None:
            result[key_str] = sanitized
    return result


def _sanitize_input_value(value: object) -> str | None:
    """Return a safe compact representation for one model-ish input value."""
    if isinstance(value, str):
        if "\\" in value or "/" in value or ":" in value:
            return PureWindowsPath(value).name
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _format_model_inputs(model_inputs: dict[str, str]) -> str:
    """Format sanitized model-ish inputs into one compact string."""
    return ",".join(f"{key}={value}" for key, value in sorted(model_inputs.items()))


def _format_node_reference(node_id: str, prompt_nodes: dict[str, object]) -> str:
    """Format one node id and class type for compact lists."""
    node_context = _node_context(node_id, prompt_nodes)
    if node_context.class_type:
        return f"{node_id}:{node_context.class_type}"
    return node_id


def _format_node_progress(
    *,
    node_id: str,
    state: str | None,
    value: float | None,
    maximum: float | None,
    prompt_nodes: dict[str, object],
) -> str:
    """Format one node's progress_state entry for compact logging."""
    node_context = _node_context(node_id, prompt_nodes)
    percent = _percent(value, maximum)
    class_type = node_context.class_type or "unknown"
    if percent is None:
        return f"{node_id}:{class_type}:{state or 'unknown'}"
    return f"{node_id}:{class_type}:{state or 'unknown'}:{percent:.1f}"


def _list_or_empty(value: object) -> list[object]:
    """Return a list value or an empty list for malformed payload fields."""
    return value if isinstance(value, list) else []


def _string_or_none(value: object) -> str | None:
    """Return a string representation for scalar websocket fields."""
    if value is None:
        return None
    if isinstance(value, (str, int)):
        return str(value)
    return None


def _float_or_none(value: object) -> float | None:
    """Return a float for numeric websocket fields."""
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _percent(value: float | None, maximum: float | None) -> float | None:
    """Return a bounded percentage from value/max websocket fields."""
    if value is None or maximum is None or maximum <= 0:
        return None
    return min(100.0, max(0.0, 100.0 * value / maximum))


def _bounded_percent_value(value: float | None) -> float | None:
    """Return a bounded percentage value when telemetry already supplies one."""
    if value is None:
        return None
    return min(100.0, max(0.0, value))


def _truncate(value: str | None, limit: int = 240) -> str | None:
    """Return a compact exception message for trace logs."""
    if value is None or len(value) <= limit:
        return value
    return f"{value[:limit]}..."


__all__ = ["ComfyWebsocketTrace", "is_model_loader_candidate"]
