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

"""Own atomic publication of synchronized prompt projection layout state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from ..core.projection.document import PromptProjectionDisplayMode


class PromptProjectionGeometrySynchronization(Protocol):
    """Expose geometry-input synchronization required before layout publication."""

    def synchronize_geometry_inputs(self) -> None:
        """Synchronize reorder geometry inputs with current projection state."""


class PromptProjectionFrameSynchronization(Protocol):
    """Expose frame synchronization required by layout publication."""

    def sync(
        self,
        *,
        display_mode: PromptProjectionDisplayMode,
        commit_projection: bool,
    ) -> None:
        """Synchronize one projection frame with current layout inputs."""


class PromptProjectionLayoutRenderPublication(Protocol):
    """Expose render publication after layout synchronization."""

    def layout_synchronized(self) -> None:
        """Publish render state derived from synchronized layout."""


class PromptProjectionLayoutPublicationOwner:
    """Publish synchronized layout, freshness, chrome, and render state atomically."""

    def __init__(
        self,
        *,
        reorder: PromptProjectionGeometrySynchronization,
        frame_synchronizer: PromptProjectionFrameSynchronization,
        render_publication: PromptProjectionLayoutRenderPublication,
        display_mode: Callable[[], PromptProjectionDisplayMode],
    ) -> None:
        """Bind the ordered effects required for one layout publication."""

        self._reorder = reorder
        self._frame_synchronizer = frame_synchronizer
        self._render_publication = render_publication
        self._display_mode = display_mode

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_SYNC_LAYOUT)
    def sync(self, *, commit_projection: bool = False) -> None:
        """Synchronize geometry inputs and publish one complete layout frame."""

        self._reorder.synchronize_geometry_inputs()
        self._frame_synchronizer.sync(
            display_mode=self._display_mode(),
            commit_projection=commit_projection,
        )
        self._render_publication.layout_synchronized()


__all__ = [
    "PromptProjectionFrameSynchronization",
    "PromptProjectionGeometrySynchronization",
    "PromptProjectionLayoutPublicationOwner",
    "PromptProjectionLayoutRenderPublication",
]
