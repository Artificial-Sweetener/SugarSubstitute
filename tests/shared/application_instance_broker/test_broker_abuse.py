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

"""Abuse instance routing at lifecycle boundaries that previously stranded users."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from sugarsubstitute_shared import application_instance_broker
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
    ApplicationInstanceBrokerError,
    ApplicationInstanceEndpoint,
    ApplicationInvocation,
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


def test_child_crash_before_receipt_reaches_replacement_without_relaunch(
    tmp_path: Path,
) -> None:
    """Retain in-flight work across a child crash until another child presents it."""

    broker = _elect_primary(tmp_path)
    environment = broker.child_environment({})
    first_client = ApplicationSupervisorClient.connect_from_environment(environment)
    assert first_client is not None
    first_delivery = threading.Event()
    first_requests: list[RoutedApplicationInvocation] = []

    def record_first_delivery(request: RoutedApplicationInvocation) -> None:
        """Record delivery without acknowledging presentation."""

        first_requests.append(request)
        first_delivery.set()

    first_client.bind_invocation_handler(record_first_delivery)
    forward_result, forward_thread = _start_forward(tmp_path, "survive-crash.sugar")
    replacement_client: ApplicationSupervisorClient | None = None
    try:
        assert first_delivery.wait(2.0)
        first_client.close()
        replacement_client = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert replacement_client is not None
        replacement_delivery = threading.Event()
        replacement_requests: list[RoutedApplicationInvocation] = []

        def present(request: RoutedApplicationInvocation) -> None:
            """Present the exact retained request from the replacement child."""

            replacement_requests.append(request)
            replacement_client.complete_invocation(
                request.request_id,
                outcome="presented",
                surface="replacement-window",
            )
            replacement_delivery.set()

        replacement_client.bind_invocation_handler(present)
        assert replacement_delivery.wait(2.0)
        forward_thread.join(timeout=2.0)
        assert not forward_thread.is_alive()
        assert forward_result == []
        assert replacement_requests == first_requests
    finally:
        first_client.close()
        if replacement_client is not None:
            replacement_client.close()
        broker.close()
        forward_thread.join(timeout=2.0)


def test_failed_presentation_is_retained_for_a_replacement_child(
    tmp_path: Path,
) -> None:
    """Release the caller visibly while preserving work that no surface showed."""

    broker = _elect_primary(tmp_path)
    first_client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert first_client is not None
    rejected = threading.Event()

    def reject(request: RoutedApplicationInvocation) -> None:
        """Report that the current child could not show a surface."""

        first_client.complete_invocation(
            request.request_id,
            outcome="unavailable",
            surface="window-never-painted",
        )
        rejected.set()

    first_client.bind_invocation_handler(reject)
    forward_result, forward_thread = _start_forward(tmp_path, "retry-later.sugar")
    replacement_client: ApplicationSupervisorClient | None = None
    try:
        assert rejected.wait(2.0)
        forward_thread.join(timeout=2.0)
        assert len(forward_result) == 1
        assert isinstance(forward_result[0], ApplicationInstanceBrokerError)
        first_client.close()
        replacement_client = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert replacement_client is not None
        delivered = threading.Event()

        def present(request: RoutedApplicationInvocation) -> None:
            """Finish the retained work on the next usable child."""

            replacement_client.complete_invocation(
                request.request_id,
                outcome="presented",
                surface="replacement-window",
            )
            delivered.set()

        replacement_client.bind_invocation_handler(present)
        assert delivered.wait(2.0)
    finally:
        first_client.close()
        if replacement_client is not None:
            replacement_client.close()
        broker.close()
        forward_thread.join(timeout=2.0)


def test_startup_acknowledgements_cannot_bypass_total_work_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Bound all unfinished work even after splash acknowledgements release callers."""

    monkeypatch.setattr(application_instance_broker, "_MAXIMUM_PENDING_INVOCATIONS", 3)
    broker = _elect_primary(tmp_path)
    broker.bind_startup_presenter(lambda _invocation: "startup-splash")
    try:
        for index in range(3):
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path,
                    invocation=ApplicationInvocation.capture(
                        ["Substitute", f"queued-{index}.sugar"]
                    ),
                )
                is None
            )
        with pytest.raises(ApplicationInstanceBrokerError):
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=ApplicationInvocation.capture(
                    ["Substitute", "over-capacity.sugar"]
                ),
            )
    finally:
        broker.close()


def test_supervisor_shutdown_releases_waiter_and_endpoint_immediately(
    tmp_path: Path,
) -> None:
    """A shutdown race must neither hang the launcher nor leave stale ownership."""

    broker = _elect_primary(tmp_path)
    presentation_attempted = threading.Event()

    def reject_startup_presentation(_invocation: ApplicationInvocation) -> None:
        """Record a presentation attempt while withholding acknowledgement."""

        presentation_attempted.set()

    broker.bind_startup_presenter(reject_startup_presentation)
    forward_result, forward_thread = _start_forward(tmp_path, "during-close.sugar")
    assert presentation_attempted.wait(2.0)
    broker.close()
    forward_thread.join(timeout=2.0)
    assert not forward_thread.is_alive()
    assert len(forward_result) == 1
    assert isinstance(forward_result[0], ApplicationInstanceBrokerError)

    replacement = _elect_primary(tmp_path)
    replacement.close()


def test_application_handler_failure_does_not_kill_the_control_channel(
    tmp_path: Path,
) -> None:
    """One bad invocation must fail visibly while later launches still work."""

    broker = _elect_primary(tmp_path)
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    failed_handler_called = threading.Event()

    def fail(_request: RoutedApplicationInvocation) -> None:
        """Simulate an application-owned dispatch defect."""

        failed_handler_called.set()
        raise RuntimeError("synthetic handler failure")

    client.bind_invocation_handler(fail)
    first_result, first_thread = _start_forward(tmp_path, "handler-fails.sugar")
    try:
        assert failed_handler_called.wait(2.0)
        first_thread.join(timeout=2.0)
        assert len(first_result) == 1
        assert isinstance(first_result[0], ApplicationInstanceBrokerError)

        presented = threading.Event()

        def present(request: RoutedApplicationInvocation) -> None:
            """Prove the reader remains available after the failed handler."""

            client.complete_invocation(
                request.request_id,
                outcome="presented",
                surface="main-window",
            )
            presented.set()

        client.bind_invocation_handler(present)
        second_result, second_thread = _start_forward(tmp_path, "later.sugar")
        assert presented.wait(2.0)
        second_thread.join(timeout=2.0)
        assert second_result == []
    finally:
        client.close()
        broker.close()
        first_thread.join(timeout=2.0)


def test_stalled_handshake_cannot_block_later_launches(tmp_path: Path) -> None:
    """One client that sends nothing must not monopolize the native listener."""

    broker = _elect_primary(tmp_path)
    environment = broker.child_environment({})
    endpoint = ApplicationInstanceEndpoint.from_json(environment[BROKER_ENDPOINT_ENV])
    stalled = connect_instance_endpoint(endpoint)
    broker.bind_startup_presenter(lambda _invocation: "startup-window")
    result, forwarder = _start_forward(tmp_path, "behind-stalled-client.sugar")
    try:
        forwarder.join(timeout=2.0)
        assert not forwarder.is_alive()
        assert result == []
    finally:
        stalled.close()
        broker.close()
        forwarder.join(timeout=2.0)


def test_forged_child_receipt_requeues_work_for_a_real_child(tmp_path: Path) -> None:
    """A bad child receipt must lose its channel rather than lose user work."""

    broker = _elect_primary(tmp_path)
    environment = broker.child_environment({})
    endpoint = ApplicationInstanceEndpoint.from_json(environment[BROKER_ENDPOINT_ENV])
    forged_child = connect_instance_endpoint(endpoint)
    send_instance_message(
        forged_child,
        {"kind": "register-child", "token": environment[BROKER_TOKEN_ENV]},
    )
    assert receive_instance_message(forged_child)["status"] == "accepted"
    result, forwarder = _start_forward(tmp_path, "survive-forged-receipt.sugar")
    routed = receive_instance_message(forged_child, timeout_seconds=2.0)
    request_id = routed["request_id"]
    assert isinstance(request_id, str)
    send_instance_message(
        forged_child,
        {
            "kind": "invocation-receipt",
            "token": "forged-token",
            "request_id": request_id,
            "outcome": "presented",
            "surface": "fake-window",
        },
    )
    replacement = ApplicationSupervisorClient.connect_from_environment(environment)
    assert replacement is not None
    presented = threading.Event()

    def present(request: RoutedApplicationInvocation) -> None:
        """Prove a correctly authenticated replacement receives the same request."""

        replacement.complete_invocation(
            request.request_id,
            outcome="presented",
            surface="real-window",
        )
        presented.set()

    replacement.bind_invocation_handler(present)
    try:
        assert presented.wait(2.0)
        forwarder.join(timeout=2.0)
        assert not forwarder.is_alive()
        assert result == []
    finally:
        forged_child.close()
        replacement.close()
        broker.close()
        forwarder.join(timeout=2.0)


def _elect_primary(install_root: Path) -> ApplicationInstanceBroker:
    """Elect one broker or fail the test with a concrete type assertion."""

    broker = ApplicationInstanceBroker.elect(
        install_root=install_root,
        invocation=ApplicationInvocation.capture(["Substitute"]),
    )
    assert broker is not None
    return broker


def _start_forward(
    install_root: Path,
    document_name: str,
) -> tuple[list[BaseException], threading.Thread]:
    """Start one secondary and capture only its terminal exception."""

    result: list[BaseException] = []

    def forward() -> None:
        """Forward one request and retain any visible failure for assertion."""

        try:
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=install_root,
                    invocation=ApplicationInvocation.capture(
                        ["Substitute", document_name]
                    ),
                )
                is None
            )
        except BaseException as error:
            result.append(error)

    thread = threading.Thread(target=forward)
    thread.start()
    return result, thread
