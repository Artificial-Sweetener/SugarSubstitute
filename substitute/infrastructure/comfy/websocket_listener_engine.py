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

"""Run the blocking Comfy websocket listener loop without Qt dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.application.errors import ErrorReport
from substitute.infrastructure.comfy.binary_websocket_event_router import (
    BinaryWebsocketEventRouter,
)
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    ComfyWebsocketEventRouter,
    WebsocketProgressEmission,
)
from substitute.infrastructure.comfy.text_websocket_event_parser import (
    parse_text_websocket_message,
)
from substitute.infrastructure.comfy.prompt_liveness import PromptLivenessProbe
from substitute.infrastructure.comfy.websocket_transport import (
    WebSocketClient,
    is_disconnect_error,
    is_timeout_error,
    set_receive_timeout,
)


class JsonMessageRouter(Protocol):
    """Describe JSON message routing behavior needed by the engine."""

    def route_message(
        self,
        *,
        message_type: object,
        data: Mapping[str, object],
    ) -> object:
        """Route a parsed JSON websocket message."""


class BinaryMessageRouter(Protocol):
    """Describe binary message routing behavior needed by the engine."""

    def route_event(self, event_payload: object, *, all_node_ids: set[str]) -> None:
        """Route one raw binary websocket payload."""


@dataclass(frozen=True)
class ListenerEngineCallbacks:
    """Provide listener side-effect callbacks used by the receive engine."""

    on_text_message: Callable[[Mapping[str, object]], None]
    on_progress: Callable[[WebsocketProgressEmission], None]


@dataclass(frozen=True)
class ListenerEngineResult:
    """Describe the terminal outcome returned by the receive engine."""

    prompt_finished: bool


class ListenerEngineExecutionError(RuntimeError):
    """Carry routed execution failure detail through listener failure handling."""

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        error_report: ErrorReport | None = None,
    ) -> None:
        """Store a user-facing message and optional diagnostic report."""

        super().__init__(message)
        self.detail = detail
        self.error_report = error_report


class ListenerEngineInterrupted(ListenerEngineExecutionError):
    """Represent an expected terminal interruption reported by Comfy."""


@dataclass(frozen=True)
class ComfyWebsocketListenerEngine:
    """Own blocking websocket receive, parse, and route orchestration."""

    websocket_client: WebSocketClient
    receive_timeout_seconds: float
    active_prompt_id: str
    prompt_liveness_probe: PromptLivenessProbe
    all_node_ids: set[str]
    json_event_router: ComfyWebsocketEventRouter | JsonMessageRouter
    binary_event_router: BinaryWebsocketEventRouter | BinaryMessageRouter
    callbacks: ListenerEngineCallbacks

    def run(self) -> ListenerEngineResult:
        """Receive websocket payloads until prompt completion or failure."""

        set_receive_timeout(self.websocket_client, self.receive_timeout_seconds)
        while True:
            try:
                event_payload = self._receive_payload()
            except TimeoutError as timeout_error:
                liveness_result = self._resolve_idle_interval(timeout_error)
                if liveness_result is not None:
                    return liveness_result
                continue
            if isinstance(event_payload, str):
                text_message = parse_text_websocket_message(event_payload)
                self.callbacks.on_text_message(text_message.message)
                route = self.json_event_router.route_message(
                    message_type=text_message.message_type,
                    data=text_message.data,
                )
                if bool(getattr(route, "interrupted", False)):
                    raise ListenerEngineInterrupted("Generation interrupted")
                failure = getattr(route, "failure", None)
                if failure is not None:
                    raise ListenerEngineExecutionError(
                        str(getattr(failure, "message")),
                        detail=_string_or_none(getattr(failure, "detail", None)),
                        error_report=_error_report_or_none(
                            getattr(failure, "error_report", None)
                        ),
                    )
                progress_emission = getattr(route, "progress_emission", None)
                if isinstance(progress_emission, WebsocketProgressEmission):
                    self.callbacks.on_progress(progress_emission)
                if bool(getattr(route, "prompt_finished", False)):
                    return ListenerEngineResult(prompt_finished=True)
                continue

            self.binary_event_router.route_event(
                event_payload,
                all_node_ids=self.all_node_ids,
            )

    def _receive_payload(self) -> object:
        """Receive one payload while normalizing transport failures."""

        try:
            return self.websocket_client.recv()
        except Exception as recv_error:
            if is_timeout_error(recv_error):
                raise TimeoutError(
                    "Comfy websocket listener timed out waiting for events "
                    f"(receive_timeout_seconds={self.receive_timeout_seconds})."
                ) from recv_error
            if is_disconnect_error(recv_error):
                raise ConnectionError(
                    "Comfy websocket connection closed before generation completed."
                ) from recv_error
            raise

    def _resolve_idle_interval(
        self,
        timeout_error: TimeoutError,
    ) -> ListenerEngineResult | None:
        """Continue active prompts and normalize verified terminal idle states."""

        observation = self.prompt_liveness_probe.observe(self.active_prompt_id)
        if observation.state == "active":
            return None
        if observation.state == "succeeded":
            return ListenerEngineResult(prompt_finished=True)
        if observation.state == "failed":
            raise ListenerEngineExecutionError(
                "Comfy reported prompt failure after websocket inactivity.",
                detail=observation.detail,
            ) from timeout_error
        if observation.state == "unavailable":
            raise ConnectionError(
                "Unable to verify Comfy prompt liveness after websocket inactivity: "
                f"{observation.detail}"
            ) from timeout_error
        raise TimeoutError(
            "Comfy stopped reporting websocket events and the active prompt could "
            f"not be found: {observation.detail}"
        ) from timeout_error


def _string_or_none(value: object) -> str | None:
    """Return string values while preserving optional fields."""

    return value if isinstance(value, str) else None


def _error_report_or_none(value: object) -> ErrorReport | None:
    """Return typed error reports while preserving optional fields."""

    return value if isinstance(value, ErrorReport) else None


__all__ = [
    "BinaryMessageRouter",
    "ComfyWebsocketListenerEngine",
    "JsonMessageRouter",
    "ListenerEngineCallbacks",
    "ListenerEngineExecutionError",
    "ListenerEngineInterrupted",
    "ListenerEngineResult",
]
