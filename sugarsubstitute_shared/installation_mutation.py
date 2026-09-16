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

"""Serialize installation mutations using process-lifetime kernel ownership."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import errno
import logging
import os
from pathlib import Path
import threading
import sys
from sugarsubstitute_shared.process_identity import ProcessIdentityError
from sugarsubstitute_shared.installation_mutation_record import (
    InstallationMutationRecord,
    open_mutation_record,
    publish_mutation_record,
    read_mutation_record,
    retire_mutation_record,
)

_LOGGER = logging.getLogger(__name__)


class InstallationMutationBusyError(RuntimeError):
    """Preserve prepared intent when another execution owns installation mutation."""

    def __init__(
        self,
        message: str,
        *,
        owner_record: InstallationMutationRecord | None = None,
    ) -> None:
        """Retain candidate identity for independent verification by recovery."""
        super().__init__(message)
        self.owner_record = owner_record


class InstallationMutationOwnership:
    """Retain native ownership for explicitly authorized collaborators only."""

    def __init__(
        self, root: Path, descriptor: int | None, release_lock: Callable[[], None]
    ) -> None:
        """Bind native ownership and advisory metadata to their execution scope."""
        self._root = root
        self._descriptor = descriptor
        self._release_lock = release_lock
        self._process_id = os.getpid()
        self._thread = threading.current_thread()
        self._participants = 1

    def retain(self, root: Path) -> None:
        """Admit a collaborator only while this exact operation remains active."""
        self.validate(root)
        self._participants += 1

    def validate(self, root: Path) -> None:
        """Require the live operation before a retained actor mutates its installation."""
        if (
            self._participants == 0
            or root != self._root
            or os.getpid() != self._process_id
            or threading.current_thread() is not self._thread
        ):
            raise InstallationMutationBusyError(
                "Installation operation ownership is expired or belongs elsewhere."
            )

    def release(self) -> None:
        """Release native ownership when the last authorized participant finishes."""
        self.validate(self._root)
        self._participants -= 1
        if self._participants == 0:
            try:
                try:
                    if self._descriptor is not None:
                        retire_mutation_record(self._descriptor)
                except OSError:
                    _LOGGER.warning(
                        "Could not retire installation ownership identity",
                        exc_info=True,
                    )
            finally:
                try:
                    self._release_lock()
                finally:
                    if self._descriptor is not None:
                        os.close(self._descriptor)


@contextmanager
def installation_mutation(
    install_root: Path,
    *,
    ownership: InstallationMutationOwnership | None = None,
) -> Iterator[InstallationMutationOwnership]:
    """Acquire an independent operation or explicitly retain a collaborator's claim.

    Kernel ownership survives nested scope exit until the last participant ends.
    File existence and thread identity never authorize joining another operation.
    The rendezvous file is advisory; native ownership determines admission.
    """
    root = install_root.resolve()
    if ownership is None:
        descriptor, release_lock = _acquire(root)
        ownership = InstallationMutationOwnership(root, descriptor, release_lock)
    else:
        ownership.retain(root)
    try:
        yield ownership
    finally:
        ownership.release()


def _acquire(root: Path) -> tuple[int | None, Callable[[], None]]:
    """Acquire native authority before publishing a non-authoritative identity hint."""
    descriptor: int | None = None
    release_lock: Callable[[], None] | None = None
    try:
        if sys.platform == "win32":
            release_lock = _lock(root, None)
        try:
            descriptor = open_mutation_record(root)
        except OSError:
            if release_lock is None:
                raise
            _LOGGER.warning(
                "Installation operation acquired without accessible identity-hint storage",
                exc_info=True,
            )
        if release_lock is None:
            release_lock = _lock(root, descriptor)
        if descriptor is None:
            return None, release_lock
        try:
            publish_mutation_record(descriptor)
        except (OSError, ProcessIdentityError):
            _LOGGER.warning(
                "Installation operation acquired without a recovery identity hint",
                exc_info=True,
            )
            try:
                retire_mutation_record(descriptor)
            except OSError:
                _LOGGER.warning(
                    "Could not clear an unproven installation identity hint",
                    exc_info=True,
                )
        return descriptor, release_lock
    except BaseException:
        try:
            if release_lock is not None:
                release_lock()
        finally:
            if descriptor is not None:
                os.close(descriptor)
        raise


def _lock(root: Path, descriptor: int | None) -> Callable[[], None]:
    """Select the platform's native owner and return its scoped release operation."""
    try:
        if sys.platform == "win32":
            from sugarsubstitute_shared.windows_mutation_mutex import (
                WindowsMutationMutex,
            )

            return WindowsMutationMutex(root).release

        import fcntl

        if descriptor is None:
            raise ValueError("POSIX mutation ownership requires its native descriptor.")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            raise
        _LOGGER.info(
            "Installation mutation is owned by another execution",
            extra={"operation": "installation_mutation"},
        )
        raise InstallationMutationBusyError(
            "Installation mutation is already active; prepared work is retained.",
            owner_record=read_mutation_record(root),
        ) from error

    def release() -> None:
        """Release the POSIX claim while the metadata descriptor remains open."""
        fcntl.flock(descriptor, fcntl.LOCK_UN)

    return release
