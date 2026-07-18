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

"""Verify durable workspace layout across cube and direct documents."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.workspace_layout_controller import (
    WorkspaceLayoutController,
)


class _Splitter:
    """Record canvas insertion and removal against a two-pane workspace."""

    def __init__(
        self, details: object, canvas: object, *, canvas_attached: bool
    ) -> None:
        """Store pane identities and initial canvas participation."""

        self._details = details
        self._canvas = canvas
        self.canvas_attached = canvas_attached
        self.insertions: list[tuple[int, object]] = []

    def indexOf(self, widget: object) -> int:
        """Return the current pane index for one widget identity."""

        if widget is self._details:
            return 0
        if widget is self._canvas and self.canvas_attached:
            return 1
        return -1

    def insertWidget(self, index: int, widget: object) -> None:
        """Record reattaching the canvas pane."""

        self.canvas_attached = True
        self.insertions.append((index, widget))

    def sizes(self) -> list[int]:
        """Return stable trace-only splitter sizes."""

        return [600, 400]


class _CanvasContainer:
    """Record detachment from the workspace splitter."""

    def __init__(self) -> None:
        """Initialize an empty parent history."""

        self.parents: list[object | None] = []

    def setParent(self, parent: object | None) -> None:
        """Record one Qt-compatible parent request."""

        self.parents.append(parent)

    def width(self) -> int:
        """Return a stable trace width."""

        return 400


def _shell(*, stack_width: int, canvas_attached: bool) -> SimpleNamespace:
    """Build the narrow shell surface consumed by canvas participation."""

    details = SimpleNamespace(width=lambda: 536)
    canvas = _CanvasContainer()
    emitted: list[int] = []
    shell = SimpleNamespace(
        canvas_tabs=SimpleNamespace(
            sizeHint=lambda: SimpleNamespace(width=lambda: 400)
        ),
        active_editor_panel=lambda: details,
        cube_stack_container=SimpleNamespace(width=lambda: stack_width),
        editor_output_container=details,
        canvas_tabs_container=canvas,
        resize_requested=SimpleNamespace(emit=emitted.append),
        search_overlay_controller=SimpleNamespace(position_search_box=lambda: None),
        editor_output_splitter=SimpleNamespace(sizes=lambda: []),
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow"),
        _remembered_workflow_splitter_sizes=(),
    )
    shell.splitter = _Splitter(details, canvas, canvas_attached=canvas_attached)
    shell.emitted = emitted
    return shell


def test_hidden_canvas_in_direct_workflow_uses_zero_stack_width() -> None:
    """Direct documents resize from editor width without requiring a stack widget."""

    shell = _shell(stack_width=0, canvas_attached=True)

    WorkspaceLayoutController(shell).toggle_canvas_tabs(False)

    assert shell.emitted == [536]
    assert shell.canvas_tabs_container.parents == [None]


def test_show_canvas_in_direct_workflow_reattaches_after_editor() -> None:
    """Direct documents can restore canvas participation while the stack is unavailable."""

    shell = _shell(stack_width=0, canvas_attached=False)

    WorkspaceLayoutController(shell).toggle_canvas_tabs(True)

    assert shell.splitter.insertions == [(1, shell.canvas_tabs_container)]
    assert shell.emitted == [936]
