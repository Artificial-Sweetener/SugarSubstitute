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

"""Delegate launcher coordination while retaining the baseline's native broker."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
    RoutedApplicationInvocation,
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    receive_instance_message,
    send_instance_message,
)
from sugarsubstitute_shared.application_instance_transport import (
    connect_instance_endpoint,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)

_LOGGER = logging.getLogger(__name__)


class DelegatedApplicationBroker:
    """Use an authenticated owner session without acquiring or releasing its lease."""

    def __init__(self, environment: Mapping[str, str]) -> None:
        """Authenticate retained credentials before exposing broker operations."""
        endpoint = environment.get(BROKER_ENDPOINT_ENV)
        token = environment.get(BROKER_TOKEN_ENV)
        if not endpoint or not token:
            raise ApplicationInstanceBrokerError(
                "Delegated launcher credentials are missing."
            )
        self._endpoint = ApplicationInstanceEndpoint.from_json(endpoint)
        self._token = token
        self._credentials = {BROKER_ENDPOINT_ENV: endpoint, BROKER_TOKEN_ENV: token}
        self._closed = False
        self._startup_client: ApplicationSupervisorClient | None = None
        self._request("supervisor-session")

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Pass the retained owner's credentials through each supervised child hop."""
        self._require_open()
        return {**environment, **self._credentials}

    def release_startup_resource(self, identity: str) -> None:
        """Ask the creating supervisor to close only this startup resource."""
        self._request(
            "release-startup-resource", resource_identity=identity, timeout_seconds=10.0
        )

    def consume_restart_request(self) -> bool:
        """Consume restart state atomically at the baseline broker."""
        response = self._request("consume-restart")
        requested = response.get("restart")
        if not isinstance(requested, bool):
            raise ApplicationInstanceBrokerError("Invalid delegated restart response.")
        return requested

    def bind_startup_presenter(
        self, presenter: Callable[[ApplicationInvocation], str | None] | None
    ) -> None:
        """Temporarily register a startup surface through the existing child channel."""
        self._require_open()
        if self._startup_client is not None:
            self._startup_client.close()
            self._startup_client = None
        if presenter is None:
            return
        client = ApplicationSupervisorClient.connect_from_environment(
            dict(self._credentials)
        )
        if client is None:
            raise ApplicationInstanceBrokerError(
                "Delegated startup registration failed."
            )
        self._startup_client = client

        def present(request: RoutedApplicationInvocation) -> None:
            """Return an explicit outcome for every delegated startup invocation."""
            surface: str | None = None
            try:
                surface = presenter(request.invocation)
            except Exception:
                _LOGGER.exception("Delegated startup presentation failed")
            client.complete_invocation(
                request.request_id,
                outcome="presented" if surface is not None else "unavailable",
                surface=surface or "startup-unavailable",
            )

        client.bind_invocation_handler(present)

    def close(self) -> None:
        """Close the session's startup channel while leaving native ownership intact."""
        if self._closed:
            return
        self._closed = True
        if self._startup_client is not None:
            self._startup_client.close()
            self._startup_client = None

    def _require_open(self) -> None:
        """Reject reuse after this delegated process has released its session."""
        if self._closed:
            raise ApplicationInstanceBrokerError(
                "Delegated launcher session is closed."
            )

    def _request(
        self,
        kind: str,
        *,
        resource_identity: str | None = None,
        timeout_seconds: float = 2.0,
    ) -> dict[str, object]:
        """Bound every authenticated control request and release its connection."""
        self._require_open()
        connection = connect_instance_endpoint(self._endpoint)
        try:
            message: dict[str, object] = {"kind": kind, "token": self._token}
            if resource_identity is not None:
                message["resource_identity"] = resource_identity
            send_instance_message(connection, message)
            response = receive_instance_message(
                connection, timeout_seconds=timeout_seconds
            )
            if response.get("status") != "accepted":
                raise ApplicationInstanceBrokerError(
                    "Delegated launcher request was rejected."
                )
            return response
        finally:
            connection.close()
