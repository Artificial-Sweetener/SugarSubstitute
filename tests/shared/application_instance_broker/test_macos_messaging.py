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

import pytest

from sugarsubstitute_shared import application_instance_macos
from sugarsubstitute_shared.application_instance_macos import (
    MacOSMessagePortClaim,
    MacOSMessagePortElection,
)
from sugarsubstitute_shared.application_instance_macos_core_foundation import (
    CoreFoundationMessagePortApi,
    LocalMessagePortCreation,
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


class _DuplicateNameApi:
    """Model Core Foundation returning an existing same-process local port."""

    def __init__(self) -> None:
        """Record released Core Foundation objects."""

        self.released: list[int] = []

    def create_name(self, _value: str) -> int:
        """Return one fake retained name."""

        return 10

    def create_local_port(
        self,
        _name: int,
        _callback: object,
        _context: object,
    ) -> LocalMessagePortCreation:
        """Return the already-owned port without claiming its name."""

        return LocalMessagePortCreation(port=20, created=False)

    def release(self, value: int) -> None:
        """Record release of each retained fake object."""

        self.released.append(value)


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


def test_existing_local_message_port_is_a_secondary_election(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat Core Foundation's returned existing port as election loss."""

    api = _DuplicateNameApi()
    monkeypatch.setattr(
        application_instance_macos,
        "CoreFoundationMessagePortApi",
        lambda: api,
    )

    result = application_instance_macos.acquire_macos_message_port("instance")

    assert result.election is MacOSMessagePortElection.SECONDARY
    assert result.claim is None
    assert api.released == [10, 20]
