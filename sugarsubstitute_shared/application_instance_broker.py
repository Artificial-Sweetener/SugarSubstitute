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

"""Own fileless application election and supervisor IPC for one installation account."""

from __future__ import annotations

from sugarsubstitute_shared.application_instance_election import (
    ApplicationInstanceReservation,
    SelectedInstallationReservation,
    reserve_application_instance,
)

from collections.abc import Callable, Mapping
import json
import logging
import os
from pathlib import Path
import secrets
import threading
from typing import Self

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceBrokerError,
    ApplicationInvocation,
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    parse_routed_application_invocation,
    receive_instance_message,
    send_instance_message,
)
from sugarsubstitute_shared.application_invocation_router import (
    ApplicationInvocationRouter,
)
from sugarsubstitute_shared.application_instance_bindings import (
    ApplicationInstanceBindings,
)


from sugarsubstitute_shared.startup_resource_owner import StartupResourceOwner


_LOGGER = logging.getLogger(__name__)
_MAXIMUM_PENDING_INVOCATIONS = 64
_SUPERVISOR_RECEIPT_DEADLINE_SECONDS = 14.0
_CONNECTION_HANDSHAKE_TIMEOUT_SECONDS = 2.0


class ApplicationInstanceBroker:
    """Elect one supervisor and route later invocations to its application child."""

    def __init__(
        self,
        *,
        reservation: ApplicationInstanceReservation,
        child_token: str,
        accept_listener_invocations: bool,
        reserve_selected: SelectedInstallationReservation | None = None,
    ) -> None:
        """Start accepting invocations on the already-claimed native endpoint."""

        self._endpoint = reservation.endpoint
        self._child_token = child_token
        self._accept_listener_invocations = accept_listener_invocations
        self._closing = threading.Event()
        self._restart_requested = threading.Event()
        self._restart_lock = threading.Lock()
        self._startup_resources = StartupResourceOwner()
        self._router = ApplicationInvocationRouter(
            child_token=child_token,
            closing=self._closing,
            maximum_active_requests=_MAXIMUM_PENDING_INVOCATIONS,
            receipt_deadline_seconds=_SUPERVISOR_RECEIPT_DEADLINE_SECONDS,
        )
        try:
            self._bindings = ApplicationInstanceBindings(
                reservation,
                closing=self._closing,
                handle_connection=self._handle_connection,
                reserve_selected=reserve_selected,
            )
        except BaseException:
            self._router.close()
            self._startup_resources.close()
            raise

    @classmethod
    def elect(
        cls,
        *,
        install_root: Path,
        invocation: ApplicationInvocation,
        reserve_selected: SelectedInstallationReservation | None = None,
    ) -> Self | None:
        """Become the supervisor or forward this invocation to the elected owner."""

        reservation = reserve_application_instance(install_root, invocation)
        if reservation is None:
            return None
        _LOGGER.info(
            "Elected application supervisor through native IPC | owner_pid=%s | transport=%s",
            os.getpid(),
            reservation.endpoint.transport,
        )
        try:
            return cls(
                reservation=reservation,
                child_token=secrets.token_urlsafe(32),
                accept_listener_invocations=True,
                reserve_selected=reserve_selected,
            )
        except BaseException:
            reservation.close()
            raise

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

        with self._restart_lock:
            if not self._restart_requested.is_set():
                return False
            self._restart_requested.clear()
            return True

    def register_startup_resource(self, cleanup: Callable[[], None]) -> str:
        """Retain cleanup locally and return a generation-specific release identity."""
        return self._startup_resources.register(cleanup)

    def release_startup_resource(self, identity: str) -> bool:
        """Release only the matching resource through its original process owner."""
        return self._startup_resources.release(identity)

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
        self._startup_resources.close()
        stopped = self._bindings.close()
        self._router.close()
        _LOGGER.info(
            "Application supervisor shutdown completed | owner_pid=%s | transport=%s | accept_threads_stopped=%s",
            os.getpid(),
            self._endpoint.transport,
            stopped,
        )

    def __enter__(self) -> Self:
        """Return this active broker for context-managed supervision."""

        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Release native ownership when supervision finishes."""

        self.close()

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
            if kind == "claim-installation":
                root = message.get("install_root")
                if not isinstance(root, str) or not Path(root).is_absolute():
                    send_instance_message(connection, {"status": "rejected"})
                    return
                try:
                    admitted = self._bindings.claim(
                        Path(root),
                        on_activity=lambda: send_instance_message(
                            connection, {"status": "pending"}
                        ),
                    )
                except ApplicationInstanceBrokerError:
                    _LOGGER.warning(
                        "Selected installation admission failed", exc_info=True
                    )
                    send_instance_message(connection, {"status": "rejected"})
                    return
                send_instance_message(
                    connection, {"status": "admitted" if admitted else "presented"}
                )
                return
            if kind == "register-child":
                retain_connection = True
                self._router.register_child(connection)
                return
            if kind == "restart":
                with self._restart_lock:
                    self._restart_requested.set()
                send_instance_message(connection, {"status": "accepted"})
                return
            if kind == "release-startup-resource":
                identity = message.get("resource_identity")
                released = isinstance(identity, str) and self.release_startup_resource(
                    identity
                )
                send_instance_message(
                    connection, {"status": "accepted" if released else "rejected"}
                )
                return
            if kind == "supervisor-session":
                send_instance_message(connection, {"status": "accepted"})
                return
            if kind == "consume-restart":
                send_instance_message(
                    connection,
                    {"status": "accepted", "restart": self.consume_restart_request()},
                )
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


__all__ = [
    "ApplicationInstanceBroker",
]
