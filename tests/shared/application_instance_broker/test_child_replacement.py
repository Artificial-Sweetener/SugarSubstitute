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

"""Qualify native child-channel replacement against delayed presentation receipts."""

from __future__ import annotations

from pathlib import Path
import threading

import pytest

from sugarsubstitute_shared import (
    application_instance_broker,
    application_invocation_router,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInvocation,
    RoutedApplicationInvocation,
    receive_instance_message,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)


def test_retired_child_receipt_cannot_discard_replacement_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep replacement work authoritative when an outgoing receipt arrives late."""
    monkeypatch.setattr(
        application_instance_broker, "_SUPERVISOR_RECEIPT_DEADLINE_SECONDS", 1.0
    )
    original_receive = receive_instance_message
    receipt_received = threading.Event()
    release_receipt = threading.Event()
    receipt_processed = threading.Event()
    outgoing_connection: ApplicationInstanceConnection | None = None

    def receive(
        connection: ApplicationInstanceConnection,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """Delay a decoded native receipt across registration of its replacement."""
        nonlocal outgoing_connection
        if connection is outgoing_connection:
            receipt_processed.set()
        message = original_receive(connection, timeout_seconds=timeout_seconds)
        if message.get("surface") == "retired-window":
            outgoing_connection = connection
            receipt_received.set()
            assert release_receipt.wait(5.0)
        return message

    monkeypatch.setattr(
        application_invocation_router, "receive_instance_message", receive
    )
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(("primary",))
    )
    assert broker is not None
    first = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert first is not None
    replacement: ApplicationSupervisorClient | None = None
    result: list[BaseException] = []

    def reject(request: RoutedApplicationInvocation) -> None:
        """Send a real receipt from the child that is about to be replaced."""
        first.complete_invocation(
            request.request_id, outcome="unavailable", surface="retired-window"
        )

    def forward() -> None:
        """Record the ordinary secondary launch result."""
        try:
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path,
                    invocation=ApplicationInvocation.capture(("secondary",)),
                )
                is None
            )
        except BaseException as error:
            result.append(error)

    first.bind_invocation_handler(reject)
    thread = threading.Thread(target=forward)
    thread.start()
    try:
        assert receipt_received.wait(2.0)
        replacement = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert replacement is not None
        delivered = threading.Event()
        requests: list[RoutedApplicationInvocation] = []

        def retain(request: RoutedApplicationInvocation) -> None:
            """Observe delivery before publishing replacement presentation."""
            requests.append(request)
            delivered.set()

        replacement.bind_invocation_handler(retain)
        assert delivered.wait(2.0)
        release_receipt.set()
        assert receipt_processed.wait(2.0)
        assert len(requests) == 1
        replacement.complete_invocation(
            requests[0].request_id, outcome="presented", surface="replacement-window"
        )
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert result == []
    finally:
        release_receipt.set()
        first.close()
        if replacement is not None:
            replacement.close()
        broker.close()
        thread.join(timeout=2.0)


def test_retired_child_send_failure_cannot_discard_replacement_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep replacement routing intact when a previously admitted send fails."""
    from collections.abc import Mapping

    from sugarsubstitute_shared.application_invocation_router import (
        ApplicationInvocationRouter,
    )
    from sugarsubstitute_shared.application_instance_protocol import (
        send_instance_message,
    )

    monkeypatch.setattr(
        application_instance_broker, "_SUPERVISOR_RECEIPT_DEADLINE_SECONDS", 1.0
    )
    send_entered = threading.Event()
    release_send = threading.Event()
    dispatch_finished = threading.Event()
    old_connection: ApplicationInstanceConnection | None = None
    original_route = ApplicationInvocationRouter.route_invocation

    def send(
        connection: ApplicationInstanceConnection, message: Mapping[str, object]
    ) -> None:
        """Hold the first invocation at its native write boundary until replacement."""
        nonlocal old_connection
        if message.get("kind") == "invoke" and old_connection is None:
            old_connection = connection
            send_entered.set()
            assert release_send.wait(5.0)
        send_instance_message(connection, message)

    def route(
        router: ApplicationInvocationRouter,
        invocation: RoutedApplicationInvocation,
        *,
        waiter: ApplicationInstanceConnection,
    ) -> bool:
        """Observe public dispatch completion without changing routing behavior."""
        try:
            return original_route(router, invocation, waiter=waiter)
        finally:
            dispatch_finished.set()

    monkeypatch.setattr(application_invocation_router, "send_instance_message", send)
    monkeypatch.setattr(ApplicationInvocationRouter, "route_invocation", route)
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(("primary",))
    )
    assert broker is not None
    first = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert first is not None
    replacement: ApplicationSupervisorClient | None = None
    result: list[BaseException] = []

    def forward() -> None:
        """Capture an ordinary secondary result through the native broker."""
        try:
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path,
                    invocation=ApplicationInvocation.capture(("secondary",)),
                )
                is None
            )
        except BaseException as error:
            result.append(error)

    thread = threading.Thread(target=forward)
    thread.start()
    try:
        assert send_entered.wait(2.0)
        replacement = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert replacement is not None
        delivered = threading.Event()
        requests: list[RoutedApplicationInvocation] = []

        def retain(request: RoutedApplicationInvocation) -> None:
            """Hold presentation until the old native write has settled."""
            requests.append(request)
            delivered.set()

        replacement.bind_invocation_handler(retain)
        release_send.set()
        assert dispatch_finished.wait(2.0)
        assert delivered.wait(2.0)
        assert len(requests) == 1
        replacement.complete_invocation(
            requests[0].request_id, outcome="presented", surface="replacement-window"
        )
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert result == []
    finally:
        release_send.set()
        first.close()
        if replacement is not None:
            replacement.close()
        broker.close()
        thread.join(timeout=2.0)
