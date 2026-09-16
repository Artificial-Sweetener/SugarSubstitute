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

"""Verify repair supervision owns the same native instance as normal startup."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.repair_session_supervisor import (
    RepairSessionSupervisor,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared.supervisor_handoff import with_supervisor_handoff
from sugarsubstitute_shared.application_instance_identity import instance_identity
from sugarsubstitute_shared.application_instance_transport import (
    bind_instance_listener,
    instance_endpoint,
    endpoint_is_already_owned,
)


@pytest.mark.parametrize("result", [0, 2, -1])
def test_repair_session_owns_instance_until_presentation_finishes(
    tmp_path: Path, result: int
) -> None:
    """Normal startup cannot become owner during repair; relaunch follows release."""
    root = tmp_path / "installation"
    staging = root / ".repair/staging/1.2.3"
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
        wait_pid=77,
        wait_process_created_at=123.5,
        relaunch=True,
    )
    events: list[str] = []

    class Presentation:
        """Stand in for the visible child while exercising real native ownership."""

        def run(
            self, candidate: PreparedRepairRequest, environment: Mapping[str, str]
        ) -> int:
            """Prove the normal native endpoint is already claimed during repair."""
            assert candidate == request
            assert events == ["waited:88", "waited:77"]
            assert environment
            with pytest.raises(OSError) as error:
                bind_instance_listener(instance_endpoint(instance_identity(root)))
            assert endpoint_is_already_owned(error.value)
            events.append("presented")
            if result == -1:
                raise RuntimeError("controlled presentation failure")
            if result == 0:
                from sugarsubstitute_shared.application_supervisor_client import (
                    ApplicationSupervisorClient,
                )

                client = ApplicationSupervisorClient.connect_from_environment(
                    dict(environment)
                )
                assert client is not None
                try:
                    assert client.request_restart()
                finally:
                    client.close()
            return result

    def wait(identity: ProcessIdentity) -> None:
        """Require the exact outgoing process before native election."""
        assert identity in (ProcessIdentity(77, 123.5), ProcessIdentity(88, 124.5))
        events.append(f"waited:{identity.pid}")

    def start(command: tuple[str, ...]) -> None:
        """Prove the native ownership is released before normal launch starts."""
        assert command[0].endswith("SugarSubstitute.exe")
        broker = ApplicationInstanceBroker.elect(
            install_root=root, invocation=ApplicationInvocation.capture(())
        )
        assert broker is not None
        broker.close()
        events.append("launched")

    supervisor = RepairSessionSupervisor(
        presentation=Presentation(),
        process_waiter=wait,
        app_starter=start,
        environment=with_supervisor_handoff({}, ProcessIdentity(88, 124.5)),
    )
    if result == -1:
        with pytest.raises(RuntimeError, match="controlled presentation failure"):
            supervisor.run(request)
    else:
        assert supervisor.run(request) == result
    assert events == [
        "waited:88",
        "waited:77",
        "presented",
        *(["launched"] if result == 0 else []),
    ]
    released = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(())
    )
    assert released is not None
    released.close()


def test_secondary_repair_reaches_existing_owner_without_execution(
    tmp_path: Path,
) -> None:
    """A second repair command should activate the owner without starting work."""
    root = tmp_path / "installation"
    staging = root / ".repair/staging/1.2.3"
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
    )
    broker = ApplicationInstanceBroker.elect(
        install_root=root, invocation=ApplicationInvocation.capture(())
    )
    assert broker is not None
    activations: list[ApplicationInvocation] = []

    def present(invocation: ApplicationInvocation) -> str:
        """Acknowledge the existing test presentation through native IPC."""
        activations.append(invocation)
        return "repair-test-surface"

    class UnexpectedPresentation:
        """Reject any attempt to start a second repair presentation."""

        def run(
            self, candidate: PreparedRepairRequest, environment: Mapping[str, str]
        ) -> int:
            """Fail if election admits another execution owner."""
            pytest.fail("A second repair presentation started")

    with broker:
        broker.bind_startup_presenter(present)
        assert (
            RepairSessionSupervisor(
                presentation=UnexpectedPresentation(), environment={}
            ).run(request)
            == 0
        )
    assert len(activations) == 1


def test_repair_election_failure_reaches_application_recovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Let users leave failed repair ownership through the shared recovery flow."""
    from launcher.sugarsubstitute_launcher import launcher_ui_supervision
    from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
        InstanceRecoveryAction,
    )
    from sugarsubstitute_shared.application_instance_protocol import (
        ApplicationInstanceBrokerError,
    )

    root = tmp_path / "installation"
    staging = root / ".repair/staging/1.2.3"
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
    )
    recovery_requests: list[object] = []

    def fail_election(**kwargs: object) -> None:
        """Represent an unavailable native owner without contacting other processes."""
        raise ApplicationInstanceBrokerError("controlled unavailable owner")

    def recover(**kwargs: object) -> InstanceRecoveryAction:
        """Record the offered recovery and model the user choosing Exit."""
        recovery_requests.append(kwargs["layout"])
        return InstanceRecoveryAction.EXIT

    class UnexpectedPresentation:
        """Prevent repair work while no ownership has been acquired."""

        def run(
            self, candidate: PreparedRepairRequest, environment: Mapping[str, str]
        ) -> int:
            """Reject execution without an elected supervisor."""
            pytest.fail("Repair ran without ownership")

    monkeypatch.setattr(ApplicationInstanceBroker, "elect", fail_election)
    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", recover
    )
    assert (
        RepairSessionSupervisor(
            presentation=UnexpectedPresentation(), environment={}
        ).run(request)
        == 0
    )
    assert len(recovery_requests) == 1


@pytest.mark.parametrize("has_supervisor", [True, False])
def test_repair_handoff_retires_unavailable_owner_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    has_supervisor: bool,
) -> None:
    """Keep a stalled outgoing supervisor recoverable before repair acquires ownership."""
    from launcher.sugarsubstitute_launcher import launcher_ui_supervision
    from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
        InstanceRecoveryAction,
    )
    from sugarsubstitute_shared.process_identity import ProcessIdentityError

    root = tmp_path / "installation"
    staging = root / ".repair/staging/1.2.3"
    outgoing = ProcessIdentity(1234, 456.0)
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
    )
    from launcher.sugarsubstitute_launcher import application_instance_recovery
    from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope

    if not has_supervisor:
        request = request.with_process_behavior(
            wait_pid=outgoing.pid,
            wait_process_created_at=outgoing.created_at,
            relaunch=False,
        )
    offered: list[bool] = []
    attempts: list[ProcessIdentity] = []
    terminated: list[ProcessIdentity] = []
    presentations: list[bool] = []

    def wait(identity: ProcessIdentity) -> None:
        """Model the exact outgoing owner's bounded wait failing."""
        assert identity == outgoing
        attempts.append(identity)
        if len(attempts) == 1:
            raise ProcessIdentityError("controlled outgoing timeout")

    def recover(**kwargs: object) -> InstanceRecoveryAction:
        """Record unexpected manual intervention before repair admission."""
        offered.append("can_end_owner" in kwargs)
        return InstanceRecoveryAction.EXIT

    def terminate(identity: ProcessIdentity, *, scope: ApplicationProcessScope) -> bool:
        """Record authenticated recovery without sending a signal to any process."""
        terminated.append(identity)
        return True

    class Presentation:
        """Reject mutations while the old supervisor has not exited."""

        def run(
            self, candidate: PreparedRepairRequest, environment: Mapping[str, str]
        ) -> int:
            """Fail if repair bypasses the outgoing-owner boundary."""
            assert len(attempts) == 2
            presentations.append(True)
            return 0

    monkeypatch.setattr(
        launcher_ui_supervision, "supervise_instance_recovery_window", recover
    )
    monkeypatch.setattr(
        application_instance_recovery, "terminate_verified_process", terminate
    )
    assert (
        RepairSessionSupervisor(
            presentation=Presentation(),
            process_waiter=wait,
            environment=with_supervisor_handoff({}, outgoing) if has_supervisor else {},
        ).run(request)
        == 0
    )
    assert offered == []
    assert presentations == [True]
    assert terminated == [outgoing]
