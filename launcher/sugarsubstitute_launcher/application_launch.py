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

"""Own installed-application election and supervised child authorization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation
from sugarsubstitute_shared.application_runtime_mode import (
    packaged_application_environment,
)
from sugarsubstitute_shared.startup_remote_access import StartupRemoteAccess


def elect_installed_application(
    layout: InstallLayout,
    arguments: Sequence[str],
) -> ApplicationInstanceBroker | None:
    """Become the installation supervisor or forward this launch and exit."""

    return ApplicationInstanceBroker.elect(
        install_root=layout.root,
        invocation=ApplicationInvocation.capture(arguments),
    )


def installed_application_environment(
    broker: ApplicationInstanceBroker,
    *,
    remote_failure_reason: str | None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build one authenticated app-child environment owned by the supervisor."""

    remote_access = StartupRemoteAccess()
    if remote_failure_reason is not None:
        remote_access.degrade(reason=remote_failure_reason)
    remote_environment = remote_access.child_environment(environment or os.environ)
    return broker.child_environment(
        packaged_application_environment(remote_environment)
    )


__all__ = [
    "elect_installed_application",
    "installed_application_environment",
]
