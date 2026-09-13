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

"""Retain application invocations until a supervised surface presents them."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
import json
import logging
import os
import secrets
import threading

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInvocation,
    ApplicationInvocationReceipt,
    RoutedApplicationInvocation,
    parse_application_invocation_receipt,
    receive_instance_message,
    send_instance_message,
)


_LOGGER = logging.getLogger(__name__)


class ApplicationInvocationRouter:
    """Own durable in-process routing from waiting launchers to one app child."""

    def __init__(
        self,
        *,
        child_token: str,
        closing: threading.Event,
        maximum_active_requests: int,
        receipt_deadline_seconds: float,
    ) -> None:
        """Initialize bounded request state and the replaceable child channel."""

        self._child_token = child_token
        self._closing = closing
        self._maximum_active_requests = maximum_active_requests
        self._receipt_deadline_seconds = receipt_deadline_seconds
        self._pending: deque[RoutedApplicationInvocation] = deque()
        self._inflight: dict[str, RoutedApplicationInvocation] = {}
        self._waiters: dict[str, ApplicationInstanceConnection] = {}
        self._waiter_timers: dict[str, threading.Timer] = {}
        self._released_request_ids: set[str] = set()
        self._startup_presenter: (
            Callable[[ApplicationInvocation], str | None] | None
        ) = None
        self._state_lock = threading.Lock()
        self._child_socket: ApplicationInstanceConnection | None = None
        self._child_send_lock = threading.Lock()

    def bind_startup_presenter(
        self,
        presenter: Callable[[ApplicationInvocation], str | None] | None,
    ) -> None:
        """Expose a visible startup or recovery surface before child registration."""

        with self._state_lock:
            self._startup_presenter = presenter
            pending = tuple(self._pending) if presenter is not None else ()
        for request in pending:
            self._present_during_startup(request)

    def close(self) -> None:
        """Release every child and launcher connection with explicit outcomes."""

        with self._state_lock:
            child_socket = self._child_socket
            self._child_socket = None
            waiters = tuple(self._waiters.items())
            waiter_timers = tuple(self._waiter_timers.values())
            self._waiters.clear()
            self._waiter_timers.clear()
            self._pending.clear()
            self._inflight.clear()
            self._released_request_ids.clear()
            self._startup_presenter = None
        for timer in waiter_timers:
            timer.cancel()
        for request_id, waiter in waiters:
            try:
                _send_invocation_response(
                    waiter,
                    ApplicationInvocationReceipt(
                        request_id=request_id,
                        outcome="unavailable",
                        surface="supervisor-closing",
                    ),
                )
            finally:
                _close_connection(waiter)
        if child_socket is not None:
            _close_connection(child_socket)

    def register_child(self, connection: ApplicationInstanceConnection) -> None:
        """Replace the supervised child channel and flush retained invocations."""

        child_process_id = _peer_process_id(connection)
        with self._state_lock:
            previous = self._child_socket
            self._child_socket = connection
            pending = (*self._inflight.values(), *self._pending)
            self._inflight.clear()
            self._pending.clear()
        if previous is not None:
            _close_connection(previous)
        send_instance_message(connection, {"status": "accepted"})
        _LOGGER.info(
            "Registered supervised application child | owner_pid=%s | child_pid=%s | "
            "queued_invocations=%s",
            os.getpid(),
            child_process_id,
            len(pending),
        )
        try:
            for invocation in pending:
                self._deliver_or_queue(invocation)
            while not self._closing.is_set():
                self._handle_child_message(receive_instance_message(connection))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        finally:
            inflight: tuple[RoutedApplicationInvocation, ...] = ()
            with self._state_lock:
                if self._child_socket is connection:
                    self._child_socket = None
                    inflight = tuple(self._inflight.values())
                    self._inflight.clear()
                    self._pending.extendleft(reversed(inflight))
            if self._closing.is_set():
                _LOGGER.info(
                    "Supervised application child closed with its owner | "
                    "owner_pid=%s | child_pid=%s | retained_invocations=%s",
                    os.getpid(),
                    child_process_id,
                    len(inflight),
                )
            else:
                _LOGGER.warning(
                    "Supervised application child disconnected | owner_pid=%s | "
                    "child_pid=%s | requeued_invocations=%s",
                    os.getpid(),
                    child_process_id,
                    len(inflight),
                )
            _close_connection(connection)

    def route_invocation(
        self,
        invocation: RoutedApplicationInvocation,
        *,
        waiter: ApplicationInstanceConnection,
    ) -> bool:
        """Retain one caller and its work until presentation is proven."""

        with self._state_lock:
            active_request_ids = {
                request.request_id for request in self._pending
            } | set(self._inflight)
            duplicate = invocation.request_id in active_request_ids
            overloaded = len(active_request_ids) >= self._maximum_active_requests
            accepted = not duplicate and not overloaded
            if accepted:
                self._waiters[invocation.request_id] = waiter
                timer = threading.Timer(
                    self._receipt_deadline_seconds,
                    self._expire_waiting_launcher,
                    args=(invocation.request_id,),
                )
                timer.daemon = True
                self._waiter_timers[invocation.request_id] = timer
        if not accepted:
            surface = "duplicate-request" if duplicate else "supervisor-overloaded"
            _send_invocation_response(
                waiter,
                ApplicationInvocationReceipt(
                    request_id=invocation.request_id,
                    outcome="unavailable",
                    surface=surface,
                ),
            )
            _LOGGER.warning(
                "Rejected secondary invocation without dropping active work | "
                "request_id=%s | reason=%s",
                invocation.request_id,
                surface,
            )
            return False
        timer.start()
        _LOGGER.info(
            "Accepted secondary invocation for presentation | owner_pid=%s | "
            "request_id=%s | requester_pid=%s",
            os.getpid(),
            invocation.request_id,
            _peer_process_id(waiter),
        )
        self._deliver_or_queue(invocation)
        return True

    def _deliver_or_queue(self, invocation: RoutedApplicationInvocation) -> None:
        """Deliver one request to the current child or retain it for replacement."""

        with self._state_lock:
            child_socket = self._child_socket
            if child_socket is None:
                self._pending.append(invocation)
                should_present = self._startup_presenter is not None
            else:
                should_present = False
                self._inflight[invocation.request_id] = invocation
        if child_socket is None:
            if should_present:
                self._present_during_startup(invocation)
            return
        _LOGGER.info(
            "Delivered secondary invocation to application child | request_id=%s",
            invocation.request_id,
        )
        try:
            with self._child_send_lock:
                send_instance_message(child_socket, invocation.to_message())
        except OSError:
            with self._state_lock:
                if self._child_socket is child_socket:
                    self._child_socket = None
                self._inflight.pop(invocation.request_id, None)
                self._pending.appendleft(invocation)

    def _handle_child_message(self, message: Mapping[str, object]) -> None:
        """Authenticate and settle one child presentation receipt."""

        token = message.get("token")
        if not isinstance(token, str) or not secrets.compare_digest(
            token,
            self._child_token,
        ):
            raise ValueError("Application invocation receipt token is invalid.")
        receipt = parse_application_invocation_receipt(message)
        with self._state_lock:
            invocation = self._inflight.pop(receipt.request_id, None)
            waiter = self._waiters.pop(receipt.request_id, None)
            waiter_timer = self._waiter_timers.pop(receipt.request_id, None)
            released = receipt.request_id in self._released_request_ids
            if receipt.outcome == "presented":
                self._released_request_ids.discard(receipt.request_id)
            elif invocation is not None:
                self._pending.append(invocation)
                self._released_request_ids.add(receipt.request_id)
        if waiter_timer is not None:
            waiter_timer.cancel()
        if invocation is None:
            _LOGGER.warning(
                "Ignored application presentation receipt without an active request",
                extra={"request_id": receipt.request_id},
            )
            return
        if waiter is None and released:
            _LOGGER.info(
                "Application completed invocation after its launcher was released | "
                "request_id=%s | surface=%s | outcome=%s",
                receipt.request_id,
                receipt.surface,
                receipt.outcome,
            )
            return
        if waiter is None:
            _LOGGER.warning(
                "Ignored application presentation receipt without a waiting launcher",
                extra={"request_id": receipt.request_id},
            )
            return
        try:
            _LOGGER.info(
                "Application completed secondary invocation | request_id=%s | "
                "surface=%s | outcome=%s",
                receipt.request_id,
                receipt.surface,
                receipt.outcome,
            )
            _send_invocation_response(waiter, receipt)
        finally:
            _close_connection(waiter)

    def _present_during_startup(self, request: RoutedApplicationInvocation) -> None:
        """Acknowledge a secondary only after the startup surface is presented."""

        with self._state_lock:
            presenter = self._startup_presenter
            if presenter is None or request.request_id in self._released_request_ids:
                return
        try:
            surface = presenter(request.invocation)
        except Exception:
            _LOGGER.exception(
                "Startup surface presentation failed",
                extra={"request_id": request.request_id},
            )
            return
        if surface is None:
            return
        with self._state_lock:
            waiter = self._waiters.pop(request.request_id, None)
            waiter_timer = self._waiter_timers.pop(request.request_id, None)
            if waiter is None:
                return
            self._released_request_ids.add(request.request_id)
        if waiter_timer is not None:
            waiter_timer.cancel()
        try:
            _LOGGER.info(
                "Presented startup surface for secondary invocation | request_id=%s "
                "| surface=%s",
                request.request_id,
                surface,
            )
            _send_invocation_response(
                waiter,
                ApplicationInvocationReceipt(
                    request_id=request.request_id,
                    outcome="presented",
                    surface=surface,
                ),
            )
        finally:
            _close_connection(waiter)

    def _expire_waiting_launcher(self, request_id: str) -> None:
        """Release a caller at the deadline without losing routed work."""

        with self._state_lock:
            waiter = self._waiters.pop(request_id, None)
            self._waiter_timers.pop(request_id, None)
            if waiter is None:
                return
            self._released_request_ids.add(request_id)
        _LOGGER.warning(
            "Secondary invocation reached the presentation deadline | request_id=%s",
            request_id,
        )
        try:
            _send_invocation_response(
                waiter,
                ApplicationInvocationReceipt(
                    request_id=request_id,
                    outcome="unavailable",
                    surface="presentation-timeout",
                ),
            )
        finally:
            _close_connection(waiter)


def _send_invocation_response(
    connection: ApplicationInstanceConnection,
    receipt: ApplicationInvocationReceipt,
) -> None:
    """Return one bounded presentation outcome to a waiting launcher."""

    try:
        send_instance_message(
            connection,
            {
                "status": receipt.outcome,
                "request_id": receipt.request_id,
                "surface": receipt.surface,
                "owner_process_id": os.getpid(),
            },
        )
    except OSError:
        _LOGGER.debug(
            "Application invocation caller disconnected before presentation receipt",
            extra={"request_id": receipt.request_id},
        )


def _peer_process_id(connection: ApplicationInstanceConnection) -> int | None:
    """Read optional transport identity without breaking invocation routing."""

    try:
        return connection.peer_process_id()
    except OSError:
        return None


def _close_connection(connection: ApplicationInstanceConnection) -> None:
    """Close one transport connection idempotently."""

    try:
        connection.close()
    except OSError:
        pass


__all__ = ["ApplicationInvocationRouter"]
