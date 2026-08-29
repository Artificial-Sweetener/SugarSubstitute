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

"""Hold crash-safe operating-system ownership for one application instance."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from sugarsubstitute_shared.process_lifetime_lease import ProcessLifetimeLease
from sugarsubstitute_shared.windows_long_paths import operational_path


APPLICATION_INSTANCE_LEASE_NAME = "application-instance.lease"


class ApplicationInstanceLease(ProcessLifetimeLease):
    """Own one installation-scoped lease until release or process termination."""

    @classmethod
    def acquire(
        cls,
        install_root: Path,
        *,
        timeout_seconds: float = 0.0,
    ) -> Self | None:
        """Acquire the process-lifetime lease within one bounded wait."""

        return cls.acquire_path(
            application_instance_lease_path(install_root),
            timeout_seconds=timeout_seconds,
        )

    @classmethod
    def owner_exists(cls, install_root: Path) -> bool:
        """Return whether another process currently holds the lifetime lease."""

        lease = cls.acquire(install_root)
        if lease is None:
            return True
        lease.release()
        return False


def application_instance_lease_path(install_root: Path) -> Path:
    """Return the installation-scoped lifetime lease path."""

    return (
        operational_path(install_root).expanduser().resolve()
        / "launcher"
        / "locks"
        / APPLICATION_INSTANCE_LEASE_NAME
    )


__all__ = [
    "APPLICATION_INSTANCE_LEASE_NAME",
    "ApplicationInstanceLease",
    "application_instance_lease_path",
]
