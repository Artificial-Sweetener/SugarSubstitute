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

"""Qualify selected-folder admission through the existing supervisor channel."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from threading import Barrier

import pytest

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)


def test_selected_folder_routes_to_the_existing_setup_owner(tmp_path: Path) -> None:
    """Claim the chosen folder before mutation without creating a second owner."""
    invocation = ApplicationInvocation.capture(["setup"])
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path / "bootstrap", invocation=invocation
    )
    assert broker is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    received: list[ApplicationInvocation] = []

    def present_setup(request: ApplicationInvocation) -> str:
        """Record the visible setup receipt from the same supervisor."""
        received.append(request)
        return "setup"

    broker.bind_startup_presenter(present_setup)
    target = tmp_path / "selected"
    try:
        assert client.claim_installation(target)
        assert client.claim_installation(target)
        client.close()
        assert (
            ApplicationInstanceBroker.elect(install_root=target, invocation=invocation)
            is None
        )
        assert received == [invocation]
        assert not target.exists()
    finally:
        client.close()
        broker.close()
    replacement = ApplicationInstanceBroker.elect(
        install_root=target, invocation=invocation
    )
    assert replacement is not None
    replacement.close()


def test_existing_selected_folder_owner_receives_install_request(
    tmp_path: Path,
) -> None:
    """Do not admit installation while an existing app owns the chosen folder."""
    invocation = ApplicationInvocation.capture(["setup"])
    target = tmp_path / "selected"
    existing = ApplicationInstanceBroker.elect(
        install_root=target, invocation=invocation
    )
    bootstrap = ApplicationInstanceBroker.elect(
        install_root=tmp_path / "bootstrap", invocation=invocation
    )
    assert existing is not None and bootstrap is not None
    received: list[ApplicationInvocation] = []

    def present_existing(request: ApplicationInvocation) -> str:
        """Record presentation without granting a second installation owner."""
        received.append(request)
        return "main-shell"

    existing.bind_startup_presenter(present_existing)
    client = ApplicationSupervisorClient.connect_from_environment(
        bootstrap.child_environment({})
    )
    assert client is not None
    try:
        assert not client.claim_installation(target)
        assert len(received) == 1
        assert not target.exists()
    finally:
        client.close()
        bootstrap.close()
        existing.close()


def test_claiming_the_initial_folder_is_idempotent(tmp_path: Path) -> None:
    """Never forward admission to the same waiting installer thread."""
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["setup"])
    )
    assert broker is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    try:
        assert client.claim_installation(tmp_path)
    finally:
        client.close()
        broker.close()


@pytest.mark.parametrize("contenders", [2, 4])
def test_concurrent_setup_claims_admit_exactly_one_owner(
    tmp_path: Path, contenders: int
) -> None:
    """Serialize independent setup owners choosing one folder at the same time."""
    target = tmp_path / "selected"
    invocation = ApplicationInvocation.capture(["setup"])
    presented: list[int] = []
    brokers: list[ApplicationInstanceBroker] = []
    clients: list[ApplicationSupervisorClient] = []
    barrier = Barrier(contenders)

    def presenter(index: int) -> Callable[[ApplicationInvocation], str]:
        """Bind each receipt to the supervisor that actually presented it."""

        def present(_invocation: ApplicationInvocation) -> str:
            """Record successful delivery through the native listener."""
            presented.append(index)
            return "setup"

        return present

    def claim(index: int) -> bool:
        """Release contenders together without relying on scheduling sleeps."""
        barrier.wait(timeout=10)
        return clients[index].claim_installation(target)

    with ExitStack() as cleanup:
        for index in range(contenders):
            broker = ApplicationInstanceBroker.elect(
                install_root=tmp_path / f"bootstrap-{index}", invocation=invocation
            )
            assert broker is not None
            cleanup.callback(broker.close)
            broker.bind_startup_presenter(presenter(index))
            brokers.append(broker)
            client = ApplicationSupervisorClient.connect_from_environment(
                broker.child_environment({})
            )
            assert client is not None
            cleanup.callback(client.close)
            clients.append(client)
        with ThreadPoolExecutor(max_workers=contenders) as pool:
            futures = [pool.submit(claim, index) for index in range(contenders)]
            admitted = [future.result(timeout=30) for future in futures]
        assert sum(admitted) == 1
        winner = admitted.index(True)
        assert presented == [winner] * (contenders - 1)
        assert not target.exists()
        for index, broker in enumerate(brokers):
            if index != winner:
                clients[index].close()
                broker.close()
        assert (
            ApplicationInstanceBroker.elect(install_root=target, invocation=invocation)
            is None
        )
        assert presented == [winner] * contenders
    replacement = ApplicationInstanceBroker.elect(
        install_root=target, invocation=invocation
    )
    assert replacement is not None
    replacement.close()


@pytest.mark.parametrize("reject", [False, True])
def test_admission_activity_does_not_replace_the_terminal_result(
    tmp_path: Path, reject: bool
) -> None:
    """Wait through real activity receipts while preserving terminal failure semantics."""
    from sugarsubstitute_shared.application_instance_election import (
        ApplicationInstanceReservation,
        reserve_application_instance,
    )
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInstanceBrokerError,
    )

    def reserve(
        root: Path, invocation: ApplicationInvocation, activity: Callable[[], None]
    ) -> ApplicationInstanceReservation | None:
        """Expose progress at the injected reservation boundary, then finish normally."""
        activity()
        activity()
        if reject:
            raise ApplicationInstanceBrokerError("Unrecoverable admission")
        return reserve_application_instance(root, invocation)

    with ExitStack() as cleanup:
        broker = ApplicationInstanceBroker.elect(
            install_root=tmp_path / "bootstrap",
            invocation=ApplicationInvocation.capture(["setup"]),
            reserve_selected=reserve,
        )
        assert broker is not None
        cleanup.callback(broker.close)
        client = ApplicationSupervisorClient.connect_from_environment(
            broker.child_environment({})
        )
        assert client is not None
        cleanup.callback(client.close)
        if reject:
            with pytest.raises(ApplicationInstanceBrokerError):
                client.claim_installation(tmp_path / "target")
        else:
            assert client.claim_installation(tmp_path / "target")
        assert not (tmp_path / "target").exists()


def test_unauthenticated_target_claim_cannot_reserve_a_folder(tmp_path: Path) -> None:
    """Only the private supervised child may change installation admission."""
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInstanceEndpoint,
        BROKER_ENDPOINT_ENV,
        receive_instance_message,
        send_instance_message,
    )
    from sugarsubstitute_shared.application_instance_transport import (
        connect_instance_endpoint,
    )

    invocation = ApplicationInvocation.capture(["setup"])
    broker = ApplicationInstanceBroker.elect(
        install_root=tmp_path / "bootstrap", invocation=invocation
    )
    assert broker is not None
    target = tmp_path / "selected"
    connection = connect_instance_endpoint(
        ApplicationInstanceEndpoint.from_json(
            broker.child_environment({})[BROKER_ENDPOINT_ENV]
        )
    )
    try:
        send_instance_message(
            connection,
            {
                "kind": "claim-installation",
                "token": "untrusted",
                "install_root": str(target),
            },
        )
        assert receive_instance_message(connection) == {"status": "rejected"}
        owner = ApplicationInstanceBroker.elect(
            install_root=target, invocation=invocation
        )
        assert owner is not None
        owner.close()
    finally:
        connection.close()
        broker.close()


def test_listener_start_failure_releases_only_the_selected_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject admission and reclaim partial listeners without losing bootstrap."""
    import threading
    from sugarsubstitute_shared.application_instance_election import (
        application_instance_endpoints,
    )
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInstanceBrokerError,
    )

    invocation = ApplicationInvocation.capture(["setup"])
    root = tmp_path / "bootstrap"
    target = tmp_path / "selected"
    broker = ApplicationInstanceBroker.elect(install_root=root, invocation=invocation)
    assert broker is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        broker.child_environment({})
    )
    assert client is not None
    original_start = threading.Thread.start
    started: list[threading.Thread] = []
    attempted = 0

    def fail_last_listener(thread: threading.Thread) -> None:
        """Fail the final native listener thread after any earlier one starts."""
        nonlocal attempted
        if thread.name == "application-instance-broker":
            attempted += 1
            if attempted == len(application_instance_endpoints(target)):
                raise RuntimeError("native listener thread unavailable")
            started.append(thread)
        original_start(thread)

    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(threading.Thread, "start", fail_last_listener)
            with pytest.raises(ApplicationInstanceBrokerError):
                client.claim_installation(target)
        assert all(not thread.is_alive() for thread in started)
        assert client.claim_installation(root)
        replacement = ApplicationInstanceBroker.elect(
            install_root=target, invocation=invocation
        )
        assert replacement is not None
        replacement.close()
    finally:
        client.close()
        broker.close()


@pytest.mark.parametrize("replacement_supervisor", [False, True])
def test_stale_setup_client_cannot_claim_after_supervisor_exit(
    tmp_path: Path, replacement_supervisor: bool
) -> None:
    """Keep admission tied to the original authenticated supervisor lifetime."""
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInstanceBrokerError,
    )

    invocation = ApplicationInvocation.capture(["setup"])
    bootstrap = tmp_path / "bootstrap"
    target = tmp_path / "selected"
    original = ApplicationInstanceBroker.elect(
        install_root=bootstrap, invocation=invocation
    )
    assert original is not None
    client = ApplicationSupervisorClient.connect_from_environment(
        original.child_environment({})
    )
    assert client is not None
    replacement = None
    target_owner = None
    try:
        client.close()
        original.close()
        if replacement_supervisor:
            replacement = ApplicationInstanceBroker.elect(
                install_root=bootstrap, invocation=invocation
            )
            assert replacement is not None
        with pytest.raises((ApplicationInstanceBrokerError, OSError)):
            client.claim_installation(target)
        assert not target.exists()
        target_owner = ApplicationInstanceBroker.elect(
            install_root=target, invocation=invocation
        )
        assert target_owner is not None
    finally:
        if target_owner is not None:
            target_owner.close()
        if replacement is not None:
            replacement.close()
        client.close()
        original.close()
