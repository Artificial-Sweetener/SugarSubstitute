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

"""Verify mounted shell adaptation of external prompt text."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import QDropEvent

from substitute.presentation.editor.prompt_editor.external_input_facade import (
    PromptEditorExternalInputBindings,
    PromptEditorExternalInputFacade,
)


@dataclass(slots=True)
class _ExternalInputRecorder:
    """Record mounted cursor, insertion, and completion effects."""

    drop_position: QPoint = field(default_factory=lambda: QPoint(19, 31))
    calls: list[object] = field(default_factory=list)

    def set_cursor(self, position: QPoint) -> None:
        """Record one positional cursor update."""

        self.calls.append(("cursor", position))

    def insert_text(self, text: str, command_name: str) -> None:
        """Record one source insertion."""

        self.calls.append(("insert", text, command_name))

    def complete_paste(self, command_name: str) -> None:
        """Record paste completion publication."""

        self.calls.append(("complete", command_name))

    def position_for_drop(self, _event: QDropEvent) -> QPoint:
        """Return the configured projection-viewport position."""

        return self.drop_position


def test_non_positional_mime_insert_commits_before_completion() -> None:
    """Host MIME insertion preserves source-command and completion ordering."""

    recorder = _ExternalInputRecorder()
    facade = _facade(recorder)
    source = QMimeData()
    source.setText("red dress")

    facade.insert(source)

    assert recorder.calls == [
        ("insert", "red dress", "mime_plain_text"),
        ("complete", "mime_plain_text"),
    ]


def test_drop_moves_caret_before_insertion_and_completion() -> None:
    """Host drops translate coordinates before committing one edit transaction."""

    recorder = _ExternalInputRecorder()
    facade = _facade(recorder)
    source = QMimeData()
    source.setText("blue eyes")
    event = QDropEvent(
        QPointF(7, 11),
        Qt.DropAction.CopyAction,
        source,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    facade.drop(event)

    assert event.isAccepted()
    assert recorder.calls == [
        ("cursor", QPoint(19, 31)),
        ("insert", "blue eyes", "drop_plain_text"),
        ("complete", "drop_plain_text"),
    ]


def _facade(recorder: _ExternalInputRecorder) -> PromptEditorExternalInputFacade:
    """Bind one recorder to the production shell external-input facade."""

    return PromptEditorExternalInputFacade(
        PromptEditorExternalInputBindings(
            set_cursor_at_viewport_position=recorder.set_cursor,
            insert_external_text=recorder.insert_text,
            complete_paste=recorder.complete_paste,
            viewport_position_for_drop=recorder.position_for_drop,
        )
    )
