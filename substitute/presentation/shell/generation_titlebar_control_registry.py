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

"""Synchronize shell generation titlebar controls across window surfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)

if TYPE_CHECKING:
    from substitute.presentation.shell.titlebar_buttons import (
        GenerationTitleBarRunControl,
    )


@dataclass(frozen=True)
class _ControlConnections:
    """Store callbacks connected for one registered titlebar control."""

    play_clicked: Callable[..., None]
    skip_clicked: Callable[..., None]
    queue_clicked: Callable[..., None]
    queue_context_menu_requested: Callable[..., None]
    stop_clicked: Callable[..., None]
    generate_mode_selected: Callable[..., None]
    batch_count_changed: Callable[..., None]


class GenerationTitleBarControlRegistry(QObject):
    """Synchronize all shell generation titlebar controls."""

    def __init__(
        self,
        *,
        on_generate: Callable[[], None],
        on_skip: Callable[[], None],
        on_stop: Callable[[], None],
        show_queue_for: Callable[[QWidget], None],
        show_queue_context_menu_for: Callable[[QWidget], None],
        on_generate_mode_selected: Callable[[str], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create registry with explicit generation command callbacks."""

        super().__init__(parent)
        self._on_generate = on_generate
        self._on_skip = on_skip
        self._on_stop = on_stop
        self._show_queue_for = show_queue_for
        self._show_queue_context_menu_for = show_queue_context_menu_for
        self._on_generate_mode_selected = on_generate_mode_selected
        self._latest_presentation: GenerationActionPresentation | None = None
        self._batch_count = 1
        self._syncing_batch_count = False
        self._connections: dict[GenerationTitleBarRunControl, _ControlConnections] = {}

    def register(self, control: GenerationTitleBarRunControl) -> None:
        """Register one titlebar generation control with shared state."""

        if control in self._connections:
            return

        connections = _ControlConnections(
            play_clicked=lambda *_args: self._on_generate(),
            skip_clicked=lambda *_args: self._on_skip(),
            queue_clicked=lambda *_args, source=control: self._show_queue_for(
                source.queue_button_target()
            ),
            queue_context_menu_requested=(
                lambda *_args, source=control: self._show_queue_context_menu_for(
                    source.queue_button_target()
                )
            ),
            stop_clicked=lambda *_args: self._on_stop(),
            generate_mode_selected=(
                lambda mode, *_args: self._handle_generate_mode_selected(str(mode))
            ),
            batch_count_changed=(
                lambda value, *_args, source=control: self.set_batch_count(
                    int(value), source=source
                )
            ),
        )
        control.playClicked.connect(connections.play_clicked)
        control.skipClicked.connect(connections.skip_clicked)
        control.queueClicked.connect(connections.queue_clicked)
        control.queueContextMenuRequested.connect(
            connections.queue_context_menu_requested
        )
        control.stopClicked.connect(connections.stop_clicked)
        control.generateModeSelected.connect(connections.generate_mode_selected)
        control.batchCountChanged.connect(connections.batch_count_changed)
        self._connections[control] = connections

        self._apply_batch_count(control, self._batch_count)
        if self._latest_presentation is not None:
            control.apply_generation_presentation(self._latest_presentation)

    def unregister(self, control: GenerationTitleBarRunControl) -> None:
        """Unregister one titlebar generation control and disconnect callbacks."""

        connections = self._connections.pop(control, None)
        if connections is None:
            return
        self._disconnect(control.playClicked, connections.play_clicked)
        self._disconnect(control.skipClicked, connections.skip_clicked)
        self._disconnect(control.queueClicked, connections.queue_clicked)
        self._disconnect(
            control.queueContextMenuRequested,
            connections.queue_context_menu_requested,
        )
        self._disconnect(control.stopClicked, connections.stop_clicked)
        self._disconnect(
            control.generateModeSelected,
            connections.generate_mode_selected,
        )
        self._disconnect(control.batchCountChanged, connections.batch_count_changed)

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Apply one generation presentation snapshot to all controls."""

        self._latest_presentation = presentation
        for control in tuple(self._connections):
            control.apply_generation_presentation(presentation)
            self._apply_batch_count(control, self._batch_count)

    def effective_batch_count(self) -> int:
        """Return the shared effective generation batch count."""

        if (
            self._latest_presentation is not None
            and not self._latest_presentation.batch_accessory_visible
        ):
            return 1
        return max(1, self._batch_count)

    def set_batch_count(
        self,
        value: int,
        *,
        source: GenerationTitleBarRunControl | None = None,
    ) -> None:
        """Set the shared batch count and mirror it to every other control."""

        if self._syncing_batch_count:
            return
        normalized_value = max(1, int(value))
        self._batch_count = normalized_value
        self._syncing_batch_count = True
        try:
            for control in tuple(self._connections):
                if control is source:
                    continue
                control.set_batch_count(normalized_value)
        finally:
            self._syncing_batch_count = False

    def _apply_batch_count(
        self,
        control: GenerationTitleBarRunControl,
        value: int,
    ) -> None:
        """Apply batch count to one control without re-entering the registry."""

        self._syncing_batch_count = True
        try:
            control.set_batch_count(max(1, int(value)))
        finally:
            self._syncing_batch_count = False

    def _handle_generate_mode_selected(self, mode: str) -> None:
        """Forward one selected generation mode from any registered control."""

        if self._on_generate_mode_selected is not None:
            self._on_generate_mode_selected(mode)

    @staticmethod
    def _disconnect(signal: Any, callback: Callable[..., None]) -> None:
        """Disconnect one signal callback while tolerating stale Qt handles."""

        try:
            signal.disconnect(callback)
        except (RuntimeError, TypeError):
            return


__all__ = ["GenerationTitleBarControlRegistry"]
