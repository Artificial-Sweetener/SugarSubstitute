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

"""Verify deterministic Qt teardown for canvas-owned global input hooks."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication
import pytest
from shiboken6 import isValid

from tests.support.qt import lifecycle


class _RecordingInteraction:
    """Record the pre-destruction hook released by canvas cleanup."""

    def __init__(self, owner: QObject) -> None:
        """Retain the canvas validity boundary observed during shutdown."""

        self._owner = owner
        self.was_valid_during_shutdown = False

    def shutdown(self) -> None:
        """Record that the canvas remains valid while its hook is removed."""

        self.was_valid_during_shutdown = isValid(self._owner)


class _FakeCanvas(QObject):
    """Expose the exact interaction owner required by canvas teardown."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Create one canvas stand-in with a recording interaction."""

        super().__init__(parent)
        self.interaction = _RecordingInteraction(self)


def test_ensure_qt_application_returns_the_process_owned_application(
    qt_application_owner: QApplication,
) -> None:
    """Reuse only the worker-local application identity across Qt test setup."""

    assert lifecycle.ensure_qt_application() is qt_application_owner


def test_destroy_qt_object_detaches_descendant_canvas_input_before_deletion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release application-wide focus observation while the canvas is still valid."""

    monkeypatch.setattr(lifecycle, "CuteCanvas", _FakeCanvas)
    root = QObject()
    canvas = _FakeCanvas(root)

    lifecycle.destroy_qt_object(root)

    assert canvas.interaction.was_valid_during_shutdown
