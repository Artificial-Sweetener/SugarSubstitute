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

"""Connect the application child to its authoritative native supervisor."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, MutableMapping
import json
import logging
import os
import threading
from typing import Self

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceConnection,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    parse_application_invocation,
    receive_instance_message,
    send_instance_message,
)
from sugarsubstitute_shared.application_instance_transport import (
    connect_instance_endpoint,
)


_LOGGER = logging.getLogger(__name__)


class ApplicationSupervisorClient:
    """Receive launcher-owned invocation routing inside the application process."""

    def __init__(
        self,
        *,
        endpoint: ApplicationInstanceEndpoint,
        token: str,
        connection: ApplicationInstanceConnection,
    ) -> None:
        """Retain the authenticated supervisor channel."""

        self._endpoint = endpoint
        self._token = token
        self._connection = connection
        self._handler: Callable[[ApplicationInvocation], None] | None = None
        self._disconnect_handler: Callable[[], None] | None = None
        self._disconnected = False
        self._pending: deque[ApplicationInvocation] = deque(maxlen=64)
        self._lock = threading.Lock()
        self._closing = threading.Event()
        self._reader = threading.Thread(
            target=self._receive_invocations,
            name="application-supervisor-client",
            daemon=True,
        )
        self._reader.start()

    @classmethod
    def connect_from_environment(
        cls,
        environment: MutableMapping[str, str] | None = None,
    ) -> Self | None:
        """Connect using one-use child credentials and remove inherited secrets."""

        source = os.environ if environment is None else environment
        endpoint_value = source.get(BROKER_ENDPOINT_ENV)
        token = source.get(BROKER_TOKEN_ENV)
        if not endpoint_value or not token:
            return None
        endpoint = ApplicationInstanceEndpoint.from_json(endpoint_value)
        connection = connect_instance_endpoint(endpoint)
        send_instance_message(connection, {"kind": "register-child", "token": token})
        response = receive_instance_message(connection)
        if response.get("status") != "accepted":
            connection.close()
            raise ApplicationInstanceBrokerError(
                "The application supervisor rejected child registration."
            )
        source.pop(BROKER_ENDPOINT_ENV, None)
        source.pop(BROKER_TOKEN_ENV, None)
        return cls(endpoint=endpoint, token=token, connection=connection)

    def bind_invocation_handler(
        self,
        handler: Callable[[ApplicationInvocation], None],
    ) -> None:
        """Bind the application owner and replay startup invocations once."""

        with self._lock:
            self._handler = handler
            pending = tuple(self._pending)
            self._pending.clear()
        for invocation in pending:
            handler(invocation)

    def request_restart(self) -> bool:
        """Ask the existing supervisor to relaunch after this child exits."""

        try:
            connection = connect_instance_endpoint(self._endpoint)
            try:
                send_instance_message(
                    connection,
                    {"kind": "restart", "token": self._token},
                )
                return receive_instance_message(connection).get("status") == "accepted"
            finally:
                connection.close()
        except OSError:
            return False

    def bind_disconnect_handler(self, handler: Callable[[], None]) -> None:
        """Bind child shutdown to loss of the authoritative supervisor."""

        with self._lock:
            self._disconnect_handler = handler
            disconnected = self._disconnected
        if disconnected:
            handler()

    def close(self) -> None:
        """Disconnect from the supervisor idempotently."""

        if self._closing.is_set():
            return
        self._closing.set()
        try:
            self._connection.close()
        except OSError:
            pass

    def _receive_invocations(self) -> None:
        """Receive forwarded invocations without blocking the Qt event loop."""

        try:
            while not self._closing.is_set():
                invocation = parse_application_invocation(
                    receive_instance_message(self._connection)
                )
                with self._lock:
                    handler = self._handler
                    if handler is None:
                        self._pending.append(invocation)
                        continue
                handler(invocation)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        finally:
            if self._closing.is_set():
                return
            with self._lock:
                self._disconnected = True
                disconnect_handler = self._disconnect_handler
            if disconnect_handler is not None:
                _LOGGER.warning("Application lost its authoritative supervisor")
                disconnect_handler()


__all__ = ["ApplicationSupervisorClient"]
