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

"""Forward launch requests and retain authenticated process identity for recovery."""

from __future__ import annotations
from collections.abc import Mapping
import logging
import os
import secrets
import sys
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
    ApplicationInstanceBrokerError,
    ApplicationInstanceFailureReason,
    RoutedApplicationInvocation,
    NativeApplicationInstanceOwner,
    send_instance_message,
    receive_instance_message,
)
from sugarsubstitute_shared.application_instance_transport import (
    connect_instance_endpoint,
)
from sugarsubstitute_shared.application_instance_owner import (
    capture_native_instance_owner,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
    capture_process_identity,
)

_LOGGER = logging.getLogger(__name__)
_PRESENTATION_TIMEOUT_SECONDS = 15.0


def forward_application_invocation(
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
    owner_process_id: int | None = None
    owner_identity: ProcessIdentity | None = None
    native_owner: NativeApplicationInstanceOwner | None = None
    try:
        try:
            owner_process_id = connection.peer_process_id()
            owner_identity = _capture_owner(owner_process_id)
            if owner_process_id is not None:
                _require_accessible_owner_session(endpoint, owner_identity)
                if owner_identity is not None:
                    native_owner = capture_native_instance_owner(
                        endpoint, owner_identity
                    )
            send_instance_message(connection, request.to_message())
            response = receive_instance_message(
                connection,
                timeout_seconds=_PRESENTATION_TIMEOUT_SECONDS,
            )
            response_owner = _response_owner_process_id(
                response,
                fallback=owner_process_id,
            )
            if owner_process_id is None:
                owner_process_id = response_owner
                owner_identity = _capture_owner(owner_process_id)
        except (OSError, TimeoutError) as error:
            raise ApplicationInstanceBrokerError(
                "The active application did not present a usable window in time.",
                owner_identity=owner_identity,
                endpoint=endpoint,
                native_owner=native_owner,
            ) from error
    finally:
        connection.close()
    if (
        response.get("status") != "presented"
        or response.get("request_id") != request.request_id
    ):
        owner_is_closing = response.get("surface") in {
            "application-closing",
            "supervisor-closing",
        }
        raise ApplicationInstanceBrokerError(
            "The active application could not present a usable window.",
            owner_identity=owner_identity,
            endpoint=endpoint,
            native_owner=native_owner,
            owner_is_closing=owner_is_closing,
        )
    _require_accessible_owner_session(endpoint, owner_identity)
    _LOGGER.info(
        "Secondary invocation produced a visible surface | requester_pid=%s | "
        "owner_pid=%s | request_id=%s | surface=%s",
        os.getpid(),
        owner_process_id,
        request.request_id,
        response.get("surface"),
    )


def _require_accessible_owner_session(
    endpoint: ApplicationInstanceEndpoint, owner: ProcessIdentity | None
) -> None:
    """Keep a different Windows desktop from acknowledging usable local activation."""
    if sys.platform != "win32":
        return
    from sugarsubstitute_shared.windows_process_security import process_session_id

    try:
        if owner is None:
            raise OSError("The native application owner could not be identified.")
        requester_session = process_session_id(os.getpid())
        owner_session = process_session_id(owner.pid)
    except OSError as error:
        raise ApplicationInstanceBrokerError(
            "The active application's desktop session could not be verified.",
            reason=ApplicationInstanceFailureReason.SESSION_UNVERIFIED,
            owner_identity=owner,
            endpoint=endpoint,
        ) from error
    if requester_session != owner_session:
        _LOGGER.info(
            "Application owner is on another desktop session | owner_pid=%s | "
            "owner_session=%s | requester_session=%s",
            owner.pid,
            owner_session,
            requester_session,
        )
        raise ApplicationInstanceBrokerError(
            "The active application belongs to another Windows desktop session.",
            reason=ApplicationInstanceFailureReason.OTHER_SESSION,
            owner_identity=owner,
            endpoint=endpoint,
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


def _capture_owner(pid: int | None) -> ProcessIdentity | None:
    """Keep activation usable if its peer exits while its identity is being captured."""
    if pid is None:
        return None
    try:
        return capture_process_identity(pid)
    except ProcessIdentityError:
        _LOGGER.warning(
            "Could not retain authenticated owner identity | owner_pid=%s",
            pid,
            exc_info=True,
        )
        return None
