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

"""Define authoritative Comfy connection and recovery state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from substitute.domain.onboarding import ComfyTargetMode


class ComfyConnectionPhase(str, Enum):
    """Identify the user-relevant phase of the active Comfy connection."""

    READY = "ready"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    RESTARTING = "restarting"
    RESTART_FAILED = "restart_failed"


@dataclass(frozen=True, slots=True)
class ComfyConnectionState:
    """Describe current connection state and safe recovery capabilities."""

    phase: ComfyConnectionPhase
    target_mode: ComfyTargetMode
    can_restart: bool
    revision: int = 0


@dataclass(frozen=True, slots=True)
class ComfyConnectionStateChange:
    """Describe one deduplicated connection-state transition."""

    previous: ComfyConnectionState
    current: ComfyConnectionState


__all__ = [
    "ComfyConnectionPhase",
    "ComfyConnectionState",
    "ComfyConnectionStateChange",
]
