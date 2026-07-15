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

"""Own deterministic cleanup for resources scoped to one GUI shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.shell.shell_resource_lifecycle")


@dataclass(frozen=True, slots=True)
class ShellResourceCleanupFailure:
    """Describe one shell resource that failed to release."""

    resource_name: str
    error: BaseException


class ShellResourceShutdownError(RuntimeError):
    """Report shell resources that could not be released before replacement."""

    def __init__(self, failures: tuple[ShellResourceCleanupFailure, ...]) -> None:
        """Build an actionable aggregate cleanup error."""

        self.failures = failures
        names = ", ".join(failure.resource_name for failure in failures)
        super().__init__(f"Failed to release GUI shell resources: {names}.")


@dataclass(frozen=True, slots=True)
class _ShellResourceCleanup:
    """Bind one diagnostic resource name to its cleanup operation."""

    resource_name: str
    cleanup: Callable[[], None]


class ShellResourceLifecycle:
    """Release shell-scoped resources once in reverse construction order."""

    def __init__(self) -> None:
        """Create an open lifecycle registry for one shell composition."""

        self._cleanups: list[_ShellResourceCleanup] = []
        self._is_shutdown = False

    @property
    def is_shutdown(self) -> bool:
        """Return whether every registered resource has been released."""

        return self._is_shutdown

    def register(self, resource_name: str, cleanup: Callable[[], None]) -> None:
        """Register one resource cleanup before the shell becomes active."""

        normalized_name = resource_name.strip()
        if not normalized_name:
            raise ValueError("resource_name must not be blank.")
        if self._is_shutdown:
            raise RuntimeError("Cannot register resources after shell shutdown.")
        self._cleanups.append(
            _ShellResourceCleanup(
                resource_name=normalized_name,
                cleanup=cleanup,
            )
        )

    def shutdown(
        self,
        *_signal_args: object,
    ) -> tuple[ShellResourceCleanupFailure, ...]:
        """Release all resources and retain failed operations for a retry."""

        if self._is_shutdown:
            return ()

        failed_cleanups: list[_ShellResourceCleanup] = []
        failures: list[ShellResourceCleanupFailure] = []
        for registered in reversed(self._cleanups):
            try:
                registered.cleanup()
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Failed to release GUI shell resource",
                    resource_name=registered.resource_name,
                    error=error,
                )
                failed_cleanups.append(registered)
                failures.append(
                    ShellResourceCleanupFailure(
                        resource_name=registered.resource_name,
                        error=error,
                    )
                )

        self._cleanups = list(reversed(failed_cleanups))
        self._is_shutdown = not self._cleanups
        return tuple(failures)

    def shutdown_or_raise(self) -> None:
        """Release every resource or reject a shell replacement with context."""

        failures = self.shutdown()
        if failures:
            raise ShellResourceShutdownError(failures)


__all__ = [
    "ShellResourceCleanupFailure",
    "ShellResourceLifecycle",
    "ShellResourceShutdownError",
]
