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

"""Reserve every supported launch address before admitting one application owner."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import sys
from typing import Protocol

from sugarsubstitute_shared.application_instance_forwarding import (
    forward_application_invocation,
)
from sugarsubstitute_shared.application_instance_identity import instance_identity
from sugarsubstitute_shared.application_instance_legacy_identity import (
    released_instance_identity,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
)
from sugarsubstitute_shared.application_instance_transport import (
    ApplicationInstanceListener,
    bind_instance_listener,
    endpoint_is_already_owned,
    instance_endpoint,
)

_LOGGER = logging.getLogger(__name__)


class NativeInstanceClaim(Protocol):
    """Retain the platform's auxiliary election resource."""

    def close(self) -> None:
        """Release native authority idempotently."""


@dataclass(slots=True)
class ApplicationInstanceReservation:
    """Own all public addresses as one indivisible application reservation."""

    endpoint: ApplicationInstanceEndpoint
    listeners: tuple[ApplicationInstanceListener, ...]
    platform_claim: NativeInstanceClaim | None = None
    _closed: bool = field(default=False, init=False)

    def close(self) -> None:
        """Release partial or complete reservations even when an endpoint has failed."""
        if self._closed:
            return
        self._closed = True
        try:
            for listener in self.listeners:
                try:
                    listener.close()
                except OSError:
                    _LOGGER.warning(
                        "Application election endpoint close failed", exc_info=True
                    )
        finally:
            if self.platform_claim is not None:
                self.platform_claim.close()


def application_instance_endpoints(
    install_root: Path,
) -> tuple[ApplicationInstanceEndpoint, ...]:
    """Return canonical authority followed by supported public compatibility addresses."""
    return tuple(
        dict.fromkeys(
            (
                instance_endpoint(instance_identity(install_root)),
                instance_endpoint(released_instance_identity(install_root)),
            )
        )
    )


def reserve_application_instance(
    install_root: Path, invocation: ApplicationInvocation
) -> ApplicationInstanceReservation | None:
    """Reserve all addresses or route to their existing owner without retaining any."""
    identity = instance_identity(install_root)
    endpoints = application_instance_endpoints(install_root)
    secondary, platform_claim = _claim_platform_owner(identity)
    if secondary:
        forward_application_invocation(endpoints[0], invocation)
        return None
    listeners: list[ApplicationInstanceListener] = []
    try:
        for endpoint in endpoints:
            try:
                listeners.append(bind_instance_listener(endpoint))
            except OSError as error:
                if not endpoint_is_already_owned(error):
                    raise
                ApplicationInstanceReservation(
                    endpoints[0], tuple(listeners), platform_claim
                ).close()
                listeners.clear()
                platform_claim = None
                forward_application_invocation(endpoint, invocation)
                return None
        return ApplicationInstanceReservation(
            endpoints[0], tuple(listeners), platform_claim
        )
    except BaseException:
        ApplicationInstanceReservation(
            endpoints[0], tuple(listeners), platform_claim
        ).close()
        raise


def _claim_platform_owner(identity: str) -> tuple[bool, NativeInstanceClaim | None]:
    """Preserve native desktop election while transports enforce address exclusion."""
    if sys.platform.startswith("linux"):
        from sugarsubstitute_shared.application_instance_linux import (
            LinuxSessionBusElection,
            acquire_linux_session_bus,
        )

        result = acquire_linux_session_bus(identity)
        return result.election is LinuxSessionBusElection.SECONDARY, result.claim
    if sys.platform == "darwin":
        from sugarsubstitute_shared.application_instance_macos import (
            MacOSMessagePortElection,
            acquire_macos_message_port,
        )

        mac_result = acquire_macos_message_port(identity)
        return (
            mac_result.election is MacOSMessagePortElection.SECONDARY,
            mac_result.claim,
        )
    return False, None
