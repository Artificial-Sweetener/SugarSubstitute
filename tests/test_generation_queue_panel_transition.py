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

"""Tests for animated generation queue side-panel shell transitions."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.generation_queue_panel_transition import (
    GenerationQueuePanelTransition,
)
from substitute.presentation.shell.shell_layout_controller import ShellLayoutController

_REDUCED_MOTION_PROPERTY = "substitute.reduce_motion"


@pytest.fixture(autouse=True)
def normal_motion_for_transition_tests() -> Iterator[None]:
    """Run side-panel transition contracts with animations enabled."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    previous_override = app.property(_REDUCED_MOTION_PROPERTY)
    app.setProperty(_REDUCED_MOTION_PROPERTY, False)
    try:
        yield
    finally:
        app.setProperty(_REDUCED_MOTION_PROPERTY, previous_override)


class _Host:
    """Record rendered side-panel width and committed visibility."""

    def __init__(self, *, width: int = 360, visible: bool = False) -> None:
        """Create a fake host with durable and rendered width state."""

        self._panel_width = width
        self._rendered_width = width if visible else 0
        self.visible = visible
        self.begin_calls: list[bool] = []
        self.finish_calls: list[bool] = []
        self.applied_widths: list[int] = []

    def panel_width(self) -> int:
        """Return durable side-panel width."""

        return self._panel_width

    def rendered_width(self) -> int:
        """Return current rendered side-panel width."""

        return self._rendered_width

    def is_queue_panel_visible(self) -> bool:
        """Return committed side-panel visibility."""

        return self.visible

    def begin_width_transition(self, *, target_visible: bool) -> None:
        """Record that transition visibility was prepared."""

        self.begin_calls.append(target_visible)
        self.visible = True

    def apply_width_transition(self, width: int) -> None:
        """Record a rendered width frame."""

        self.applied_widths.append(width)
        self._rendered_width = width

    def finish_width_transition(self, *, visible: bool) -> None:
        """Record final transition visibility."""

        self.finish_calls.append(visible)
        self.visible = visible
        self._rendered_width = self._panel_width if visible else 0


class _Splitter:
    """Record splitter size updates for transition arithmetic tests."""

    def __init__(self, widgets: list[object], sizes: list[int]) -> None:
        """Store fake splitter panes and sizes."""

        self._widgets = list(widgets)
        self._sizes = list(sizes)
        self.set_size_calls: list[list[int]] = []

    def indexOf(self, widget: object) -> int:
        """Return widget index or -1 when absent."""

        try:
            return self._widgets.index(widget)
        except ValueError:
            return -1

    def sizes(self) -> list[int]:
        """Return current fake splitter sizes."""

        return list(self._sizes)

    def setSizes(self, sizes: list[int]) -> None:
        """Record and store one splitter size update."""

        self.set_size_calls.append(list(sizes))
        self._sizes = list(sizes)


def _view(
    *,
    host: _Host,
    splitter: _Splitter | None,
    editor: object | None,
    canvas: object | None,
) -> SimpleNamespace:
    """Build a MainWindow-like fake for side-panel transition tests."""

    remembered: list[list[int]] = []
    view = SimpleNamespace(
        sidePanelHost=host,
        splitter=splitter,
        editor_output_container=editor,
        canvas_tabs_container=canvas,
        remembered=remembered,
    )
    view.shell_layout_controller = ShellLayoutController(view)
    view.shell_layout_controller.remember_workflow_splitter_sizes = lambda sizes: (
        remembered.append(list(sizes))
    )
    return view


def test_generation_queue_panel_transition_open_preserves_editor_width() -> None:
    """Opening should allocate side-panel width from the canvas pane only."""

    editor = object()
    canvas = object()
    host = _Host(width=360, visible=False)
    splitter = _Splitter([editor, canvas, host], [800, 600, 0])
    view = _view(host=host, splitter=splitter, editor=editor, canvas=canvas)
    transition = GenerationQueuePanelTransition(view)

    transition.transition_to(True)
    transition.setProgress(0.5)

    assert host.begin_calls == [True]
    assert host.visible is True
    assert host.applied_widths[-1] == 180
    assert splitter.set_size_calls[-1] == [800, 420, 180]
    assert view.remembered[-1] == [800, 420, 180]
    transition.stop()


def test_generation_queue_panel_transition_close_hides_after_finish() -> None:
    """Closing should release side-panel width to canvas before hiding host."""

    editor = object()
    canvas = object()
    host = _Host(width=360, visible=True)
    splitter = _Splitter([editor, canvas, host], [800, 600, 360])
    view = _view(host=host, splitter=splitter, editor=editor, canvas=canvas)
    transition = GenerationQueuePanelTransition(view)

    transition.transition_to(False)
    transition.setProgress(0.5)

    assert host.begin_calls == [False]
    assert host.visible is True
    assert host.applied_widths[-1] == 180
    assert splitter.set_size_calls[-1] == [800, 780, 180]

    transition._finish_transition()

    assert host.finish_calls[-1] is False
    assert host.visible is False
    assert host.rendered_width() == 0
    assert splitter.set_size_calls[-1] == [800, 960, 0]


def test_generation_queue_panel_transition_reduced_motion_finishes_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reduced motion should commit final side-panel state without animating."""

    import substitute.presentation.shell.generation_queue_panel_transition as mod

    monkeypatch.setattr(mod, "resolve_motion_duration", lambda _duration: 0)
    editor = object()
    canvas = object()
    host = _Host(width=320, visible=False)
    splitter = _Splitter([editor, canvas, host], [700, 500, 0])
    view = _view(host=host, splitter=splitter, editor=editor, canvas=canvas)
    transition = GenerationQueuePanelTransition(view)

    transition.transition_to(True)

    assert transition.is_animating() is False
    assert host.finish_calls == [True]
    assert host.visible is True
    assert host.rendered_width() == 320
    assert splitter.set_size_calls[-1] == [700, 180, 320]


def test_generation_queue_panel_transition_tolerates_missing_splitter() -> None:
    """Transition should still update host geometry when splitter data is absent."""

    host = _Host(width=300, visible=False)
    view = _view(host=host, splitter=None, editor=None, canvas=None)
    transition = GenerationQueuePanelTransition(view)

    transition.transition_to(True)
    transition.setProgress(1.0)

    assert host.applied_widths[-1] == 300
    assert host.visible is True
    transition.stop()
