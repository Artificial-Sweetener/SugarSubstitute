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

"""Test authoritative external prompt-text input behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QMimeData, QPoint, QUrl

from substitute.presentation.editor.prompt_editor.interactions.external_text_input import (
    PromptExternalTextInputOwner,
)


@dataclass
class _MimeEvent:
    """Record acceptance state for one controller-facing MIME event."""

    mime_data: QMimeData
    accepted: bool = False
    ignored: bool = False

    def mimeData(self) -> QMimeData:  # noqa: N802
        """Return the configured payload."""
        return self.mime_data

    def acceptProposedAction(self) -> None:  # noqa: N802
        """Record proposed-action acceptance."""
        self.accepted = True

    def ignore(self) -> None:
        """Record event rejection."""
        self.ignored = True


@dataclass
class _InsertionRecorder:
    """Record external-text insertion requests."""

    requests: list[tuple[str, str, QPoint | None]] = field(default_factory=list)

    def __call__(
        self,
        text: str,
        *,
        command_name: str,
        viewport_position: QPoint | None,
    ) -> None:
        """Record one accepted insertion request."""
        self.requests.append((text, command_name, viewport_position))


def _plain_text(value: str) -> QMimeData:
    """Build one plain-text MIME payload."""
    mime_data = QMimeData()
    mime_data.setText(value)
    return mime_data


def test_owner_inserts_non_positional_mime_text_with_stable_command_identity() -> None:
    """Direct MIME insertion should preserve its source-command identity."""
    insertion = _InsertionRecorder()
    owner = PromptExternalTextInputOwner(insertion)

    assert owner.insert(_plain_text("red dress"))
    assert insertion.requests == [("red dress", "mime_plain_text", None)]


def test_owner_accepts_plain_text_drop_at_projection_viewport_position() -> None:
    """A safe drop should commit at the supplied projection position."""
    insertion = _InsertionRecorder()
    owner = PromptExternalTextInputOwner(insertion)
    event = _MimeEvent(_plain_text("blue eyes"))
    position = QPoint(17, 29)

    assert owner.accept_or_ignore_drag(event)
    assert event.accepted
    assert not event.ignored
    event.accepted = False

    assert owner.drop(event, viewport_position=position)
    assert event.accepted
    assert insertion.requests == [("blue eyes", "drop_plain_text", position)]


def test_owner_rejects_file_drop_without_mutating_prompt_source() -> None:
    """A file-backed text payload should stay rejected through drag and drop."""
    insertion = _InsertionRecorder()
    owner = PromptExternalTextInputOwner(insertion)
    mime_data = _plain_text("E:/output/image.png")
    mime_data.setUrls([QUrl.fromLocalFile("E:/output/image.png")])
    event = _MimeEvent(mime_data)

    assert not owner.accept_or_ignore_drag(event)
    assert event.ignored
    event.ignored = False

    assert not owner.drop(event, viewport_position=QPoint(3, 5))
    assert event.ignored
    assert insertion.requests == []
