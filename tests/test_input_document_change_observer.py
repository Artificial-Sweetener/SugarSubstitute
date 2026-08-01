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

"""Prove Input edits autosave document authority without flattened mask writes."""

from collections.abc import Callable

from substitute.presentation.canvas.input.input_document_change_observer import (
    InputDocumentChangeObserver,
)


class _Signal:
    """Provide one deterministic Qt-like signal."""

    def __init__(self) -> None:
        """Initialize without subscribers."""
        self._callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> object:
        """Register one subscriber."""
        self._callbacks.append(callback)
        return None

    def emit(self, *args: object) -> None:
        """Deliver one change synchronously."""
        for callback in tuple(self._callbacks):
            callback(*args)


def test_document_edits_mark_active_workflow_and_request_archive_autosave() -> None:
    """Each durable edit must route to the complete-document persistence barrier."""
    changed = _Signal()
    invalidated: list[str] = []
    autosaves: list[None] = []
    observer = InputDocumentChangeObserver(
        changed=changed,
        active_workflow_id=lambda: "workflow-a",
        mark_workflow_changed=invalidated.append,
        request_autosave=lambda: autosaves.append(None),
    )

    for revision in range(100):
        changed.emit("mask-a", revision)

    assert observer is not None
    assert invalidated == ["workflow-a"] * 100
    assert autosaves == [None] * 100


def test_document_edit_without_active_workflow_still_saves_shared_document() -> None:
    """Document authority survives transient workflow deactivation."""
    changed = _Signal()
    invalidated: list[str] = []
    autosaves: list[None] = []
    InputDocumentChangeObserver(
        changed=changed,
        active_workflow_id=lambda: "",
        mark_workflow_changed=invalidated.append,
        request_autosave=lambda: autosaves.append(None),
    )

    changed.emit()

    assert invalidated == []
    assert autosaves == [None]
