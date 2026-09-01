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

"""Verify macOS native message-port invocation routing without AppKit."""

from typing import cast

from sugarsubstitute_shared.application_instance_macos import MacOSMessagePortClaim
from sugarsubstitute_shared.application_instance_macos_core_foundation import (
    CoreFoundationMessagePortApi,
)
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation


class _DataApi:
    """Provide deterministic Core Foundation data ownership for routing tests."""

    def __init__(self, payload: bytes) -> None:
        """Retain one incoming payload and allocate response identifiers."""

        self.values = {1: payload}
        self.next_identifier = 2

    def read_data(self, identifier: int) -> bytes:
        """Return bytes owned by one fake Core Foundation data object."""

        return self.values[identifier]

    def create_data(self, payload: bytes) -> int:
        """Retain response bytes and return their fake object identifier."""

        identifier = self.next_identifier
        self.next_identifier += 1
        self.values[identifier] = payload
        return identifier


def test_native_message_queues_until_broker_handler_is_bound() -> None:
    """Acknowledge and deliver a launch that arrives during broker startup."""

    api = _DataApi(
        b'{"kind":"invoke","arguments":["Substitute","project.cubepak"],'
        b'"working_directory":"/workspace"}'
    )
    claim = MacOSMessagePortClaim(
        port=10,
        core_foundation=cast(CoreFoundationMessagePortApi, api),
        callback=object(),
    )

    response = claim.receive_message(1)
    received: list[ApplicationInvocation] = []
    claim.bind_invocation_handler(received.append)

    assert api.values[response] == b"accepted"
    assert received == [
        ApplicationInvocation(
            arguments=("Substitute", "project.cubepak"),
            working_directory="/workspace",
        )
    ]


def test_native_message_rejects_malformed_invocation() -> None:
    """Reject untrusted native payloads before they reach the broker."""

    api = _DataApi(b'{"kind":"invoke","arguments":"not-a-list"}')
    claim = MacOSMessagePortClaim(
        port=10,
        core_foundation=cast(CoreFoundationMessagePortApi, api),
        callback=object(),
    )

    response = claim.receive_message(1)

    assert api.values[response] == b"rejected"
