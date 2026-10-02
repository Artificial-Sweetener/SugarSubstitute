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

"""Admit startup recovery only after the installation's current writer finishes."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import logging
from pathlib import Path
from threading import Event
import time

from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
    InstallationStartupDeferred,
)
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationBusyError,
    InstallationMutationOwnership,
    installation_mutation,
)

_LOGGER = logging.getLogger(__name__)
_POLL_SECONDS = 0.05


class StartupInstallationWait:
    """Own cancellable startup admission without changing writer exclusion policy."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 120.0,
        monotonic: Callable[[], float] = time.monotonic,
        wait: Callable[[float], object] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> None:
        """Bind bounded waiting to the caller's authenticated cancellation signal."""
        if timeout_seconds <= 0:
            raise ValueError("Installation startup wait must be positive.")
        self._timeout_seconds = timeout_seconds
        self._monotonic = monotonic
        self._wait = wait or Event().wait
        self._cancellation_requested = cancellation_requested

    @contextmanager
    def acquire(self, root: Path) -> Iterator[InstallationMutationOwnership]:
        """Wait for native admission, then retain authority through recovery.

        Advisory identity records and journal absence never authorize reading a
        changing installation. Each retry asks the same kernel owner; timeout
        and cancellation leave the writer and its prepared work untouched.
        """
        deadline = self._monotonic() + self._timeout_seconds
        waiting = False
        while True:
            if (
                self._cancellation_requested is not None
                and self._cancellation_requested()
            ):
                raise ApplicationStartupCancelled()
            claim = installation_mutation(root)
            try:
                operation = claim.__enter__()
            except InstallationMutationBusyError:
                if not waiting:
                    _LOGGER.info("Waiting for installation writer before startup")
                    waiting = True
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    _LOGGER.warning(
                        "Installation writer remains active; deferring startup"
                    )
                    raise InstallationStartupDeferred() from None
                self._wait(min(_POLL_SECONDS, remaining))
                continue
            try:
                if waiting:
                    _LOGGER.info(
                        "Installation writer finished; admitted startup recovery"
                    )
                yield operation
            finally:
                claim.__exit__(None, None, None)
            return
