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

"""Require selected-folder setup to recover unavailable native owners automatically."""

from pathlib import Path
import json
import socket

import pytest
import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.application_launch import elect_application
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_supervisor_client import (
    ApplicationSupervisorClient,
)
from tests.launcher.application_readiness.process_family_fixture import command

pytestmark = pytest.mark.platforms("windows")


@pytest.mark.parametrize("freeze_owner", [False, True])
def test_selected_folder_recovers_an_owner_without_a_usable_surface(
    tmp_path: Path,
    freeze_owner: bool,
) -> None:
    """Use production setup election and require recovery before any fixture cleanup."""
    target = tmp_path / "selected"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(15)
        family, _log = spawn_supervised_process(
            command("broker", listener.getsockname()[1], target),
            startup_log_path=tmp_path / "owner.log",
        )
        bootstrap = None
        client = None
        try:
            channel, _address = listener.accept()
            with channel:
                channel.settimeout(10)
                with channel.makefile("rb") as stream:
                    ready = json.loads(stream.read())
            assert ready["role"] == "broker"
            if freeze_owner:
                owner = psutil.Process(ready["pid"])
                assert owner.pid == family.pid or family.pid in {
                    parent.pid for parent in owner.parents()
                }
                owner.suspend()
            bootstrap = elect_application(
                InstallLayout.from_root(tmp_path / "bootstrap"), ["setup"]
            )
            assert bootstrap is not None
            client = ApplicationSupervisorClient.connect_from_environment(
                bootstrap.child_environment({})
            )
            assert client is not None
            assert client.claim_installation(target)
            family.wait(timeout=10)
            assert family.poll() is not None
            assert not target.exists()
            received: list[ApplicationInvocation] = []

            def present(invocation: ApplicationInvocation) -> str:
                """Acknowledge the newly admitted setup owner after recovery."""
                received.append(invocation)
                return "setup"

            bootstrap.bind_startup_presenter(present)
            invocation = ApplicationInvocation.capture(["repeat"])
            assert (
                ApplicationInstanceBroker.elect(
                    install_root=target, invocation=invocation
                )
                is None
            )
            assert received == [invocation]
        finally:
            if client is not None:
                client.close()
            if bootstrap is not None:
                bootstrap.close()
            if family.poll() is None:
                family.kill()
            family.wait(timeout=10)
