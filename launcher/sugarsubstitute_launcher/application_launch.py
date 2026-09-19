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

"""Own application election and supervised child authorization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime_policy import runtime_environment
from launcher.sugarsubstitute_launcher.selected_installation_admission import (
    reserve_selected_installation,
)
from sugarsubstitute_shared.application_broker_session import ApplicationBrokerSession
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_runtime_mode import (
    packaged_application_environment,
)
from sugarsubstitute_shared.startup_remote_access import StartupRemoteAccess


def elect_application(
    layout: InstallLayout,
    arguments: Sequence[str],
) -> ApplicationInstanceBroker | None:
    """Become the installation supervisor or forward this launch and exit."""

    return ApplicationInstanceBroker.elect(
        install_root=layout.root,
        invocation=ApplicationInvocation.capture(arguments),
        reserve_selected=reserve_selected_installation,
    )


def installed_application_environment(
    broker: ApplicationBrokerSession,
    *,
    layout: InstallLayout,
    remote_failure_reason: str | None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build one authenticated app-child environment owned by the supervisor."""

    remote_access = StartupRemoteAccess()
    if remote_failure_reason is not None:
        remote_access.degrade(reason=remote_failure_reason)
    base_environment = os.environ if environment is None else environment
    selected_environment = runtime_environment(
        layout=layout,
        environment=base_environment,
    )
    remote_environment = remote_access.child_environment(selected_environment)
    return broker.child_environment(
        packaged_application_environment(remote_environment)
    )


__all__ = [
    "elect_application",
    "installed_application_environment",
]
