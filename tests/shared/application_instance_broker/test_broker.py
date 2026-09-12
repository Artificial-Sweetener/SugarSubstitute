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

import pytest

from sugarsubstitute_shared import application_instance_broker
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInvocation,
    RoutedApplicationInvocation,
)
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

    def receive(request: RoutedApplicationInvocation) -> None:
        """Capture the invocation delivered through the retained child channel."""

        received.append(request.invocation)
        client.complete_invocation(
            request.request_id,
            outcome="presented",
            surface="test-window",
        )
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
    forward_finished = threading.Event()

    def forward() -> None:
        """Forward the launch while the primary application is still starting."""

        assert (
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=queued,
            )
            is None
        )
        forward_finished.set()

    forward_thread = threading.Thread(target=forward)
    forward_thread.start()
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    received: list[ApplicationInvocation] = []
    delivered = threading.Event()

    def receive(request: RoutedApplicationInvocation) -> None:
        """Capture the one launch retained by the supervisor."""

        received.append(request.invocation)
        client.complete_invocation(
            request.request_id,
            outcome="presented",
            surface="test-window",
        )
        delivered.set()

    try:
        client.bind_invocation_handler(receive)
        assert delivered.wait(2.0)
        assert forward_finished.wait(2.0)
        assert received == [queued]
    finally:
        client.close()
        broker.close()
        forward_thread.join(timeout=2.0)


def test_secondary_remains_pending_until_the_application_presents_a_surface(
    tmp_path: Path,
) -> None:
    """Define launch acceptance as presentation rather than IPC delivery."""

    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    routed: list[RoutedApplicationInvocation] = []
    delivered = threading.Event()
    forward_finished = threading.Event()

    def receive(request: RoutedApplicationInvocation) -> None:
        """Retain the request without claiming a presentation yet."""

        routed.append(request)
        delivered.set()

    client.bind_invocation_handler(receive)

    def forward() -> None:
        """Attempt the secondary launch on a thread until presentation occurs."""

        assert (
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=ApplicationInvocation.capture(
                    ["Substitute", "delayed.sugar"]
                ),
            )
            is None
        )
        forward_finished.set()

    forward_thread = threading.Thread(target=forward)
    forward_thread.start()
    try:
        assert delivered.wait(2.0)
        assert not forward_finished.wait(0.1)
        request = routed.pop()
        client.complete_invocation(
            request.request_id,
            outcome="presented",
            surface="test-window",
        )
        assert forward_finished.wait(2.0)
    finally:
        client.close()
        broker.close()
        forward_thread.join(timeout=2.0)


def test_startup_surface_acknowledges_launch_without_losing_queued_invocation(
    tmp_path: Path,
) -> None:
    """Present the splash immediately and still deliver work to the future child."""

    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    presented: list[ApplicationInvocation] = []

    def present_startup(invocation: ApplicationInvocation) -> str:
        """Record the invocation and identify the visible startup surface."""

        presented.append(invocation)
        return "startup-splash"

    broker.bind_startup_presenter(present_startup)
    duplicate = ApplicationInvocation.capture(["Substitute", "queued.sugar"])

    assert (
        ApplicationInstanceBroker.elect(
            install_root=tmp_path,
            invocation=duplicate,
        )
        is None
    )
    assert presented == [duplicate]

    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    delivered: list[ApplicationInvocation] = []
    complete = threading.Event()

    def receive(request: RoutedApplicationInvocation) -> None:
        """Prove the early acknowledgement did not consume routed work."""

        delivered.append(request.invocation)
        client.complete_invocation(
            request.request_id,
            outcome="presented",
            surface="main-window",
        )
        complete.set()

    try:
        client.bind_invocation_handler(receive)
        assert complete.wait(2.0)
        assert delivered == [duplicate]
    finally:
        client.close()
        broker.close()


def test_presentation_deadline_releases_launcher_without_discarding_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Bound an unusable owner while retaining invocation delivery for recovery."""

    monkeypatch.setattr(
        application_instance_broker,
        "_SUPERVISOR_RECEIPT_DEADLINE_SECONDS",
        0.05,
    )
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    duplicate = ApplicationInvocation.capture(["Substitute", "retained.sugar"])

    with pytest.raises(ApplicationInstanceBrokerError) as captured:
        ApplicationInstanceBroker.elect(
            install_root=tmp_path,
            invocation=duplicate,
        )

    assert captured.value.owner_process_id is not None
    assert captured.value.endpoint is not None

    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    delivered: list[ApplicationInvocation] = []
    completed = threading.Event()

    def receive(request: RoutedApplicationInvocation) -> None:
        """Complete work retained after its original launcher was released."""

        delivered.append(request.invocation)
        client.complete_invocation(
            request.request_id,
            outcome="presented",
            surface="main-window",
        )
        completed.set()

    try:
        client.bind_invocation_handler(receive)
        assert completed.wait(2.0)
        assert delivered == [duplicate]
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
