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

"""Tests for workspace canvas drag-source classification."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject

from substitute.presentation.shell.workspace_drag_source import (
    WorkspaceCanvasDragSourceClassifier,
    workspace_canvas_drag_source_classifier_for,
)


def test_drag_source_classifier_reuses_composed_shell_instance() -> None:
    """Classifier lookup should preserve the shell-composed owner."""

    shell = SimpleNamespace()
    classifier = WorkspaceCanvasDragSourceClassifier(shell)
    shell.workspace_canvas_drag_source_classifier = classifier

    assert workspace_canvas_drag_source_classifier_for(shell) is classifier


def test_workspace_canvas_drag_source_matches_canvas_panes() -> None:
    """Canvas panes registered on the shell should classify as internal sources."""

    input_pane = object()
    output_pane = object()
    external_source = object()
    shell = SimpleNamespace(
        canvas_tabs=SimpleNamespace(
            canvas_map={
                "Input": SimpleNamespace(pane=input_pane),
                "Output": SimpleNamespace(pane=output_pane),
            }
        )
    )
    classifier = WorkspaceCanvasDragSourceClassifier(shell)

    assert classifier.is_workspace_canvas_drag_source(input_pane) is True
    assert classifier.is_workspace_canvas_drag_source(output_pane) is True
    assert classifier.is_workspace_canvas_drag_source(external_source) is False
    assert classifier.is_workspace_canvas_drag_source(None) is False


def test_workspace_canvas_drag_source_ignores_missing_canvas_map() -> None:
    """Missing or non-mapping canvas state should not classify as internal."""

    shell = SimpleNamespace(canvas_tabs=SimpleNamespace(canvas_map=object()))
    classifier = WorkspaceCanvasDragSourceClassifier(shell)

    assert classifier.is_workspace_canvas_drag_source(object()) is False


def test_drag_source_matches_qobject_pane_children() -> None:
    """QObject descendants of a pane should classify as internal drag sources."""

    pane = QObject()
    child = QObject(pane)
    grandchild = QObject(child)
    external = QObject()

    assert (
        WorkspaceCanvasDragSourceClassifier.drag_source_matches_pane(grandchild, pane)
        is True
    )
    assert (
        WorkspaceCanvasDragSourceClassifier.drag_source_matches_pane(external, pane)
        is False
    )
    assert (
        WorkspaceCanvasDragSourceClassifier.drag_source_matches_pane(object(), pane)
        is False
    )
