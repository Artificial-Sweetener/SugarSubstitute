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

"""Keep native recovery authority independent of untrusted message identities."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sugarsubstitute_shared import application_instance_forwarding
from sugarsubstitute_shared.application_instance_owner import (
    capture_native_instance_owner,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
    NativeApplicationInstanceOwner,
)
from sugarsubstitute_shared.application_instance_transport import instance_endpoint
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_process_identity,
)


class _ReplyConnection:
    """Control the external transport's kernel identity and response independently."""

    def __init__(self, kernel_pid: int | None, reported_pid: int) -> None:
        """Keep the kernel boundary distinct from a peer's arbitrary response."""
        self._kernel_pid = kernel_pid
        self._reported_pid = reported_pid
        self.closed = False

    def peer_process_id(self) -> int | None:
        """Return only the native peer observation supplied by the test boundary."""
        return self._kernel_pid

    def send_frame(self, payload: bytes) -> None:
        """Accept the activation request without impersonating its receipt."""

    def receive_frame(
        self, maximum_size: int, *, timeout_seconds: float | None = None
    ) -> bytes:
        """Respond with a failure and an independently controlled PID claim."""
        return json.dumps(
            {"status": "unavailable", "owner_process_id": self._reported_pid}
        ).encode()

    def close(self) -> None:
        """Record release of the failed activation connection."""
        self.closed = True


def test_protocol_pid_cannot_supply_native_recovery_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain legacy identity diagnostics without promoting a message to OS proof."""
    connection = _ReplyConnection(None, os.getpid())
    endpoint = instance_endpoint("7" * 48)
    monkeypatch.setattr(
        application_instance_forwarding,
        "connect_instance_endpoint",
        lambda _endpoint: connection,
    )
    with pytest.raises(ApplicationInstanceBrokerError) as caught:
        application_instance_forwarding.forward_application_invocation(
            endpoint, ApplicationInvocation.capture(())
        )
    assert caught.value.owner_process_id == os.getpid()
    assert caught.value.native_owner is None
    assert connection.closed


def test_kernel_peer_overrides_a_different_message_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep native ownership bound to the transport even when its response lies."""
    connection = _ReplyConnection(os.getpid(), os.getpid() + 1)
    endpoint = instance_endpoint("7" * 48)
    monkeypatch.setattr(
        application_instance_forwarding,
        "connect_instance_endpoint",
        lambda _endpoint: connection,
    )
    with pytest.raises(ApplicationInstanceBrokerError) as caught:
        application_instance_forwarding.forward_application_invocation(
            endpoint, ApplicationInvocation.capture(())
        )
    failure = caught.value
    assert failure.owner_identity == capture_process_identity(os.getpid())
    if endpoint.transport == "loopback-tcp":
        assert failure.native_owner is None
    else:
        assert failure.native_owner is not None
        assert failure.native_owner.identity == failure.owner_identity
        assert failure.native_owner.endpoint == endpoint
        assert failure.native_owner.executable.is_absolute()
    assert connection.closed


def test_reused_pid_cannot_acquire_native_image_evidence() -> None:
    """Reject image lookup when the process incarnation changed after peer capture."""
    identity = capture_process_identity(os.getpid())
    changed = ProcessIdentity(identity.pid, identity.created_at + 1)
    assert capture_native_instance_owner(instance_endpoint("7" * 48), changed) is None


@pytest.mark.parametrize("mismatch", ["identity", "endpoint"])
def test_native_evidence_must_match_the_failed_request(
    tmp_path: Path, mismatch: str
) -> None:
    """Reject evidence copied from another owner or another installation endpoint."""
    endpoint = ApplicationInstanceEndpoint("windows-named-pipe", "test-owner")
    identity = ProcessIdentity(100, 1)
    native = NativeApplicationInstanceOwner(endpoint, identity, tmp_path / "setup.exe")
    with pytest.raises(ValueError, match="must match"):
        ApplicationInstanceBrokerError(
            "unavailable",
            owner_identity=ProcessIdentity(101, 1)
            if mismatch == "identity"
            else identity,
            endpoint=ApplicationInstanceEndpoint("windows-named-pipe", "other")
            if mismatch == "endpoint"
            else endpoint,
            native_owner=native,
        )
