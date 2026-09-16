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

"""Retain native launch addresses for one supervisor and its selected installation."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import threading
import time

from sugarsubstitute_shared.application_instance_election import (
    ApplicationInstanceReservation,
    SelectedInstallationReservation,
    application_instance_endpoints,
    reserve_application_instance,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceBrokerError,
    ApplicationInvocation,
)
from sugarsubstitute_shared.application_instance_transport import (
    ApplicationInstanceListener,
)

_LOGGER = logging.getLogger(__name__)


class ApplicationInstanceBindings:
    """Route bootstrap and selected-folder addresses through one process owner."""

    def __init__(
        self,
        reservation: ApplicationInstanceReservation,
        *,
        closing: threading.Event,
        handle_connection: Callable[[ApplicationInstanceConnection], None],
        reserve_selected: SelectedInstallationReservation | None = None,
    ) -> None:
        """Retain the initial reservation before accepting any client requests."""
        self._closing = closing
        self._handle_connection = handle_connection
        self._reserve_selected = reserve_selected
        self._lock = threading.Lock()
        self._reservations = {reservation.endpoint: reservation}
        self._threads: list[threading.Thread] = []
        try:
            self._start(reservation)
        except BaseException:
            self.close()
            raise

    def claim(self, install_root: Path, *, on_activity: Callable[[], None]) -> bool:
        """Admit the chosen folder or present its existing application owner.

        Ownership is acquired before mutation and retained through worker and UI
        transitions. Repeated admission of the same identity is idempotent.
        Native resources alone govern exclusion; no persisted claim blocks launch.
        """
        endpoint = application_instance_endpoints(install_root)[0]
        with self._lock:
            if self._closing.is_set():
                raise ApplicationInstanceBrokerError(
                    "The application owner is closing."
                )
            if endpoint in self._reservations:
                return True
            invocation = ApplicationInvocation.capture(
                ["SugarSubstitute", f"--install-root={install_root}"],
                working_directory=install_root,
            )
            reservation = (
                reserve_application_instance(install_root, invocation)
                if self._reserve_selected is None
                else self._reserve_selected(install_root, invocation, on_activity)
            )
            if reservation is None:
                return False
            if self._closing.is_set():
                reservation.close()
                raise ApplicationInstanceBrokerError(
                    "The application owner is closing."
                )
            self._reservations[endpoint] = reservation
            try:
                self._start(reservation)
            except BaseException as error:
                self._reservations.pop(endpoint)
                reservation.close()
                if isinstance(error, (OSError, RuntimeError)):
                    raise ApplicationInstanceBrokerError(
                        "The selected installation listener could not start."
                    ) from error
                raise
            _LOGGER.info(
                "Supervisor admitted selected installation | transport=%s",
                endpoint.transport,
            )
            return True

    def close(self) -> bool:
        """Release every claimed address and bound the accept-thread shutdown."""
        self._closing.set()
        with self._lock:
            reservations = tuple(self._reservations.values())
            self._reservations.clear()
            threads = tuple(self._threads)
        for reservation in reservations:
            reservation.close()
        deadline = time.monotonic() + 2.0
        for thread in threads:
            if thread.ident is not None and threading.current_thread() is not thread:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))
        stopped = all(not thread.is_alive() for thread in threads)
        if not stopped:
            _LOGGER.warning("Application instance accept thread did not stop")
        return stopped

    def _start(self, reservation: ApplicationInstanceReservation) -> None:
        """Start accepting only after the complete native reservation exists."""
        abandoned = threading.Event()
        started: list[threading.Thread] = []
        try:
            for listener in reservation.listeners:
                thread = threading.Thread(
                    target=self._accept,
                    args=(listener, abandoned),
                    name="application-instance-broker",
                    daemon=True,
                )
                self._threads.append(thread)
                thread.start()
                started.append(thread)
        except BaseException:
            abandoned.set()
            reservation.close()
            deadline = time.monotonic() + 2.0
            for thread in started:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))
            raise

    def _accept(
        self, listener: ApplicationInstanceListener, abandoned: threading.Event
    ) -> None:
        """Dispatch authenticated native connections until ownership ends."""
        while not self._closing.is_set() and not abandoned.is_set():
            try:
                connection = listener.accept()
            except OSError:
                if not self._closing.is_set() and not abandoned.is_set():
                    time.sleep(0.01)
                continue
            threading.Thread(
                target=self._handle_connection,
                args=(connection,),
                name="application-instance-request",
                daemon=True,
            ).start()
