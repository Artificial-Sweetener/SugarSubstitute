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

"""Own macOS application election and activation through native frameworks."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import ctypes
from dataclasses import dataclass
from enum import Enum
from importlib import import_module
import json
import threading
from typing import Protocol, cast

from sugarsubstitute_shared.application_instance_macos_core_foundation import (
    CoreFoundationMessagePortApi,
    MAXIMUM_MESSAGE_BYTES,
    MessagePortCallback,
    MessagePortContext,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInvocation,
    parse_application_invocation,
)


_ACTIVATE_ALL_WINDOWS = 1
_ACTIVATE_IGNORING_OTHER_APPS = 2
_MESSAGE_IDENTIFIER = 1
_MESSAGE_TIMEOUT_SECONDS = 5.0


class MacOSMessagePortElection(str, Enum):
    """Describe whether this process owns the per-session Mach message port."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class MacOSMessagePortClaim:
    """Own one named Core Foundation port and dispatch native invocations."""

    def __init__(
        self,
        *,
        port: int,
        core_foundation: CoreFoundationMessagePortApi,
        callback: object,
    ) -> None:
        """Prepare the run loop that services the already-elected message port."""

        self._port = port
        self._core_foundation = core_foundation
        self._callback = callback
        self._handler: Callable[[ApplicationInvocation], None] | None = None
        self._pending: deque[ApplicationInvocation] = deque(maxlen=64)
        self._lock = threading.Lock()
        self._run_loop: int | None = None
        self._ready = threading.Event()
        self._startup_failed = False
        self._context_owner: object | None = None
        self._context_pointer: object | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="application-instance-macos-message-port",
            daemon=True,
        )

    def start(self) -> None:
        """Start and verify the Core Foundation service run loop."""

        self._thread.start()
        if not self._ready.wait(timeout=_MESSAGE_TIMEOUT_SECONDS):
            self.close()
            raise RuntimeError("The macOS instance message port did not become ready.")
        if self._startup_failed:
            self.close()
            raise RuntimeError(
                "The macOS instance message port has no run-loop source."
            )

    def bind_invocation_handler(
        self,
        handler: Callable[[ApplicationInvocation], None],
    ) -> None:
        """Bind the broker and replay invocations received during startup."""

        with self._lock:
            self._handler = handler
            pending = tuple(self._pending)
            self._pending.clear()
        for invocation in pending:
            handler(invocation)

    def retain_callback_context(self, owner: object, pointer: object) -> None:
        """Keep the Python callback context alive for the port lifetime."""

        self._context_owner = owner
        self._context_pointer = pointer

    def receive_message(self, data: int) -> int:
        """Validate one native message and return an acknowledged CFData response."""

        try:
            payload = self._core_foundation.read_data(data)
            if len(payload) > MAXIMUM_MESSAGE_BYTES:
                raise ValueError("Application instance message exceeds its size limit.")
            message = json.loads(payload.decode("utf-8"))
            if not isinstance(message, dict):
                raise ValueError("Application instance message must be an object.")
            invocation = parse_application_invocation(cast(dict[str, object], message))
            with self._lock:
                handler = self._handler
                if handler is None:
                    self._pending.append(invocation)
                else:
                    handler(invocation)
            response = b"accepted"
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            response = b"rejected"
        return self._core_foundation.create_data(response)

    def close(self) -> None:
        """Invalidate and release the native message-port name exactly once."""

        with self._lock:
            port = self._port
            self._port = 0
            run_loop = self._run_loop
        if not port:
            return
        self._core_foundation.invalidate_port(port)
        if run_loop is not None:
            self._core_foundation.stop_run_loop(run_loop)
        if threading.current_thread() is not self._thread and self._thread.is_alive():
            self._thread.join(timeout=_MESSAGE_TIMEOUT_SECONDS)
        self._core_foundation.release(port)

    def _run(self) -> None:
        """Attach the local port to this thread's Core Foundation run loop."""

        source = self._core_foundation.create_run_loop_source(self._port)
        if not source:
            self._startup_failed = True
            self._ready.set()
            return
        run_loop = self._core_foundation.current_run_loop()
        mode = self._core_foundation.default_run_loop_mode()
        with self._lock:
            self._run_loop = run_loop
        self._core_foundation.add_run_loop_source(run_loop, source, mode)
        self._ready.set()
        try:
            self._core_foundation.run_current_loop()
        finally:
            self._core_foundation.remove_run_loop_source(run_loop, source, mode)
            self._core_foundation.release(source)


@dataclass(frozen=True, slots=True)
class MacOSMessagePortResult:
    """Return the macOS message-port election and retained claim."""

    election: MacOSMessagePortElection
    claim: MacOSMessagePortClaim | None = None


class _RunningApplication(Protocol):
    """Describe the AppKit activation surface used by forwarded launches."""

    def activateWithOptions_(self, options: int) -> bool:
        """Activate this application using AppKit policy flags."""


def _dispatch_message(
    _port: int,
    _message_id: int,
    data: int,
    context: int,
) -> int:
    """Dispatch one Core Foundation callback to its retained Python owner."""

    holder = cast(
        list[MacOSMessagePortClaim | None],
        ctypes.cast(context, ctypes.POINTER(ctypes.py_object)).contents.value,
    )
    owner = holder[0]
    return owner.receive_message(data) if owner is not None else 0


def acquire_macos_message_port(identity: str) -> MacOSMessagePortResult:
    """Atomically claim one per-login-session Core Foundation message port."""

    core_foundation = CoreFoundationMessagePortApi()
    name = core_foundation.create_name(_message_port_name(identity))
    owner_holder: list[MacOSMessagePortClaim | None] = [None]
    owner_pointer = ctypes.py_object(owner_holder)
    owner_context = ctypes.pointer(owner_pointer)
    context = MessagePortContext(
        version=0,
        info=ctypes.cast(owner_context, ctypes.c_void_p),
        retain=None,
        release=None,
        copy_description=None,
    )
    callback = MessagePortCallback(_dispatch_message)
    try:
        creation = core_foundation.create_local_port(name, callback, context)
    finally:
        core_foundation.release(name)
    if not creation.created:
        if creation.port:
            core_foundation.release(creation.port)
        return MacOSMessagePortResult(MacOSMessagePortElection.SECONDARY)
    claim = MacOSMessagePortClaim(
        port=creation.port,
        core_foundation=core_foundation,
        callback=callback,
    )
    owner_holder[0] = claim
    claim.retain_callback_context(owner_pointer, owner_context)
    claim.start()
    return MacOSMessagePortResult(MacOSMessagePortElection.PRIMARY, claim)


def forward_macos_invocation(identity: str, invocation: ApplicationInvocation) -> None:
    """Send one invocation through the elected Core Foundation message port."""

    try:
        core_foundation = CoreFoundationMessagePortApi()
        name = core_foundation.create_name(_message_port_name(identity))
    except RuntimeError as error:
        raise ApplicationInstanceBrokerError(str(error)) from error
    try:
        port = core_foundation.create_remote_port(name)
    finally:
        core_foundation.release(name)
    if not port:
        raise ApplicationInstanceBrokerError(
            "The active macOS application supervisor could not be reached."
        )
    request = json.dumps(invocation.to_message(), separators=(",", ":")).encode()
    data = core_foundation.create_data(request)
    try:
        status, response = core_foundation.send_request(
            port,
            _MESSAGE_IDENTIFIER,
            data,
            _MESSAGE_TIMEOUT_SECONDS,
        )
        if status != 0 or not response:
            raise ApplicationInstanceBrokerError(
                f"The macOS application supervisor rejected IPC with status {status}."
            )
        try:
            accepted = core_foundation.read_data(response) == b"accepted"
        finally:
            core_foundation.release(response)
        if not accepted:
            raise ApplicationInstanceBrokerError(
                "The active macOS application supervisor rejected the invocation."
            )
    finally:
        core_foundation.release(data)
        core_foundation.release(port)


def activate_current_macos_application() -> None:
    """Ask AppKit to foreground the existing application for a forwarded launch."""

    appkit = import_module("AppKit")
    running_application_type = getattr(appkit, "NSRunningApplication")
    application = cast(
        _RunningApplication,
        running_application_type.currentApplication(),
    )
    application.activateWithOptions_(
        _ACTIVATE_ALL_WINDOWS | _ACTIVATE_IGNORING_OTHER_APPS
    )


def _message_port_name(identity: str) -> str:
    """Return the per-session Core Foundation ownership and messaging name."""

    return f"ai.artificialsweetener.Substitute.Instance.{identity}"


__all__ = [
    "MacOSMessagePortClaim",
    "MacOSMessagePortElection",
    "MacOSMessagePortResult",
    "acquire_macos_message_port",
    "activate_current_macos_application",
    "forward_macos_invocation",
]
