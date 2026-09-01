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

"""Own fileless application election and supervisor IPC for one user session."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
import json
import logging
from pathlib import Path
import secrets
import sys
import threading
import time
from typing import Protocol, Self

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    parse_application_invocation,
    receive_instance_message,
    send_instance_message,
)
from sugarsubstitute_shared.application_instance_transport import (
    ApplicationInstanceListener,
    bind_instance_listener,
    connect_instance_endpoint,
    endpoint_is_already_owned,
    instance_endpoint,
    instance_identity,
)


_LOGGER = logging.getLogger(__name__)


class _InstanceOwnerClaim(Protocol):
    """Retain an auxiliary native ownership resource until broker shutdown."""

    def close(self) -> None:
        """Release native ownership idempotently."""


class ApplicationInstanceBroker:
    """Elect one supervisor and route later invocations to its application child."""

    def __init__(
        self,
        *,
        endpoint: ApplicationInstanceEndpoint,
        listener: ApplicationInstanceListener,
        child_token: str,
        owner_claim: _InstanceOwnerClaim | None,
        accept_listener_invocations: bool,
    ) -> None:
        """Start accepting invocations on the already-claimed native endpoint."""

        self._endpoint = endpoint
        self._listener = listener
        self._child_token = child_token
        self._owner_claim = owner_claim
        self._accept_listener_invocations = accept_listener_invocations
        self._closing = threading.Event()
        self._restart_requested = threading.Event()
        self._pending: deque[ApplicationInvocation] = deque(maxlen=64)
        self._state_lock = threading.Lock()
        self._child_socket: ApplicationInstanceConnection | None = None
        self._child_send_lock = threading.Lock()
        self._accept_thread = threading.Thread(
            target=self._accept_connections,
            name="application-instance-broker",
            daemon=True,
        )
        self._accept_thread.start()

    @classmethod
    def elect(
        cls,
        *,
        install_root: Path,
        invocation: ApplicationInvocation,
    ) -> Self | None:
        """Become the supervisor or forward this invocation to the elected owner."""

        identity = instance_identity(install_root)
        endpoint = instance_endpoint(identity)
        owner_claim: _InstanceOwnerClaim | None = None
        native_invocation_binder: (
            Callable[[Callable[[ApplicationInvocation], None]], None] | None
        ) = None
        if sys.platform.startswith("linux"):
            from sugarsubstitute_shared.application_instance_linux import (
                LinuxSessionBusElection,
                acquire_linux_session_bus,
            )

            bus_result = acquire_linux_session_bus(identity)
            if bus_result.election is LinuxSessionBusElection.SECONDARY:
                _forward_invocation(endpoint, invocation)
                return None
            owner_claim = bus_result.claim
        elif sys.platform == "darwin":
            from sugarsubstitute_shared.application_instance_macos import (
                MacOSMessagePortElection,
                acquire_macos_message_port,
                forward_macos_invocation,
            )

            message_port_result = acquire_macos_message_port(identity)
            if message_port_result.election is MacOSMessagePortElection.SECONDARY:
                forward_macos_invocation(identity, invocation)
                return None
            owner_claim = message_port_result.claim
            if message_port_result.claim is not None:
                native_invocation_binder = (
                    message_port_result.claim.bind_invocation_handler
                )
        try:
            listener = bind_instance_listener(endpoint)
        except OSError as error:
            if owner_claim is not None:
                owner_claim.close()
            if native_invocation_binder is not None:
                raise
            if not endpoint_is_already_owned(error):
                raise
            try:
                _forward_invocation(endpoint, invocation)
                _LOGGER.info(
                    "Forwarded launch to the active application supervisor",
                    extra={"instance_transport": endpoint.transport},
                )
                return None
            except BaseException:
                raise ApplicationInstanceBrokerError(
                    "Application instance election lost, but the elected supervisor "
                    "could not accept this invocation."
                ) from error
        _LOGGER.info(
            "Elected application supervisor through native IPC",
            extra={"instance_transport": endpoint.transport},
        )
        broker = cls(
            endpoint=endpoint,
            listener=listener,
            child_token=secrets.token_urlsafe(32),
            owner_claim=owner_claim,
            accept_listener_invocations=native_invocation_binder is None,
        )
        if native_invocation_binder is not None:
            native_invocation_binder(broker._route_invocation)
        return broker

    def child_environment(
        self,
        environment: Mapping[str, str],
    ) -> dict[str, str]:
        """Authorize one supervised application child to receive broker commands."""

        child_environment = dict(environment)
        child_environment[BROKER_ENDPOINT_ENV] = self._endpoint.to_json()
        child_environment[BROKER_TOKEN_ENV] = self._child_token
        return child_environment

    def consume_restart_request(self) -> bool:
        """Return and clear the child's one pending supervised restart request."""

        if not self._restart_requested.is_set():
            return False
        self._restart_requested.clear()
        return True

    def close(self) -> None:
        """Stop routing and release all OS-owned resources idempotently."""

        if self._closing.is_set():
            return
        self._closing.set()
        try:
            self._listener.close()
        except OSError:
            pass
        if threading.current_thread() is not self._accept_thread:
            self._accept_thread.join()
        with self._state_lock:
            child_socket = self._child_socket
            self._child_socket = None
        if child_socket is not None:
            try:
                child_socket.close()
            except OSError:
                pass
        if self._owner_claim is not None:
            self._owner_claim.close()
            self._owner_claim = None

    def __enter__(self) -> Self:
        """Return this active broker for context-managed supervision."""

        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Release native ownership when supervision finishes."""

        self.close()

    def _accept_connections(self) -> None:
        """Accept local requests until the supervisor releases ownership."""

        while not self._closing.is_set():
            try:
                connection = self._listener.accept()
            except OSError:
                if not self._closing.is_set():
                    time.sleep(0.01)
                continue
            threading.Thread(
                target=self._handle_connection,
                args=(connection,),
                name="application-instance-request",
                daemon=True,
            ).start()

    def _handle_connection(self, connection: ApplicationInstanceConnection) -> None:
        """Validate and route one invocation or child control request."""

        retain_connection = False
        try:
            message = receive_instance_message(connection)
            kind = message.get("kind")
            if kind == "invoke":
                if not self._accept_listener_invocations:
                    send_instance_message(connection, {"status": "rejected"})
                    return
                invocation = parse_application_invocation(message)
                self._route_invocation(invocation)
                send_instance_message(connection, {"status": "accepted"})
                return
            token = message.get("token")
            if not isinstance(token, str) or not secrets.compare_digest(
                token, self._child_token
            ):
                _LOGGER.warning(
                    "Rejected unauthenticated application supervisor request",
                    extra={"request_kind": kind},
                )
                send_instance_message(connection, {"status": "rejected"})
                return
            if kind == "register-child":
                retain_connection = True
                self._register_child(connection)
                return
            if kind == "restart":
                self._restart_requested.set()
                send_instance_message(connection, {"status": "accepted"})
                return
            send_instance_message(connection, {"status": "rejected"})
        except (OSError, ValueError, json.JSONDecodeError):
            _LOGGER.debug(
                "Application instance request ended before completion",
                exc_info=True,
            )
            return
        finally:
            if not retain_connection:
                try:
                    connection.close()
                except OSError:
                    pass

    def _register_child(self, connection: ApplicationInstanceConnection) -> None:
        """Replace the supervised child channel and flush queued invocations."""

        with self._state_lock:
            previous = self._child_socket
            self._child_socket = connection
            pending = tuple(self._pending)
            self._pending.clear()
        if previous is not None:
            try:
                previous.close()
            except OSError:
                pass
        send_instance_message(connection, {"status": "accepted"})
        try:
            for invocation in pending:
                send_instance_message(connection, invocation.to_message())
            while not self._closing.is_set():
                connection.receive_frame(1)
        except OSError:
            pass
        finally:
            with self._state_lock:
                if self._child_socket is connection:
                    self._child_socket = None
            try:
                connection.close()
            except OSError:
                pass

    def _route_invocation(self, invocation: ApplicationInvocation) -> None:
        """Deliver immediately or retain a bounded startup invocation."""

        with self._state_lock:
            child_socket = self._child_socket
            if child_socket is None:
                self._pending.append(invocation)
                return
        try:
            with self._child_send_lock:
                send_instance_message(child_socket, invocation.to_message())
        except OSError:
            with self._state_lock:
                if self._child_socket is child_socket:
                    self._child_socket = None
                self._pending.append(invocation)


def _forward_invocation(
    endpoint: ApplicationInstanceEndpoint,
    invocation: ApplicationInvocation,
) -> None:
    """Forward a secondary launch and require explicit supervisor acceptance."""

    connection = connect_instance_endpoint(endpoint)
    try:
        send_instance_message(connection, invocation.to_message())
        response = receive_instance_message(connection)
    finally:
        connection.close()
    if response.get("status") != "accepted":
        raise ApplicationInstanceBrokerError(
            "The active application supervisor rejected the invocation."
        )


__all__ = [
    "ApplicationInstanceBroker",
]
