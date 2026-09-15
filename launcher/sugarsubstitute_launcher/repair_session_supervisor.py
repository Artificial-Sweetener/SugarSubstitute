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

"""Own native application election throughout one detached repair presentation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import os
from typing import Protocol

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.application_election_recovery import (
    ApplicationElectionRecovery,
)
from launcher.sugarsubstitute_launcher.application_launch import elect_application
from launcher.sugarsubstitute_launcher.repair_handoff_process_scope import (
    RepairHandoffProcessScope,
)
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.process_execution import start_detached
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
    wait_for_process_exit,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
)
from sugarsubstitute_shared.application_instance_transport import (
    instance_endpoint,
    instance_identity,
)
from sugarsubstitute_shared.supervisor_handoff import consume_supervisor_handoff
from sugarsubstitute_shared.windows_long_paths import subprocess_path


class RepairSessionPresentation(Protocol):
    """Run the independently hosted repair window beneath its native supervisor."""

    def run(
        self, request: PreparedRepairRequest, environment: Mapping[str, str]
    ) -> int:
        """Return only when the visible child and its repair work have finished."""


class RepairSessionSupervisor:
    """Keep normal launches from racing repair and release ownership before restart."""

    def __init__(
        self,
        *,
        presentation: RepairSessionPresentation,
        process_waiter: Callable[[ProcessIdentity], None] = wait_for_process_exit,
        app_starter: Callable[[tuple[str, ...]], None] = start_detached,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        """Bind presentation and process boundaries without importing Qt."""
        self._presentation = presentation
        self._process_waiter = process_waiter
        self._app_starter = app_starter
        self._environment = dict(os.environ if environment is None else environment)

    def run(self, request: PreparedRepairRequest) -> int:
        """Wait for outgoing owners, supervise repair exclusively, then restart normally."""
        environment = dict(self._environment)
        outgoing = consume_supervisor_handoff(environment)
        target = launcher_target_for_key(request.target_key)
        layout = InstallLayout.from_root(request.install_root, target=target)

        def elect_after_handoff(
            candidate: InstallLayout, arguments: Sequence[str]
        ) -> ApplicationInstanceBroker | None:
            """Recheck outgoing lifetimes on every recovery attempt before election."""
            identities = [outgoing] if outgoing is not None else []
            if request.wait_pid is not None:
                assert request.wait_process_created_at is not None
                caller = ProcessIdentity(
                    request.wait_pid, request.wait_process_created_at
                )
                if caller not in identities:
                    identities.append(caller)
            for identity in identities:
                try:
                    self._process_waiter(identity)
                except ProcessIdentityError as error:
                    raise ApplicationInstanceBrokerError(
                        "Outgoing repair process did not exit",
                        endpoint=instance_endpoint(instance_identity(candidate.root)),
                        owner_identity=identity,
                    ) from error
            return elect_application(candidate, arguments)

        broker = ApplicationElectionRecovery(
            layout=layout,
            process_arguments=(subprocess_path(layout.executable_path), "--repair"),
            locale_override=None,
            elect=elect_after_handoff,
            process_scope=RepairHandoffProcessScope(layout),
            presentation_layout=(
                InstallLayout.from_root(request.helper_bundle_dir, target=target)
                if request.helper_bundle_dir is not None
                else None
            ),
        ).run()
        if broker is None:
            return 0
        with broker:
            result = self._presentation.run(
                request, broker.child_environment(environment)
            )
            open_requested = broker.consume_restart_request()
        if result == 0 and open_requested:
            self._app_starter(
                (
                    subprocess_path(layout.executable_path),
                    f"--install-root={subprocess_path(layout.root)}",
                )
            )
        return result
