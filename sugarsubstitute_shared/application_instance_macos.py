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

from dataclasses import dataclass
from enum import Enum
from importlib import import_module
import threading
from typing import Protocol, cast

from sugarsubstitute_shared.application_instance_macos_core_foundation import (
    CoreFoundationMessagePortApi,
    MessagePortCallback,
    MessagePortContext,
)


_ACTIVATE_ALL_WINDOWS = 1
_ACTIVATE_IGNORING_OTHER_APPS = 2


class MacOSMessagePortElection(str, Enum):
    """Describe whether this process owns the per-session Mach message port."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class MacOSMessagePortClaim:
    """Retain one named Core Foundation port as an atomic ownership claim."""

    def __init__(
        self,
        *,
        port: int,
        core_foundation: CoreFoundationMessagePortApi,
        callback: object,
    ) -> None:
        """Retain the elected port and its required callback."""

        self._port = port
        self._core_foundation = core_foundation
        self._callback = callback
        self._lock = threading.Lock()

    def close(self) -> None:
        """Invalidate and release the native ownership name exactly once."""

        with self._lock:
            port = self._port
            self._port = 0
        if not port:
            return
        self._core_foundation.invalidate_port(port)
        self._core_foundation.release(port)


@dataclass(frozen=True, slots=True)
class MacOSMessagePortResult:
    """Return the macOS message-port election and retained claim."""

    election: MacOSMessagePortElection
    claim: MacOSMessagePortClaim | None = None


class _RunningApplication(Protocol):
    """Describe the AppKit activation surface used by forwarded launches."""

    def activateWithOptions_(self, options: int) -> bool:
        """Activate this application using AppKit policy flags."""


def _ignore_message(
    _port: int,
    _message_id: int,
    _data: int,
    _context: int,
) -> int:
    """Reject unexpected traffic on the ownership-only native port."""

    return 0


def acquire_macos_message_port(identity: str) -> MacOSMessagePortResult:
    """Atomically claim one per-login-session Core Foundation message port."""

    core_foundation = CoreFoundationMessagePortApi()
    name = core_foundation.create_name(_message_port_name(identity))
    context = MessagePortContext(
        version=0,
        info=None,
        retain=None,
        release=None,
        copy_description=None,
    )
    callback = MessagePortCallback(_ignore_message)
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
    return MacOSMessagePortResult(MacOSMessagePortElection.PRIMARY, claim)


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
]
