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

"""Verify editable Input document revision signal projection."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.canvas.input.input_editable_document_change_tracker import (
    InputEditableDocumentChangeTracker,
)


class _Signal:
    """Expose deterministic signal connection and emission."""

    def __init__(self) -> None:
        """Initialize without a listener."""

        self._callback: Callable[..., object] | None = None

    def connect(self, callback: Callable[..., object]) -> object:
        """Retain the supplied listener."""

        self._callback = callback
        return object()

    def emit(self, *args: object) -> None:
        """Publish one configured signal emission."""

        assert self._callback is not None
        self._callback(*args)


def test_each_durable_signal_advances_the_document_revision() -> None:
    """Project composition, mask, and scene-mapping edits to one owner."""

    signals = (_Signal(), _Signal(), _Signal())
    revisions: list[str] = []
    tracker = InputEditableDocumentChangeTracker(
        changes=signals,
        mark_changed=lambda: revisions.append("changed"),
    )

    signals[0].emit()
    signals[1].emit(object())
    signals[2].emit("mapping")

    assert tracker is not None
    assert revisions == ["changed", "changed", "changed"]
