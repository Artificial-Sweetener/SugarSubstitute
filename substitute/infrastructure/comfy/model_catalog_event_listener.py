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

"""Listen for Substitute BackEnd model catalog websocket change events."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from itertools import count
from typing import Any, Protocol, cast
from uuid import uuid4

import websocket

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.domain.model_metadata import (
    MODEL_CATALOG_CHANGE_EVENT_TYPE,
    BackendModelCatalogChangeEvent,
    parse_backend_model_catalog_change_event,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.execution.long_lived_task import LongLivedWork
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_DEFAULT_BACKOFF_SECONDS = (1.0, 2.0, 5.0, 15.0)
_LOGGER = get_logger("infrastructure.comfy.model_catalog_event_listener")

UpdateCallback = Callable[[BackendModelCatalogChangeEvent], None]
ReconnectCallback = Callable[[], BackendModelCatalogChangeEvent | None]
WebSocketFactory = Callable[[], Any]
ListenerTaskFactory = Callable[
    [TaskIdentity, ExecutionContext, LongLivedWork[None], str],
    "ListenerTaskHandle",
]
_LISTENER_REQUEST_IDS = count(1)


class ListenerTaskHandle(Protocol):
    """Describe the long-lived task handle used by event listeners."""

    @property
    def is_finished(self) -> bool:
        """Return whether the listener task has completed."""

    def stop(self, *, reason: str) -> None:
        """Request listener task shutdown."""


class ModelCatalogEventListener:
    """Maintain a persistent target websocket listener for model catalog changes."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint,
        on_update: UpdateCallback,
        latest_change_provider: ReconnectCallback | None = None,
        websocket_factory: WebSocketFactory | None = None,
        task_factory: ListenerTaskFactory | None = None,
        backoff_seconds: tuple[float, ...] = _DEFAULT_BACKOFF_SECONDS,
        receive_timeout_seconds: float = 5.0,
    ) -> None:
        """Store endpoint and callback dependencies for background listening."""

        self._endpoint = endpoint
        self._on_update = on_update
        self._latest_change_provider = latest_change_provider
        self._websocket_factory = websocket_factory or websocket.WebSocket
        self._task_factory = task_factory
        self._backoff_seconds = backoff_seconds
        self._receive_timeout_seconds = receive_timeout_seconds
        self._handle: ListenerTaskHandle | None = None
        self._last_revision = ""

    @property
    def is_running(self) -> bool:
        """Return whether the listener task is currently active."""

        handle = self._handle
        return handle is not None and not handle.is_finished

    def start(self) -> None:
        """Start the listener task once."""

        if self.is_running:
            return
        if self._task_factory is None:
            log_warning(
                _LOGGER,
                "Model catalog event listener has no execution task factory",
                host=self._endpoint.host,
                port=self._endpoint.port,
            )
            return
        self._handle = self._task_factory(
            TaskIdentity(
                request_id=next(_LISTENER_REQUEST_IDS),
                domain="model_catalog_event_listener",
            ),
            ExecutionContext(
                operation="model_catalog_event_listener",
                reason="backend_event_listener",
                lane="backend_event_listener",
                safe_fields=(
                    ("host", self._endpoint.host),
                    ("port", self._endpoint.port),
                ),
            ),
            lambda cancellation: self._run(cancellation),
            "substitute-model-catalog-event-listener",
        )

    def stop(self) -> None:
        """Request listener shutdown and wait briefly for the task to exit."""

        handle = self._handle
        if handle is None:
            return
        handle.stop(reason="model_catalog_event_listener_stop")
        if handle.is_finished:
            self._handle = None

    def _run(self, cancellation: CancellationSource) -> None:
        """Reconnect until stopped so model folder changes keep flowing."""

        backoff_index = 0
        expected_disconnect_warning_emitted = False
        while not cancellation.is_cancelled:
            try:
                self._recover_latest_change()
                self._listen_once(cancellation)
                backoff_index = 0
                expected_disconnect_warning_emitted = False
            except Exception as exc:
                if cancellation.is_cancelled:
                    return
                delay = self._backoff_seconds[
                    min(backoff_index, len(self._backoff_seconds) - 1)
                ]
                backoff_index += 1
                if _is_expected_disconnect(exc):
                    log_context = {
                        "reconnect_delay_seconds": delay,
                        "error": repr(exc),
                    }
                    if expected_disconnect_warning_emitted:
                        log_info(
                            _LOGGER,
                            "Model catalog websocket listener disconnected; reconnecting",
                            **log_context,
                        )
                    else:
                        expected_disconnect_warning_emitted = True
                        log_warning(
                            _LOGGER,
                            "Model catalog websocket listener disconnected; reconnecting",
                            **log_context,
                        )
                else:
                    log_exception(
                        _LOGGER,
                        "Model catalog websocket listener failed; reconnecting",
                        reconnect_delay_seconds=delay,
                    )
                self._sleep_until_cancelled(cancellation, delay)

    def _recover_latest_change(self) -> None:
        """Fetch the latest change event after reconnect when a provider exists."""

        if self._latest_change_provider is None:
            return
        try:
            latest_change = self._latest_change_provider()
        except Exception:
            log_exception(_LOGGER, "Failed to fetch latest model catalog change")
            return
        if latest_change is None or latest_change.revision == self._last_revision:
            return
        self._dispatch(latest_change)

    def _listen_once(self, cancellation: CancellationSource) -> None:
        """Open one websocket connection and process messages until it closes."""

        client = self._websocket_factory()
        client_id = f"substitute-model-catalog-{uuid4().hex}"
        url = self._endpoint.websocket_url(client_id)
        try:
            log_info(
                _LOGGER,
                "Model catalog websocket listener connecting",
                websocket_url=url,
                client_id=client_id,
            )
            try:
                cast(Any, client).connect(url, timeout=self._receive_timeout_seconds)
            except TypeError:
                cast(Any, client).connect(url)
            settimeout = getattr(client, "settimeout", None)
            if callable(settimeout):
                settimeout(self._receive_timeout_seconds)
            log_info(
                _LOGGER,
                "Model catalog websocket listener connected",
                websocket_url=url,
                client_id=client_id,
            )
            while not cancellation.is_cancelled:
                try:
                    payload = client.recv()
                except Exception as exc:
                    if _is_timeout_error(exc):
                        continue
                    raise
                if isinstance(payload, str):
                    self._handle_text_message(payload)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    log_warning(_LOGGER, "Failed to close model catalog websocket")

    def _sleep_until_cancelled(
        self,
        cancellation: CancellationSource,
        delay_seconds: float,
    ) -> None:
        """Sleep in short intervals so cancellation can interrupt reconnect backoff."""

        deadline = time.monotonic() + delay_seconds
        while not cancellation.is_cancelled and time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def _handle_text_message(self, payload: str) -> None:
        """Parse one text websocket message and dispatch supported updates."""

        try:
            message = json.loads(payload)
        except json.JSONDecodeError:
            log_warning(_LOGGER, "Ignored malformed model catalog websocket JSON")
            return
        if (
            not isinstance(message, dict)
            or message.get("type") != MODEL_CATALOG_CHANGE_EVENT_TYPE
        ):
            return
        data = message.get("data")
        if not isinstance(data, Mapping):
            return
        event = parse_backend_model_catalog_change_event(data)
        if event is None:
            log_warning(_LOGGER, "Ignored malformed model catalog change event")
            return
        self._dispatch(event)

    def _dispatch(self, event: BackendModelCatalogChangeEvent) -> None:
        """Dispatch one parsed update and remember its revision."""

        if event.revision == self._last_revision:
            return
        self._last_revision = event.revision
        log_info(
            _LOGGER,
            "Received model catalog websocket change event",
            revision=event.revision,
            previous_revision=event.previous_revision,
            reason=event.reason,
            kinds=event.kinds,
            affected_node_classes=event.affected_node_classes,
        )
        self._on_update(event)


def _is_timeout_error(exc: Exception) -> bool:
    """Return whether a websocket exception represents receive timeout."""

    text = str(exc).lower()
    return "timed out" in text or "timeout" in text


def _is_expected_disconnect(exc: Exception) -> bool:
    """Return whether an exception is normal for a persistent websocket."""

    return _is_timeout_error(exc) or isinstance(
        exc,
        (
            websocket.WebSocketConnectionClosedException,
            websocket.WebSocketException,
            ConnectionError,
            OSError,
        ),
    )


__all__ = ["ModelCatalogEventListener"]
