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

"""Classify workspace-owned drag sources for fallback drop handling."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QObject


class WorkspaceCanvasDragSourceClassifier:
    """Identify drag sources that originate from shell-owned canvas panes."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose canvas panes should be inspected."""

        self._shell = shell

    def is_workspace_canvas_drag_source(self, source: object | None) -> bool:
        """Return whether a drag source belongs to one of this shell's canvases."""

        if source is None:
            return False
        canvas_tabs = getattr(self._shell, "canvas_tabs", None)
        canvas_map = getattr(canvas_tabs, "canvas_map", None)
        if not isinstance(canvas_map, Mapping):
            return False
        for canvas in canvas_map.values():
            pane = getattr(canvas, "pane", None)
            if self.drag_source_matches_pane(source, pane):
                return True
        return False

    @staticmethod
    def drag_source_matches_pane(source: object, pane: object | None) -> bool:
        """Return whether a drag source is a pane or one of its QObject children."""

        if pane is None:
            return False
        if source is pane:
            return True
        if not isinstance(source, QObject):
            return False
        current_parent = source.parent()
        while current_parent is not None:
            if current_parent is pane:
                return True
            current_parent = current_parent.parent()
        return False


def workspace_canvas_drag_source_classifier_for(
    shell: Any,
) -> WorkspaceCanvasDragSourceClassifier:
    """Return the composed drag-source classifier for a shell."""

    classifier = getattr(shell, "workspace_canvas_drag_source_classifier", None)
    if isinstance(classifier, WorkspaceCanvasDragSourceClassifier):
        return classifier
    classifier = WorkspaceCanvasDragSourceClassifier(shell)
    setattr(shell, "workspace_canvas_drag_source_classifier", classifier)
    return classifier


__all__ = [
    "WorkspaceCanvasDragSourceClassifier",
    "workspace_canvas_drag_source_classifier_for",
]
