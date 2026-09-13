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

from collections.abc import Callable, Mapping
import json
import logging
import os
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
    RoutedApplicationInvocation,
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    parse_routed_application_invocation,
    receive_instance_message,
    send_instance_message,
)
from sugarsubstitute_shared.application_invocation_router import (
    ApplicationInvocationRouter,
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
_MAXIMUM_PENDING_INVOCATIONS = 64
_PRESENTATION_TIMEOUT_SECONDS = 15.0
_SUPERVISOR_RECEIPT_DEADLINE_SECONDS = 14.0
_CONNECTION_HANDSHAKE_TIMEOUT_SECONDS = 2.0


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
        self._router = ApplicationInvocationRouter(
            child_token=child_token,
            closing=self._closing,
            maximum_active_requests=_MAXIMUM_PENDING_INVOCATIONS,
            receipt_deadline_seconds=_SUPERVISOR_RECEIPT_DEADLINE_SECONDS,
        )
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
            )

            message_port_result = acquire_macos_message_port(identity)
            if message_port_result.election is MacOSMessagePortElection.SECONDARY:
                _forward_invocation(endpoint, invocation)
                return None
            owner_claim = message_port_result.claim
        try:
            listener = bind_instance_listener(endpoint)
        except OSError as error:
            if owner_claim is not None:
                owner_claim.close()
            if not endpoint_is_already_owned(error):
                raise
            try:
                _forward_invocation(endpoint, invocation)
                _LOGGER.info(
                    "Forwarded launch to the active application supervisor",
                    extra={"instance_transport": endpoint.transport},
                )
                return None
            except ApplicationInstanceBrokerError:
                raise
            except BaseException:
                raise ApplicationInstanceBrokerError(
                    "Application instance election lost, but the elected supervisor "
                    "could not accept this invocation."
                ) from error
        _LOGGER.info(
            "Elected application supervisor through native IPC | owner_pid=%s | "
            "transport=%s",
            os.getpid(),
            endpoint.transport,
        )
        broker = cls(
            endpoint=endpoint,
            listener=listener,
            child_token=secrets.token_urlsafe(32),
            owner_claim=owner_claim,
            accept_listener_invocations=True,
        )
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

    def bind_startup_presenter(
        self,
        presenter: Callable[[ApplicationInvocation], str | None] | None,
    ) -> None:
        """Expose a visible startup or recovery surface before child registration."""

        self._router.bind_startup_presenter(presenter)

    def close(self) -> None:
        """Stop routing and release all OS-owned resources idempotently."""

        if self._closing.is_set():
            return
        self._closing.set()
        try:
            self._listener.close()
        except OSError:
            pass
        self._router.close()
        if threading.current_thread() is not self._accept_thread:
            self._accept_thread.join(timeout=2.0)
            if self._accept_thread.is_alive():
                _LOGGER.warning("Application instance accept thread did not stop")
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
            message = receive_instance_message(
                connection,
                timeout_seconds=_CONNECTION_HANDSHAKE_TIMEOUT_SECONDS,
            )
            kind = message.get("kind")
            if kind == "invoke":
                if not self._accept_listener_invocations:
                    send_instance_message(connection, {"status": "rejected"})
                    return
                invocation = parse_routed_application_invocation(message)
                retain_connection = self._router.route_invocation(
                    invocation,
                    waiter=connection,
                )
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
                self._router.register_child(connection)
                return
            if kind == "restart":
                self._restart_requested.set()
                send_instance_message(connection, {"status": "accepted"})
                return
            send_instance_message(connection, {"status": "rejected"})
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
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


def _forward_invocation(
    endpoint: ApplicationInstanceEndpoint,
    invocation: ApplicationInvocation,
) -> None:
    """Forward a secondary launch and require explicit supervisor acceptance."""

    request = RoutedApplicationInvocation(
        request_id=secrets.token_urlsafe(24),
        invocation=invocation,
    )
    _LOGGER.info(
        "Forwarding secondary invocation | requester_pid=%s | request_id=%s | "
        "transport=%s",
        os.getpid(),
        request.request_id,
        endpoint.transport,
    )
    try:
        connection = connect_instance_endpoint(endpoint)
    except OSError as error:
        raise ApplicationInstanceBrokerError(
            "The active application supervisor could not be reached.",
            endpoint=endpoint,
        ) from error
    owner_process_id = connection.peer_process_id()
    try:
        send_instance_message(connection, request.to_message())
        try:
            response = receive_instance_message(
                connection,
                timeout_seconds=_PRESENTATION_TIMEOUT_SECONDS,
            )
            owner_process_id = _response_owner_process_id(
                response,
                fallback=owner_process_id,
            )
        except (OSError, TimeoutError) as error:
            raise ApplicationInstanceBrokerError(
                "The active application did not present a usable window in time.",
                owner_process_id=owner_process_id,
                endpoint=endpoint,
            ) from error
    finally:
        connection.close()
    if (
        response.get("status") != "presented"
        or response.get("request_id") != request.request_id
    ):
        raise ApplicationInstanceBrokerError(
            "The active application could not present a usable window.",
            owner_process_id=owner_process_id,
            endpoint=endpoint,
        )
    _LOGGER.info(
        "Secondary invocation produced a visible surface | requester_pid=%s | "
        "owner_pid=%s | request_id=%s | surface=%s",
        os.getpid(),
        owner_process_id,
        request.request_id,
        response.get("surface"),
    )


def _response_owner_process_id(
    response: Mapping[str, object],
    *,
    fallback: int | None,
) -> int | None:
    """Prefer the supervisor identity carried by its authenticated response."""

    owner_process_id = response.get("owner_process_id")
    if (
        isinstance(owner_process_id, int)
        and not isinstance(owner_process_id, bool)
        and owner_process_id > 0
    ):
        return owner_process_id
    return fallback


__all__ = [
    "ApplicationInstanceBroker",
]
