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

"""Observe authoritative selection-manipulation phases for contextual chrome."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal
from cutecanvas import EditorTransformSnapshot, FloatingPixelSnapshot

from .input_selection_authoring_observer import InputSelectionAuthoringObserver
from .input_tool_options_contracts import InputToolOptionsDocumentPort


class InputContextualToolbarGestureKind(str, Enum):
    """Identify one direct manipulation source affecting toolbar visibility."""

    SELECTION_AUTHORING = "selection-authoring"
    FLOATING_PIXELS = "floating-pixels"
    TRANSFORM = "transform"


@dataclass(frozen=True, slots=True)
class InputContextualToolbarGestureUpdate:
    """Describe one authoritative source transition and aggregate activity."""

    kind: InputContextualToolbarGestureKind
    active: bool
    source_active: bool
    settled: bool
    floating: FloatingPixelSnapshot | None = None
    transform: EditorTransformSnapshot | None = None


class InputContextualToolbarGestureObserver(QObject):
    """Combine direct-manipulation phases without inferring pointer state."""

    changed = Signal(object)

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        selection_authoring: InputSelectionAuthoringObserver,
        parent: QObject,
    ) -> None:
        """Observe public editor snapshots and selection-tool authorship."""

        super().__init__(parent)
        self._active_sources: set[InputContextualToolbarGestureKind] = set()
        document.floatingPixelEditChanged.connect(self._floating_changed)
        document.editorTransformChanged.connect(self._transform_changed)
        selection_authoring.activeChanged.connect(self._authoring_changed)

    def _authoring_changed(self, active: bool) -> None:
        """Publish one selection-tool pointer transition."""

        self._publish(
            InputContextualToolbarGestureKind.SELECTION_AUTHORING,
            source_active=bool(active),
        )

    def _floating_changed(self, state: object) -> None:
        """Publish direct selected-pixel drag state from CuteCanvas."""

        floating = state if isinstance(state, FloatingPixelSnapshot) else None
        self._publish(
            InputContextualToolbarGestureKind.FLOATING_PIXELS,
            source_active=bool(floating is not None and floating.dragging),
            floating=floating,
        )

    def _transform_changed(self, state: object) -> None:
        """Publish direct affine gesture state from CuteCanvas."""

        if not isinstance(state, EditorTransformSnapshot):
            return
        self._publish(
            InputContextualToolbarGestureKind.TRANSFORM,
            source_active=state.gesture_active,
            transform=state,
        )

    def _publish(
        self,
        kind: InputContextualToolbarGestureKind,
        *,
        source_active: bool,
        floating: FloatingPixelSnapshot | None = None,
        transform: EditorTransformSnapshot | None = None,
    ) -> None:
        """Replace one source and emit its settlement with aggregate activity."""

        was_active = kind in self._active_sources
        if source_active:
            self._active_sources.add(kind)
        else:
            self._active_sources.discard(kind)
        self.changed.emit(
            InputContextualToolbarGestureUpdate(
                kind=kind,
                active=bool(self._active_sources),
                source_active=source_active,
                settled=was_active and not source_active,
                floating=floating,
                transform=transform,
            )
        )


__all__ = [
    "InputContextualToolbarGestureKind",
    "InputContextualToolbarGestureObserver",
    "InputContextualToolbarGestureUpdate",
]
