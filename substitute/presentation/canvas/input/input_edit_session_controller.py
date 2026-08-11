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

"""Own Sugar's public CuteCanvas edit-session subscription and commands."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QObject, Signal, SignalInstance
from cutecanvas import (
    EditSessionPolicy,
    EditSessionSnapshot,
    EditSessionToolChange,
    EditSessionUndoBoundary,
)

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_edit_session_controller")
_INPUT_EDIT_SESSION_POLICY = EditSessionPolicy(
    checkpoint_limit=256,
    undo_boundary=EditSessionUndoBoundary.SESSION_ONLY,
    tool_change=EditSessionToolChange.REQUIRE_RESOLUTION,
)


class InputEditSessionCanvasPort(Protocol):
    """Describe the supported CuteCanvas session facade consumed by Sugar."""

    editSessionChanged: SignalInstance
    sceneEditHistoryChanged: SignalInstance

    def activeEditSession(self) -> EditSessionSnapshot | None:
        """Return detached state for the unresolved session, if any."""

    def setEditSessionPolicy(self, policy: EditSessionPolicy) -> bool:
        """Configure deterministic host-selected session behavior."""

    def editorUndoAvailable(self) -> bool:
        """Return whether unified editor Undo can act now."""

    def editorRedoAvailable(self) -> bool:
        """Return whether unified editor Redo can act now."""

    def undoEditorEdit(self) -> bool:
        """Undo provisional history before durable document history."""

    def redoEditorEdit(self) -> bool:
        """Redo provisional history before durable document history."""

    def applyActiveEditSession(self) -> bool:
        """Commit the active provisional result as one durable edit."""

    def cancelActiveEditSession(self) -> bool:
        """Restore the active session's immutable base and close it."""


class InputEditSessionController(QObject):
    """Project one authoritative CuteCanvas session into Sugar-owned commands."""

    changed = Signal(object)

    def __init__(
        self,
        canvas: InputEditSessionCanvasPort,
        *,
        parent: QObject | None = None,
    ) -> None:
        """Configure the Input policy and observe both history boundaries."""

        super().__init__(parent)
        self._canvas = canvas
        self._snapshot = canvas.activeEditSession()
        if not canvas.setEditSessionPolicy(_INPUT_EDIT_SESSION_POLICY):
            log_warning(
                _LOGGER,
                "Input edit-session policy could not be configured",
                active_session=self._snapshot is not None,
            )
        canvas.editSessionChanged.connect(self.refresh)
        canvas.sceneEditHistoryChanged.connect(self.refresh)

    @property
    def snapshot(self) -> EditSessionSnapshot | None:
        """Return the latest detached public session state."""

        return self._snapshot

    @property
    def can_undo(self) -> bool:
        """Return unified Undo availability at the current history boundary."""

        return bool(self._canvas.editorUndoAvailable())

    @property
    def can_redo(self) -> bool:
        """Return unified Redo availability at the current history boundary."""

        return bool(self._canvas.editorRedoAvailable())

    def refresh(self, *_args: object) -> None:
        """Publish current state after either history boundary changes."""

        self._snapshot = self._canvas.activeEditSession()
        self.changed.emit(self._snapshot)

    def undo(self) -> bool:
        """Route Undo through CuteCanvas's unified history owner."""

        return bool(self._canvas.undoEditorEdit())

    def redo(self) -> bool:
        """Route Redo through CuteCanvas's unified history owner."""

        return bool(self._canvas.redoEditorEdit())

    def apply(self) -> bool:
        """Apply the complete active provisional session."""

        if self._snapshot is None:
            return False
        changed = bool(self._canvas.applyActiveEditSession())
        return changed or self._canvas.activeEditSession() is None

    def cancel(self) -> bool:
        """Cancel the complete active provisional session."""

        if self._snapshot is None:
            return False
        changed = bool(self._canvas.cancelActiveEditSession())
        return changed or self._canvas.activeEditSession() is None

    def close(self) -> bool:
        """Cancel unresolved provisional state before Input teardown."""

        if self._snapshot is None:
            return False
        return self.cancel()


__all__ = ["InputEditSessionCanvasPort", "InputEditSessionController"]
