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

"""Prove selected launchers can use one retained native broker authority."""

from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    RoutedApplicationInvocation,
    ApplicationInvocation,
    ApplicationInstanceBrokerError,
    BROKER_TOKEN_ENV,
)
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)


def test_delegated_session_routes_startup_and_retains_owner_on_close(
    tmp_path: Path,
) -> None:
    """Retire a generation session without releasing the installation broker."""
    from sugarsubstitute_shared.delegated_application_broker import (
        DelegatedApplicationBroker,
    )

    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    with owner:
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        received: list[ApplicationInvocation] = []

        def present(invocation: ApplicationInvocation) -> str:
            """Record startup presentation through the actual native control channel."""
            received.append(invocation)
            return "startup-surface"

        delegate.bind_startup_presenter(present)
        try:
            invocation = ApplicationInvocation.capture(["launcher", "--repair"])
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path, invocation=invocation
                )
                is None
            )
            assert received == [invocation]
        finally:
            delegate.close()
        owner.bind_startup_presenter(lambda _invocation: "baseline-surface")
        assert (
            ApplicationInstanceBroker.elect(
                install_root=tmp_path,
                invocation=ApplicationInvocation.capture(["launcher"]),
            )
            is None
        )


def test_delegated_session_consumes_root_restart_exactly_once(tmp_path: Path) -> None:
    """Keep restart state at the retained broker while the generation runs its loop."""
    from sugarsubstitute_shared.delegated_application_broker import (
        DelegatedApplicationBroker,
    )

    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    with owner:
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        child = ApplicationSupervisorClient.connect_from_environment(
            delegate.child_environment({})
        )
        assert child is not None
        try:
            assert child.request_restart()
            with ThreadPoolExecutor(max_workers=4) as consumers:
                outcomes = list(
                    consumers.map(
                        lambda _: delegate.consume_restart_request(), range(4)
                    )
                )
            assert outcomes.count(True) == 1
            assert not delegate.consume_restart_request()
            assert not owner.consume_restart_request()
        finally:
            child.close()
            delegate.close()


def test_delegation_rejects_invalid_credentials_without_releasing_owner(
    tmp_path: Path,
) -> None:
    """Require broker authorization before exposing owner-session operations."""
    from sugarsubstitute_shared.delegated_application_broker import (
        DelegatedApplicationBroker,
    )

    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    with owner:
        environment = owner.child_environment({})
        environment[BROKER_TOKEN_ENV] = "invalid"
        with pytest.raises(ApplicationInstanceBrokerError):
            DelegatedApplicationBroker(environment)
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        delegate.close()


def test_application_replaces_delegated_startup_without_losing_native_owner(
    tmp_path: Path,
) -> None:
    """Retire the splash channel while the actual application keeps receiving launches."""
    from sugarsubstitute_shared.delegated_application_broker import (
        DelegatedApplicationBroker,
    )

    owner = ApplicationInstanceBroker.elect(
        install_root=tmp_path, invocation=ApplicationInvocation.capture(["launcher"])
    )
    assert owner is not None
    with owner:
        delegate = DelegatedApplicationBroker(owner.child_environment({}))
        delegate.bind_startup_presenter(lambda _: "splash")
        child = ApplicationSupervisorClient.connect_from_environment(
            delegate.child_environment({})
        )
        assert child is not None
        received: list[ApplicationInvocation] = []

        def present(request: RoutedApplicationInvocation) -> None:
            """Acknowledge the current application through the real control channel."""
            received.append(request.invocation)
            child.complete_invocation(
                request.request_id, outcome="presented", surface="main-shell"
            )

        child.bind_invocation_handler(present)
        delegate.bind_startup_presenter(None)
        invocation = ApplicationInvocation.capture(["launcher", "--repair"])
        try:
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=tmp_path, invocation=invocation
                )
                is None
            )
            assert received == [invocation]
        finally:
            child.close()
            delegate.close()
