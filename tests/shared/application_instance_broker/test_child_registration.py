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

"""Keep queued launches owned through an interrupted native child handshake."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import threading

import pytest

from sugarsubstitute_shared import application_invocation_router
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    RoutedApplicationInvocation,
    receive_instance_message,
    send_instance_message,
)
from sugarsubstitute_shared.application_instance_transport import (
    connect_instance_endpoint,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)


def test_failed_child_handshake_retains_queued_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliver pending user work after an acknowledged-channel write fails."""
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(("primary",))
    )
    assert broker is not None
    queued = threading.Event()
    broker.bind_startup_presenter(lambda _invocation: queued.set())
    result: list[BaseException] = []

    def forward() -> None:
        """Retain the real waiting launch until a usable replacement presents it."""
        try:
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path,
                    invocation=ApplicationInvocation.capture(
                        ("pending-document.sugar",)
                    ),
                )
                is None
            )
        except BaseException as error:
            result.append(error)

    fail_handshake = True

    def send(
        connection: ApplicationInstanceConnection, message: Mapping[str, object]
    ) -> None:
        """Fail exactly the native registration acknowledgement write."""
        nonlocal fail_handshake
        if fail_handshake and message.get("status") == "accepted":
            fail_handshake = False
            connection.close()
            raise OSError("Synthetic child handshake disconnect")
        send_instance_message(connection, message)

    monkeypatch.setattr(application_invocation_router, "send_instance_message", send)
    thread = threading.Thread(target=forward)
    thread.start()
    failed: ApplicationInstanceConnection | None = None
    replacement: ApplicationSupervisorClient | None = None
    try:
        assert queued.wait(2.0)
        environment = broker.child_environment({})
        failed = connect_instance_endpoint(
            ApplicationInstanceEndpoint.from_json(environment[BROKER_ENDPOINT_ENV])
        )
        send_instance_message(
            failed, {"kind": "register-child", "token": environment[BROKER_TOKEN_ENV]}
        )
        with pytest.raises(OSError):
            receive_instance_message(failed, timeout_seconds=2.0)
        replacement = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert replacement is not None
        presented = threading.Event()
        received: list[RoutedApplicationInvocation] = []

        def present(request: RoutedApplicationInvocation) -> None:
            """Prove the replacement receives and presents the original invocation."""
            received.append(request)
            replacement.complete_invocation(
                request.request_id, outcome="presented", surface="replacement-window"
            )
            presented.set()

        replacement.bind_invocation_handler(present)
        assert presented.wait(2.0)
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert result == []
        assert [request.invocation.arguments for request in received] == [
            ("pending-document.sugar",)
        ]
    finally:
        if failed is not None:
            failed.close()
        if replacement is not None:
            replacement.close()
        broker.close()
        thread.join(timeout=2.0)


def test_superseded_registration_cannot_deliver_its_snapshot_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep one delivery owner when a second child replaces a paused handshake."""
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(("primary",))
    )
    assert broker is not None
    queued = threading.Event()
    broker.bind_startup_presenter(lambda _invocation: queued.set())
    acknowledgement_sent = threading.Event()
    release_handshake = threading.Event()
    first_flush_finished = threading.Event()
    first_connection: ApplicationInstanceConnection | None = None

    def send(
        connection: ApplicationInstanceConnection, message: Mapping[str, object]
    ) -> None:
        """Pause after the first acknowledgement reaches its native client."""
        nonlocal first_connection
        send_instance_message(connection, message)
        if first_connection is None and message.get("status") == "accepted":
            first_connection = connection
            acknowledgement_sent.set()
            assert release_handshake.wait(5.0)

    def receive(
        connection: ApplicationInstanceConnection,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """Observe the outgoing registration finishing its queued dispatch loop."""
        if connection is first_connection:
            first_flush_finished.set()
        return receive_instance_message(connection, timeout_seconds=timeout_seconds)

    monkeypatch.setattr(application_invocation_router, "send_instance_message", send)
    monkeypatch.setattr(
        application_invocation_router, "receive_instance_message", receive
    )
    errors: list[BaseException] = []

    def forward() -> None:
        """Send the initial queued document through ordinary election."""
        try:
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path,
                    invocation=ApplicationInvocation.capture(("document",)),
                )
                is None
            )
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=forward)
    thread.start()
    first: ApplicationSupervisorClient | None = None
    replacement: ApplicationSupervisorClient | None = None
    try:
        assert queued.wait(2.0)
        first = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert first is not None
        assert acknowledgement_sent.wait(2.0)
        replacement = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert replacement is not None
        received: list[tuple[str, ...]] = []

        def present(request: RoutedApplicationInvocation) -> None:
            """Acknowledge each receipt while preserving delivery order for assertion."""
            received.append(request.invocation.arguments)
            replacement.complete_invocation(
                request.request_id, outcome="presented", surface="replacement-window"
            )

        replacement.bind_invocation_handler(present)
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert errors == []
        release_handshake.set()
        assert first_flush_finished.wait(2.0)
        assert (
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=ApplicationInvocation.capture(("barrier",)),
            )
            is None
        )
        assert received == [("document",), ("barrier",)]
    finally:
        release_handshake.set()
        if first is not None:
            first.close()
        if replacement is not None:
            replacement.close()
        broker.close()
        thread.join(timeout=2.0)
