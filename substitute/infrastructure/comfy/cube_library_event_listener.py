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

"""Listen for Substitute BackEnd Cube Library websocket change events."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from itertools import count
from typing import Any, Mapping, Protocol, cast
from uuid import uuid4

import websocket

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskIdentity,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.execution.long_lived_task import LongLivedWork
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

EVENT_TYPE = "substitute_cube_library_changed"
_SUPPORTED_SCHEMA_VERSION = 1
_DEFAULT_BACKOFF_SECONDS = (1.0, 2.0, 5.0, 15.0)
_LOGGER = get_logger("infrastructure.comfy.cube_library_event_listener")


@dataclass(frozen=True, slots=True)
class CubeLibraryChangedUpdate:
    """Represent a parsed Cube Library change notification."""

    schema_version: int
    catalog_revision: str
    previous_catalog_revision: str
    generated_at: str
    reason: str


UpdateCallback = Callable[[CubeLibraryChangedUpdate], None]
WebSocketFactory = Callable[[], Any]
SleepCallback = Callable[[float], None]
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


class CubeLibraryEventListener:
    """Maintain a persistent target websocket listener for Cube Library changes."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint,
        on_update: UpdateCallback,
        websocket_factory: WebSocketFactory | None = None,
        task_factory: ListenerTaskFactory | None = None,
        backoff_seconds: tuple[float, ...] = _DEFAULT_BACKOFF_SECONDS,
        receive_timeout_seconds: float = 5.0,
    ) -> None:
        """Store endpoint and callback dependencies for background listening."""

        self._endpoint = endpoint
        self._on_update = on_update
        self._websocket_factory = websocket_factory or websocket.WebSocket
        self._task_factory = task_factory
        self._backoff_seconds = backoff_seconds
        self._receive_timeout_seconds = receive_timeout_seconds
        self._handle: ListenerTaskHandle | None = None

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
                "Cube Library event listener has no execution task factory",
                host=self._endpoint.host,
                port=self._endpoint.port,
            )
            return
        self._handle = self._task_factory(
            TaskIdentity(
                request_id=next(_LISTENER_REQUEST_IDS),
                domain="cube_library_event_listener",
            ),
            ExecutionContext(
                operation="cube_library_event_listener",
                reason="backend_event_listener",
                lane="backend_event_listener",
                safe_fields=(
                    ("host", self._endpoint.host),
                    ("port", self._endpoint.port),
                ),
            ),
            lambda cancellation: self._run(cancellation),
            "substitute-cube-library-event-listener",
        )

    def stop(self) -> None:
        """Request listener shutdown and wait briefly for the task to exit."""

        handle = self._handle
        if handle is None:
            return
        handle.stop(reason="cube_library_event_listener_stop")
        if handle.is_finished:
            self._handle = None

    def _run(self, cancellation: CancellationSource) -> None:
        """Reconnect until stopped so library changes keep flowing."""

        backoff_index = 0
        expected_disconnect_warning_emitted = False
        while not cancellation.is_cancelled:
            try:
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
                            "Cube Library websocket listener disconnected; reconnecting",
                            **log_context,
                        )
                    else:
                        expected_disconnect_warning_emitted = True
                        log_warning(
                            _LOGGER,
                            "Cube Library websocket listener disconnected; reconnecting",
                            **log_context,
                        )
                else:
                    log_exception(
                        _LOGGER,
                        "Cube Library websocket listener failed; reconnecting",
                        reconnect_delay_seconds=delay,
                    )
                self._sleep_until_cancelled(cancellation, delay)

    def _listen_once(self, cancellation: CancellationSource) -> None:
        """Open one websocket connection and process messages until it closes."""

        client = self._websocket_factory()
        client_id = f"substitute-cube-library-{uuid4().hex}"
        url = self._endpoint.websocket_url(client_id)
        try:
            log_info(
                _LOGGER,
                "Cube Library websocket listener connecting",
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
                "Cube Library websocket listener connected",
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
                    log_warning(_LOGGER, "Failed to close Cube Library websocket")

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
            log_warning(_LOGGER, "Ignored malformed Cube Library websocket JSON")
            return
        if not isinstance(message, dict) or message.get("type") != EVENT_TYPE:
            return
        data = message.get("data")
        if not isinstance(data, dict):
            return
        update = parse_cube_library_changed_update(cast(Mapping[str, object], data))
        if update is None:
            log_warning(_LOGGER, "Ignored malformed Cube Library change event")
            return
        log_info(
            _LOGGER,
            "Received Cube Library websocket change event",
            catalog_revision=update.catalog_revision,
            previous_catalog_revision=update.previous_catalog_revision,
            generated_at=update.generated_at,
            reason=update.reason,
        )
        self._on_update(update)
        log_info(
            _LOGGER,
            "Dispatched Cube Library websocket change event",
            catalog_revision=update.catalog_revision,
            previous_catalog_revision=update.previous_catalog_revision,
            reason=update.reason,
        )


def parse_cube_library_changed_update(
    data: Mapping[str, object],
) -> CubeLibraryChangedUpdate | None:
    """Parse a version 1 Cube Library change event payload."""

    schema_version = data.get("schemaVersion")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != _SUPPORTED_SCHEMA_VERSION
    ):
        return None
    catalog_revision = _required_string(data.get("catalogRevision"))
    previous_catalog_revision = _required_string(data.get("previousCatalogRevision"))
    generated_at = _required_string(data.get("generatedAt"))
    reason = _required_string(data.get("reason"))
    if (
        catalog_revision is None
        or previous_catalog_revision is None
        or generated_at is None
        or reason is None
    ):
        return None
    return CubeLibraryChangedUpdate(
        schema_version=schema_version,
        catalog_revision=catalog_revision,
        previous_catalog_revision=previous_catalog_revision,
        generated_at=generated_at,
        reason=reason,
    )


def _required_string(value: object) -> str | None:
    """Return a non-empty string payload field."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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


__all__ = [
    "CubeLibraryChangedUpdate",
    "CubeLibraryEventListener",
    "parse_cube_library_changed_update",
]
