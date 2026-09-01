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

"""Exercise the real fileless broker through local operating-system IPC."""

import threading
from pathlib import Path

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)


def test_secondary_invocation_reaches_the_registered_application(
    tmp_path: Path,
) -> None:
    """Route one losing launch to the primary supervisor's child exactly once."""

    first = ApplicationInvocation.capture(["Substitute", "--locale=en"])
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=first,
    )
    assert broker is not None
    environment = broker.child_environment({})
    client = ApplicationSupervisorClient.connect_from_environment(environment)
    assert client is not None
    received: list[ApplicationInvocation] = []
    delivered = threading.Event()

    def receive(invocation: ApplicationInvocation) -> None:
        """Capture the invocation delivered through the retained child channel."""

        received.append(invocation)
        delivered.set()

    client.bind_invocation_handler(receive)
    duplicate = ApplicationInvocation.capture(
        ["Substitute", "example.sugar"],
        working_directory=tmp_path / "incoming",
    )
    try:
        assert (
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=duplicate,
            )
            is None
        )
        assert delivered.wait(2.0)
        assert received == [duplicate]
        assert environment == {}
    finally:
        client.close()
        broker.close()


def test_child_restart_request_is_owned_by_the_existing_supervisor(
    tmp_path: Path,
) -> None:
    """Keep restart authority in the elected supervisor rather than a new launcher."""

    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    try:
        assert client.request_restart()
        assert broker.consume_restart_request()
        assert not broker.consume_restart_request()
    finally:
        client.close()
        broker.close()


def test_startup_invocation_is_queued_until_the_child_registers(
    tmp_path: Path,
) -> None:
    """Deliver a launch that loses election during primary child startup once."""

    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    queued = ApplicationInvocation.capture(
        ["Substitute", "queued.sugar"],
        working_directory=tmp_path,
    )
    assert (
        ApplicationInstanceBroker.elect(
            install_root=tmp_path,
            invocation=queued,
        )
        is None
    )
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    received: list[ApplicationInvocation] = []
    delivered = threading.Event()

    def receive(invocation: ApplicationInvocation) -> None:
        """Capture the one launch retained by the supervisor."""

        received.append(invocation)
        delivered.set()

    try:
        client.bind_invocation_handler(receive)
        assert delivered.wait(2.0)
        assert received == [queued]
    finally:
        client.close()
        broker.close()


def test_child_observes_authoritative_supervisor_loss(tmp_path: Path) -> None:
    """Notify the application before a replacement supervisor can own the endpoint."""

    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    disconnected = threading.Event()
    client.bind_disconnect_handler(disconnected.set)

    try:
        broker.close()
        assert disconnected.wait(2.0)
    finally:
        client.close()


def test_native_endpoint_is_immediately_recoverable_after_owner_exit(
    tmp_path: Path,
) -> None:
    """Elect a replacement without stale files, PID probes, or cleanup delay."""

    invocation = ApplicationInvocation.capture(["Substitute"])
    original = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=invocation,
    )
    assert original is not None
    original.close()

    replacement = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=invocation,
    )
    assert replacement is not None
    replacement.close()
