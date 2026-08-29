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

"""Serialize launcher transactions independently from application ownership."""

from __future__ import annotations

from pathlib import Path
from typing import Self

from sugarsubstitute_shared.process_lifetime_lease import ProcessLifetimeLease
from sugarsubstitute_shared.windows_long_paths import operational_path


LAUNCHER_INVOCATION_LEASE_NAME = "launcher-invocation.lease"


class LauncherInvocationLease(ProcessLifetimeLease):
    """Own one launcher, update, or duplicate-instance decision transaction."""

    @classmethod
    def acquire(cls, install_root: Path) -> Self | None:
        """Acquire the installation-scoped launcher transaction immediately."""

        return cls.acquire_path(launcher_invocation_lease_path(install_root))


def launcher_invocation_lease_path(install_root: Path) -> Path:
    """Return the installation-scoped launcher transaction lease path."""

    return (
        operational_path(install_root).expanduser().resolve()
        / "launcher"
        / "locks"
        / LAUNCHER_INVOCATION_LEASE_NAME
    )


__all__ = [
    "LAUNCHER_INVOCATION_LEASE_NAME",
    "LauncherInvocationLease",
    "launcher_invocation_lease_path",
]
