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

"""Serialize decoded-frame commands behind asynchronous libmpv seeks."""

from __future__ import annotations

from collections import deque

from substitute.infrastructure.video.mpv_player_factory import MpvPlayerProtocol


class MpvFrameStepCoordinator:
    """Preserve frame-step intent while libmpv completes an exact seek."""

    def __init__(self, player: MpvPlayerProtocol) -> None:
        """Bind command scheduling to one long-lived native player."""

        self._player = player
        self._seek_pending = False
        self._pending_commands: deque[str] = deque()

    def reset(self) -> None:
        """Discard media-scoped command state during replacement or unload."""

        self._seek_pending = False
        self._pending_commands.clear()

    def seek(self, seconds: float) -> None:
        """Start an exact seek and supersede steps requested for an older target."""

        self._pending_commands.clear()
        self._seek_pending = True
        try:
            self._player.command("seek", seconds, "absolute+exact")
        except Exception:
            self._seek_pending = False
            raise

    def step(self, command: str) -> None:
        """Execute a frame command now or retain it until the seek settles."""

        self._player.pause = True
        if self._seek_pending:
            self._pending_commands.append(command)
            return
        self._player.command(command)

    def observe_seeking(self, value: object) -> None:
        """Release queued frame commands after libmpv reports seek completion."""

        if value is not False or not self._seek_pending:
            return
        self._seek_pending = False
        commands = tuple(self._pending_commands)
        self._pending_commands.clear()
        for command in commands:
            self._player.command(command)

    def cancel_steps(self) -> None:
        """Let an explicit Play request supersede queued frame-step intent."""

        self._pending_commands.clear()


__all__ = ["MpvFrameStepCoordinator"]
