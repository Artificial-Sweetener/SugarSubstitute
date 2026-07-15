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

"""Qt signal bridges for GUI-thread startup callbacks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, Signal


class ManagedCompatibilityRecoverySignalProtocol(Protocol):
    """Describe the signal surface used by managed recovery completion."""

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect a completion callback to the signal."""


class ManagedCompatibilityRecoveryBridgeProtocol(Protocol):
    """Describe the managed recovery completion bridge surface."""

    @property
    def finished(self) -> ManagedCompatibilityRecoverySignalProtocol:
        """Return the completion signal."""


class StartupDiagnosticsTitlebarBridge(QObject):
    """Route prepared diagnostics state back onto the Qt startup thread."""

    prepared = Signal(object)


class ManagedCompatibilityRecoveryBridge(QObject):
    """Route managed compatibility recovery completion to the Qt startup thread."""

    finished = Signal(object)


def create_managed_compatibility_recovery_bridge() -> (
    ManagedCompatibilityRecoveryBridge
):
    """Create the Qt bridge for managed compatibility recovery completion."""

    return ManagedCompatibilityRecoveryBridge()


def connect_managed_compatibility_recovery_bridge(
    *,
    bridge: ManagedCompatibilityRecoveryBridgeProtocol,
    callback: Callable[..., object],
) -> object:
    """Connect managed compatibility recovery completion to a callback."""

    return bridge.finished.connect(callback)


__all__ = [
    "ManagedCompatibilityRecoveryBridgeProtocol",
    "ManagedCompatibilityRecoverySignalProtocol",
    "ManagedCompatibilityRecoveryBridge",
    "StartupDiagnosticsTitlebarBridge",
    "connect_managed_compatibility_recovery_bridge",
    "create_managed_compatibility_recovery_bridge",
]
