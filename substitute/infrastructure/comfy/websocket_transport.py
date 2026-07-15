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

"""Own websocket-client transport primitives for Comfy listener sessions."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any, Protocol, cast

import websocket

from substitute.domain.common import WorkflowId
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("infrastructure.comfy.websocket_transport")


class WebSocketClient(Protocol):
    """Describe the websocket-client surface used by the Comfy listener."""

    def connect(self, *args: object, **kwargs: object) -> object:
        """Connect to a websocket endpoint."""

    def send(self, payload: str) -> object:
        """Send one websocket message."""

    def recv(self) -> object:
        """Receive one websocket message."""

    def close(self) -> object:
        """Close the websocket connection."""


@dataclass
class PreconnectedComfyWebsocketSession:
    """Own a live Comfy websocket that is ready before prompt queueing."""

    client_id: str
    websocket_url: str
    websocket_client: WebSocketClient
    _closed: bool = False

    @classmethod
    def connect(
        cls,
        *,
        client_id: str,
        websocket_url: str,
        connect_timeout_seconds: float,
    ) -> "PreconnectedComfyWebsocketSession":
        """Open the websocket and send preview metadata feature flags first."""

        websocket_client = create_websocket_client()
        try:
            connect_websocket(
                websocket_client,
                websocket_url=websocket_url,
                connect_timeout_seconds=connect_timeout_seconds,
            )
            send_preview_feature_flags(
                websocket_client,
                client_id=client_id,
            )
        except Exception:
            close_websocket(
                websocket_client,
                workflow_id=None,
                generation_run_id=None,
                prompt_id=None,
            )
            raise
        return cls(
            client_id=client_id,
            websocket_url=websocket_url,
            websocket_client=websocket_client,
        )

    def close(self) -> None:
        """Close the websocket at most once."""

        if self._closed:
            return
        self._closed = True
        close_websocket(
            self.websocket_client,
            workflow_id=None,
            generation_run_id=None,
            prompt_id=None,
        )


def is_timeout_error(error: BaseException) -> bool:
    """Return True when exception indicates websocket timeout semantics."""

    return isinstance(error, (TimeoutError, socket.timeout)) or (
        error.__class__.__name__ == "WebSocketTimeoutException"
    )


def is_disconnect_error(error: BaseException) -> bool:
    """Return True when exception indicates websocket disconnect semantics."""

    if isinstance(error, ConnectionError):
        return True
    if isinstance(error, (ConnectionResetError, ConnectionAbortedError)):
        return True
    error_name = error.__class__.__name__
    if error_name in {
        "WebSocketConnectionClosedException",
        "WebSocketBadStatusException",
    }:
        return True
    cause = getattr(error, "__cause__", None)
    if isinstance(cause, BaseException):
        return is_disconnect_error(cause)
    return False


def create_websocket_client() -> WebSocketClient:
    """Create a websocket-client instance for Comfy websocket transport."""

    return cast(WebSocketClient, websocket.WebSocket())


def set_receive_timeout(
    websocket_client: WebSocketClient,
    timeout_seconds: float,
) -> None:
    """Apply a receive timeout when the websocket implementation supports it."""

    if hasattr(websocket_client, "settimeout"):
        cast(Any, websocket_client).settimeout(timeout_seconds)


def connect_websocket(
    websocket_client: WebSocketClient,
    *,
    websocket_url: str,
    connect_timeout_seconds: float,
) -> None:
    """Connect a websocket-client instance using the supported timeout API."""

    try:
        cast_client = cast(Any, websocket_client)
        cast_client.connect(
            websocket_url,
            timeout=connect_timeout_seconds,
        )
    except TypeError:
        cast(Any, websocket_client).connect(websocket_url)


def send_preview_feature_flags(
    websocket_client: WebSocketClient,
    *,
    client_id: str,
) -> None:
    """Send Comfy preview metadata feature flags as the first client message."""

    feature_flags = {
        "type": "feature_flags",
        "data": {"supports_preview_metadata": True},
    }
    cast(Any, websocket_client).send(json.dumps(feature_flags))
    log_info(
        _LOGGER,
        "Sent Comfy websocket feature flags",
        client_id=client_id,
        supports_preview_metadata=True,
    )


def close_websocket(
    websocket_client: WebSocketClient,
    *,
    workflow_id: WorkflowId | None,
    generation_run_id: str | None,
    prompt_id: str | None,
) -> None:
    """Close a websocket-client instance while preserving close diagnostics."""

    try:
        websocket_client.close()
    except Exception as close_error:
        log_exception(
            _LOGGER,
            "Failed to close websocket client cleanly",
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            error=close_error,
        )
