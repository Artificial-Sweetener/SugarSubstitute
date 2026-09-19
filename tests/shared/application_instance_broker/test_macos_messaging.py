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

"""Verify macOS native ownership election without AppKit."""

import pytest

from sugarsubstitute_shared import application_instance_macos
from sugarsubstitute_shared.application_instance_macos import (
    MacOSMessagePortElection,
)
from sugarsubstitute_shared.application_instance_macos_core_foundation import (
    LocalMessagePortCreation,
)


class _OwnershipApi:
    """Model deterministic Core Foundation ownership and release behavior."""

    def __init__(self, *, creation: LocalMessagePortCreation) -> None:
        """Retain one configured native election result."""

        self.creation = creation
        self.invalidated: list[int] = []
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
        """Return the configured native election result."""

        return self.creation

    def invalidate_port(self, value: int) -> None:
        """Record ownership invalidation."""

        self.invalidated.append(value)

    def release(self, value: int) -> None:
        """Record release of each retained fake object."""

        self.released.append(value)


def test_primary_ownership_is_invalidated_and_released_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release an elected native name without a callback service thread."""

    api = _OwnershipApi(creation=LocalMessagePortCreation(port=20, created=True))
    monkeypatch.setattr(
        application_instance_macos,
        "CoreFoundationMessagePortApi",
        lambda: api,
    )

    result = application_instance_macos.acquire_macos_message_port("instance")
    assert result.election is MacOSMessagePortElection.PRIMARY
    assert result.claim is not None

    result.claim.close()
    result.claim.close()

    assert api.invalidated == [20]
    assert api.released == [10, 20]


def test_existing_local_message_port_is_a_secondary_election(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat Core Foundation's returned existing port as election loss."""

    api = _OwnershipApi(creation=LocalMessagePortCreation(port=20, created=False))
    monkeypatch.setattr(
        application_instance_macos,
        "CoreFoundationMessagePortApi",
        lambda: api,
    )

    result = application_instance_macos.acquire_macos_message_port("instance")

    assert result.election is MacOSMessagePortElection.SECONDARY
    assert result.claim is None
    assert api.invalidated == []
    assert api.released == [10, 20]
