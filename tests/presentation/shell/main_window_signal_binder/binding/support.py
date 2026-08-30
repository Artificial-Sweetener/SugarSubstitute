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

"""Provide deterministic signal and app-orb doubles for routing tests."""

from __future__ import annotations

from collections.abc import Callable


class _Signal:
    """Capture Qt-like signal connections and allow deterministic emission."""

    def __init__(self) -> None:
        """Initialize an empty callback list."""

        self.connections: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Record a signal callback."""

        self.connections.append(callback)

    def fire(self, *args: object) -> None:
        """Invoke connected callbacks with the emitted payload."""

        for callback in self.connections:
            callback(*args)


class _AppOrbMenu:
    """Expose app-orb signals used by the signal binder."""

    def __init__(self) -> None:
        """Create every app-orb signal expected by the binder."""

        self.openRequested = _Signal()
        self.saveRequested = _Signal()
        self.saveAsRequested = _Signal()
        self.exportRequested = _Signal()
        self.settingsRequested = _Signal()
        self.comfyUiSettingsRequested = _Signal()
        self.restartGuiRequested = _Signal()
        self.restartComfyRequested = _Signal()
