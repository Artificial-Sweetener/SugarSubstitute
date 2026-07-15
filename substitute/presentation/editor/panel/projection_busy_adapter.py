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

"""Adapt editor projection busy presentation to the shell-owned panel API."""

from __future__ import annotations

from typing import Any

from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.editor.panel.projection_busy_adapter")


class EditorProjectionBusyAdapter:
    """Own shell busy-overlay calls for staged editor projections."""

    def __init__(self, panel: Any) -> None:
        """Store the live panel that exposes shell busy presentation hooks."""

        self._panel = panel

    def begin_projection_busy(
        self,
        *,
        workflow_id: str,
        pending_build_count: int,
    ) -> object | None:
        """Request shell-owned busy presentation for a staged projection."""

        begin_busy = getattr(self._panel, "_begin_projection_busy", None)
        busy_token = begin_busy("Loading") if callable(begin_busy) else None
        log_info(
            _LOGGER,
            "Began editor projection busy state",
            workflow_id=workflow_id,
            pending_build_count=pending_build_count,
            busy_started=busy_token is not None,
        )
        return busy_token

    def end_projection_busy(
        self,
        busy_token: object | None,
        *,
        workflow_id: str,
        busy_started: bool,
        pending_build_count: int,
    ) -> None:
        """Release shell-owned busy presentation after a staged projection."""

        try:
            end_busy = getattr(self._panel, "_end_projection_busy", None)
            if callable(end_busy):
                end_busy(busy_token)
        finally:
            log_info(
                _LOGGER,
                "Ended editor projection busy state",
                workflow_id=workflow_id,
                pending_build_count=pending_build_count,
                busy_started=busy_started,
            )
