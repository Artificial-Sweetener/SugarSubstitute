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

"""Verify MainWindow delegates drag and drop events to the workspace owner."""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

from substitute.presentation.shell.main_window import MainWindow


class _WorkspaceDropController:
    """Record MainWindow drag and drop delegation requests."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        """Store the event history owned by this focused test double."""

        self.events = events

    def handle_drag_enter(self, event: object) -> bool:
        """Record an accepted drag-enter request."""

        self.events.append(("enter", event))
        return True

    def handle_drag_move(self, event: object) -> bool:
        """Record an accepted drag-move request."""

        self.events.append(("move", event))
        return True

    def handle_drop(self, event: object) -> bool:
        """Record an accepted drop request."""

        self.events.append(("drop", event))
        return True


class _Shell:
    """Provide the MainWindow-owned workspace drop-controller boundary."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        """Initialize the owned drop-controller collaborator."""

        self.workspace_drop_controller = _WorkspaceDropController(events)


class _DragDropDelegate(Protocol):
    """Describe the concrete MainWindow event overrides under test."""

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Delegate a drag-enter event to the workspace owner."""

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Delegate a drag-move event to the workspace owner."""

    def dropEvent(self, event: QDropEvent) -> None:
        """Delegate a drop event to the workspace owner."""


def test_drag_drop_events_delegate_to_workspace_drop_controller() -> None:
    """Delegate each MainWindow drag/drop override to the workspace owner."""

    events: list[tuple[str, object]] = []
    enter_event = object()
    move_event = object()
    drop_event = object()

    shell = _Shell(events)
    main_window = cast(_DragDropDelegate, shell)
    main_window_type = cast(type[_DragDropDelegate], MainWindow)

    main_window_type.dragEnterEvent(main_window, cast(QDragEnterEvent, enter_event))
    main_window_type.dragMoveEvent(main_window, cast(QDragMoveEvent, move_event))
    main_window_type.dropEvent(main_window, cast(QDropEvent, drop_event))

    assert events == [
        ("enter", enter_event),
        ("move", move_event),
        ("drop", drop_event),
    ]
