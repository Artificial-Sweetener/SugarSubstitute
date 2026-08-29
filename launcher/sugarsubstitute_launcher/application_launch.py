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

"""Own installed-application launch authority for shortcut invocations."""

from __future__ import annotations

import time
from typing import Self

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_lease import ApplicationInstanceLease
from sugarsubstitute_shared.application_launch_guard import ApplicationLaunchGuard
from sugarsubstitute_shared.application_launch_guard import (
    recover_unleased_application_launch,
)
from sugarsubstitute_shared.application_runtime_mode import (
    packaged_application_environment,
)
from sugarsubstitute_shared.launcher_invocation_lease import LauncherInvocationLease
from sugarsubstitute_shared.startup_remote_access import StartupRemoteAccess


class InstalledApplicationLaunchSession:
    """Serialize one launcher transaction and classify application ownership."""

    def __init__(
        self,
        layout: InstallLayout,
        invocation_lease: LauncherInvocationLease,
    ) -> None:
        """Retain exclusive launcher ownership until handoff work finishes."""

        self._layout = layout
        self._invocation_lease: LauncherInvocationLease | None = invocation_lease

    @classmethod
    def begin(cls, layout: InstallLayout) -> Self | None:
        """Return one launcher session or reject a concurrent launcher silently."""

        invocation_lease = LauncherInvocationLease.acquire(layout.root)
        if invocation_lease is None:
            return None
        return cls(layout, invocation_lease)

    def claim_application(self) -> ApplicationLaunchGuard | None:
        """Claim app handoff or report that a real application owns its lease."""

        guard = _claim_installed_application_launch(self._layout)
        if guard is not None or ApplicationInstanceLease.owner_exists(
            self._layout.root
        ):
            return guard
        recover_unleased_application_launch(self._layout.root)
        return _claim_installed_application_launch(self._layout)

    def release(self) -> None:
        """Release launcher serialization without changing application ownership."""

        invocation_lease = self._invocation_lease
        if invocation_lease is None:
            return
        self._invocation_lease = None
        invocation_lease.release()

    def wait_for_application_owner(self, *, timeout_seconds: float = 30.0) -> bool:
        """Keep launcher serialization until the child owns its native lease."""

        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while time.monotonic() < deadline:
            if ApplicationInstanceLease.owner_exists(self._layout.root):
                return True
            time.sleep(0.025)
        return ApplicationInstanceLease.owner_exists(self._layout.root)


def begin_installed_application_launch(
    layout: InstallLayout,
) -> InstalledApplicationLaunchSession | None:
    """Begin one launcher transaction before any splash or dialog construction."""

    return InstalledApplicationLaunchSession.begin(layout)


def _claim_installed_application_launch(
    layout: InstallLayout,
) -> ApplicationLaunchGuard | None:
    """Claim one application handoff within an exclusive launcher transaction."""

    return ApplicationLaunchGuard.enter(
        layout.root,
        allow_initial_handoff=True,
        acquire_instance_lease=False,
    )


def installed_application_environment(
    launch_guard: ApplicationLaunchGuard,
    *,
    remote_failure_reason: str | None,
) -> dict[str, str]:
    """Build one app-child environment with the launcher's remote outcome."""

    remote_access = StartupRemoteAccess()
    if remote_failure_reason is not None:
        remote_access.degrade(reason=remote_failure_reason)
    return packaged_application_environment(
        remote_access.child_environment(launch_guard.initial_handoff_environment())
    )


__all__ = [
    "InstalledApplicationLaunchSession",
    "begin_installed_application_launch",
    "installed_application_environment",
]
