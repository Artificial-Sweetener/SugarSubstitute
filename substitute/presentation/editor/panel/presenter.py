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

"""Coordinate editor-panel controller wiring without owning panel behavior."""

from __future__ import annotations

from typing import Protocol


class EditorPanelPresenterHost(Protocol):
    """Describe the host surface required by the panel presenter."""


class EditorPanelPresenter:
    """Hold panel presenter wiring points for later controller extraction."""

    def __init__(self, host: EditorPanelPresenterHost) -> None:
        """Initialize the presenter shell with its host panel."""

        self._host = host

    @property
    def host(self) -> EditorPanelPresenterHost:
        """Return the host panel used for future controller wiring."""

        return self._host


__all__ = ["EditorPanelPresenter", "EditorPanelPresenterHost"]
