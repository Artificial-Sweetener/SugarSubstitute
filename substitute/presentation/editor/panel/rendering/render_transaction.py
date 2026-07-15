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

"""Batch editor widget reveal operations behind parent-chain validation."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from PySide6.QtWidgets import QWidget

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.rendering.render_transaction")


class EditorRenderTransaction:
    """Batch editor widget mutation and reveal only fully attached widgets."""

    def __init__(self, root: QWidget) -> None:
        """Create a transaction scoped to one editor root widget."""

        self._root = root
        self._callbacks: list[Callable[[], None]] = []
        self._updates_were_enabled = True

    def __enter__(self) -> EditorRenderTransaction:
        """Disable root updates while callers apply grouped widget mutations."""

        self._updates_were_enabled = self._root.updatesEnabled()
        self._root.setUpdatesEnabled(False)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Restore root updates and run queued post-layout callbacks on success."""

        del tb
        self._root.setUpdatesEnabled(self._updates_were_enabled)
        if exc_type is not None or exc is not None:
            return
        for callback in self._callbacks:
            callback()
        self._root.update()

    def attach_cube(self, cube_widget: QWidget) -> None:
        """Reveal one cube widget after layout attachment."""

        self.reveal_when_attached(cube_widget)

    def attach_node_card(self, node_card: QWidget) -> None:
        """Reveal one node card after layout attachment."""

        self.reveal_when_attached(node_card)

    def reveal_when_attached(self, widget: QWidget) -> None:
        """Reveal a widget only when it already belongs to this transaction root."""

        if not self._is_descendant_of_root(widget):
            log_warning(
                _LOGGER,
                "Skipped reveal for unattached editor widget",
                widget_type=type(widget).__name__,
                object_name=widget.objectName(),
                root_type=type(self._root).__name__,
                root_object_name=self._root.objectName(),
            )
            return
        widget.setVisible(True)

    def schedule_after_layout(self, callback: Callable[[], None]) -> None:
        """Queue a callback to run after a successful transaction exits."""

        self._callbacks.append(callback)

    def _is_descendant_of_root(self, widget: QWidget) -> bool:
        """Return whether the widget parent chain reaches the transaction root."""

        current: QWidget | None = widget
        while current is not None:
            if current is self._root:
                return True
            current = current.parentWidget()
        return False
