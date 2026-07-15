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

"""Open and close listener-owned Comfy websocket sessions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.domain.common import WorkflowId
from substitute.infrastructure.comfy.websocket_transport import (
    PreconnectedComfyWebsocketSession,
    WebSocketClient,
    close_websocket,
    connect_websocket,
    create_websocket_client,
    send_preview_feature_flags,
)


@dataclass(frozen=True)
class ListenerWebsocketSession:
    """Expose an opened websocket client with its close owner."""

    websocket_client: WebSocketClient
    close_owner: Callable[[], None]

    def close(self) -> None:
        """Close the session through its authoritative owner."""

        self.close_owner()


@dataclass(frozen=True)
class ListenerWebsocketConnectionManager:
    """Open fresh or preconnected websocket sessions for one listener run."""

    client_id: str
    websocket_url: str
    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str
    connect_timeout_seconds: float
    preconnected_session: PreconnectedComfyWebsocketSession | None = None
    create_client: Callable[[], WebSocketClient] = create_websocket_client
    connect_client: Callable[[WebSocketClient, str, float], None] = (
        lambda client, websocket_url, connect_timeout_seconds: connect_websocket(
            client,
            websocket_url=websocket_url,
            connect_timeout_seconds=connect_timeout_seconds,
        )
    )
    send_feature_flags: Callable[[WebSocketClient, str], None] = (
        lambda client, client_id: send_preview_feature_flags(
            client,
            client_id=client_id,
        )
    )
    close_client: Callable[[WebSocketClient, WorkflowId, str, str], None] = (
        lambda client, workflow_id, generation_run_id, prompt_id: close_websocket(
            client,
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
        )
    )

    def open(self) -> ListenerWebsocketSession:
        """Return an opened websocket session ready for listener event reads."""

        if self.preconnected_session is not None:
            return ListenerWebsocketSession(
                websocket_client=self.preconnected_session.websocket_client,
                close_owner=self.preconnected_session.close,
            )

        websocket_client = self.create_client()
        try:
            self.connect_client(
                websocket_client,
                self.websocket_url,
                self.connect_timeout_seconds,
            )
            self.send_feature_flags(websocket_client, self.client_id)
        except Exception:
            self.close_client(
                websocket_client,
                self.workflow_id,
                self.generation_run_id,
                self.prompt_id,
            )
            raise

        return ListenerWebsocketSession(
            websocket_client=websocket_client,
            close_owner=lambda: self.close_client(
                websocket_client,
                self.workflow_id,
                self.generation_run_id,
                self.prompt_id,
            ),
        )


__all__ = [
    "ListenerWebsocketConnectionManager",
    "ListenerWebsocketSession",
]
