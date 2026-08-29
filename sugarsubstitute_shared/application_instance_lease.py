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
import time
from typing import BinaryIO, Self, cast

from sugarsubstitute_shared.windows_long_paths import operational_path


APPLICATION_INSTANCE_LEASE_NAME = "application-instance.lease"


class ApplicationInstanceLease:
    """Own one installation-scoped lease until release or process termination."""

    def __init__(self, path: Path, handle: BinaryIO) -> None:
        """Retain the locked handle that gives the lease its lifetime."""

        self._path = path
        self._handle: BinaryIO | None = handle

    @classmethod
    def acquire(
        cls,
        install_root: Path,
        *,
        timeout_seconds: float = 0.0,
    ) -> Self | None:
        """Acquire the process-lifetime lease within one bounded wait."""

        path = application_instance_lease_path(install_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b", buffering=0)
        _ensure_lock_byte(handle)
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            try:
                _try_lock(handle)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    handle.close()
                    return None
                time.sleep(0.025)
        return cls(path, handle)

    @classmethod
    def owner_exists(cls, install_root: Path) -> bool:
        """Return whether another process currently holds the lifetime lease."""

        lease = cls.acquire(install_root)
        if lease is None:
            return True
        lease.release()
        return False

    @property
    def path(self) -> Path:
        """Return the diagnostic path whose open handle carries ownership."""

        return self._path

    def release(self) -> None:
        """Release process ownership idempotently."""

        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _unlock(handle)
        finally:
            handle.close()


def application_instance_lease_path(install_root: Path) -> Path:
    """Return the installation-scoped lifetime lease path."""

    return (
        operational_path(install_root).expanduser().resolve()
        / "launcher"
        / "locks"
        / APPLICATION_INSTANCE_LEASE_NAME
    )


def _ensure_lock_byte(handle: BinaryIO) -> None:
    """Ensure Windows has one stable byte range available for locking."""

    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)


def _try_lock(handle: BinaryIO) -> None:
    """Acquire the platform-native lease without blocking."""

    handle.seek(0)
    import os

    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    _posix_flock(handle, "LOCK_EX", "LOCK_NB")


def _unlock(handle: BinaryIO) -> None:
    """Release the platform-native lease."""

    handle.seek(0)
    import os

    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    _posix_flock(handle, "LOCK_UN")


def _posix_flock(handle: BinaryIO, *flag_names: str) -> None:
    """Call POSIX flock through a typed dynamic platform boundary."""

    import importlib
    from collections.abc import Callable

    module = importlib.import_module("fcntl")
    flock = cast(Callable[[int, int], None], getattr(module, "flock"))
    operation = 0
    for flag_name in flag_names:
        operation |= cast(int, getattr(module, flag_name))
    flock(handle.fileno(), operation)


__all__ = [
    "APPLICATION_INSTANCE_LEASE_NAME",
    "ApplicationInstanceLease",
    "application_instance_lease_path",
]
