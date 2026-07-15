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

"""Mirror projected generation progress to secondary progress strips."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject

from substitute.presentation.shell.generation_progress_strip import (
    GenerationProgressStrip,
    ProgressViewStateLike,
)
from substitute.presentation.shell.progress_projection import ProgressProjectionMode


@dataclass(frozen=True)
class _RegisteredProgressStrip:
    """Store one strip and its local visibility gate."""

    strip: GenerationProgressStrip
    visible_gate: Callable[[], bool]


class GenerationProgressStripRegistry(QObject):
    """Mirror projected generation progress to secondary progress strips."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an empty progress strip registry."""

        super().__init__(parent)
        self._latest_view_state: ProgressViewStateLike | None = None
        self._registered: dict[GenerationProgressStrip, _RegisteredProgressStrip] = {}

    def register(
        self,
        strip: GenerationProgressStrip,
        *,
        visible_gate: Callable[[], bool],
    ) -> None:
        """Register one secondary progress strip."""

        self._registered[strip] = _RegisteredProgressStrip(
            strip=strip,
            visible_gate=visible_gate,
        )
        if self._latest_view_state is not None:
            strip.apply_progress_view(
                self._latest_view_state,
                mode=ProgressProjectionMode.SELECTION_REPLAY,
            )
        self.refresh_visibility(strip)

    def unregister(self, strip: GenerationProgressStrip) -> None:
        """Unregister one secondary progress strip."""

        self._registered.pop(strip, None)
        strip.set_progress_visible(False)

    def apply_progress_view(
        self,
        view_state: ProgressViewStateLike,
        *,
        mode: ProgressProjectionMode = ProgressProjectionMode.LIVE_UPDATE,
    ) -> None:
        """Apply one projected progress view to every registered strip."""

        self._latest_view_state = view_state
        for registered in tuple(self._registered.values()):
            registered.strip.apply_progress_view(view_state, mode=mode)
            self._apply_visibility(registered)

    def refresh_visibility(self, strip: GenerationProgressStrip) -> None:
        """Refresh local visibility for one registered strip."""

        registered = self._registered.get(strip)
        if registered is None:
            return
        self._apply_visibility(registered)

    def refresh_all_visibility(self) -> None:
        """Refresh local visibility for every registered strip."""

        for registered in tuple(self._registered.values()):
            self._apply_visibility(registered)

    def _apply_visibility(self, registered: _RegisteredProgressStrip) -> None:
        """Apply latest progress and local visibility gates to one strip."""

        if self._latest_view_state is None:
            registered.strip.set_progress_visible(False)
            return
        registered.strip.set_progress_visible(
            bool(self._latest_view_state.show_overlay) and registered.visible_gate()
        )


__all__ = ["GenerationProgressStripRegistry"]
