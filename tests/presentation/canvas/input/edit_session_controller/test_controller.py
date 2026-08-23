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

"""Verify Sugar's focused owner for public CuteCanvas edit sessions."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QObject, Signal
from cutecanvas import (
    EditSessionKind,
    EditSessionPolicy,
    EditSessionSnapshot,
    EditSessionToolChange,
    EditSessionUndoBoundary,
)

from substitute.presentation.canvas.input.input_edit_session_controller import (
    InputEditSessionController,
)


class _SessionCanvas(QObject):
    """Implement the external session facade boundary for focused owner tests."""

    editSessionChanged = Signal(object)
    sceneEditHistoryChanged = Signal()

    def __init__(self) -> None:
        """Initialize detached state and command observations."""

        super().__init__()
        self.snapshot: EditSessionSnapshot | None = None
        self.policy: EditSessionPolicy | None = None
        self.calls: list[str] = []
        self.resolution_changed = True

    def activeEditSession(self) -> EditSessionSnapshot | None:
        """Return current detached session state."""

        return self.snapshot

    def setEditSessionPolicy(self, policy: EditSessionPolicy) -> bool:
        """Record the host-selected deterministic policy."""

        self.policy = policy
        return True

    def editorUndoAvailable(self) -> bool:
        """Return unified Undo availability."""

        return self.snapshot is not None and self.snapshot.can_undo

    def editorRedoAvailable(self) -> bool:
        """Return unified Redo availability."""

        return self.snapshot is not None and self.snapshot.can_redo

    def undoEditorEdit(self) -> bool:
        """Record one unified Undo request."""

        self.calls.append("undo")
        return True

    def redoEditorEdit(self) -> bool:
        """Record one unified Redo request."""

        self.calls.append("redo")
        return True

    def applyActiveEditSession(self) -> bool:
        """Record one session Apply request."""

        self.calls.append("apply")
        return True

    def cancelActiveEditSession(self) -> bool:
        """Record one session Cancel request."""

        self.calls.append("cancel")
        self.snapshot = None
        self.editSessionChanged.emit(None)
        return self.resolution_changed


def _snapshot(*, can_undo: bool = True, can_redo: bool = False) -> EditSessionSnapshot:
    """Return one settled shared-edge session snapshot."""

    return EditSessionSnapshot(
        session_id=uuid4(),
        kind=EditSessionKind.SHARED_EDGE_RESIZE,
        tool_mode="shared-edge-resize",
        gesture_active=False,
        can_apply=True,
        can_cancel=True,
        can_undo=can_undo,
        can_redo=can_redo,
        undo_label="Move Shared Edge",
        redo_label=None,
        undo_depth=1,
        redo_depth=0,
    )


def test_controller_configures_safe_policy_and_routes_session_commands() -> None:
    """Use one explicit bounded policy and the unified public command boundary."""

    canvas = _SessionCanvas()
    controller = InputEditSessionController(canvas, parent=canvas)
    expected = EditSessionPolicy(
        checkpoint_limit=256,
        undo_boundary=EditSessionUndoBoundary.SESSION_ONLY,
        tool_change=EditSessionToolChange.REQUIRE_RESOLUTION,
    )
    assert canvas.policy == expected

    canvas.snapshot = _snapshot()
    canvas.editSessionChanged.emit(canvas.snapshot)

    assert controller.snapshot == canvas.snapshot
    assert controller.can_undo
    assert not controller.can_redo
    assert controller.undo()
    assert controller.redo()
    assert controller.apply()
    assert controller.cancel()
    assert canvas.calls == ["undo", "redo", "apply", "cancel"]


def test_controller_close_cancels_only_an_unresolved_session() -> None:
    """Teardown should restore provisional state without touching durable history."""

    canvas = _SessionCanvas()
    controller = InputEditSessionController(canvas, parent=canvas)

    assert not controller.close()
    canvas.snapshot = _snapshot()
    canvas.editSessionChanged.emit(canvas.snapshot)
    assert controller.close()
    assert controller.snapshot is None
    assert canvas.calls == ["cancel"]


def test_no_change_cancel_still_reports_success_when_it_closes_the_session() -> None:
    """Resolution success must not depend on whether base restoration changed pixels."""

    canvas = _SessionCanvas()
    canvas.snapshot = _snapshot(can_undo=False)
    canvas.resolution_changed = False
    controller = InputEditSessionController(canvas, parent=canvas)

    assert controller.cancel()
    assert controller.snapshot is None
