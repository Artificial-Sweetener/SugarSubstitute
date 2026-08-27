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

"""Tests for the shutdown progress dialog contract."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from substitute.presentation.shell.shutdown_progress_dialog import (
    ShutdownProgressDialog,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


@pytest.fixture()
def shutdown_progress_dialog() -> Iterator[ShutdownProgressDialog]:
    """Create one dialog with explicit application and teardown ownership."""

    application = ensure_qt_application()
    dialog = ShutdownProgressDialog()
    yield dialog
    destroy_qt_object(dialog)
    del application


def test_shutdown_progress_dialog_matches_required_copy(
    shutdown_progress_dialog: ShutdownProgressDialog,
) -> None:
    """The dialog should expose only the fixed in-progress shutdown copy."""

    dialog = shutdown_progress_dialog

    assert dialog.windowTitle() == "Closing Substitute"
    assert dialog.headline_label.text() == "Closing Substitute..."
    assert dialog.body_label.text() == "Please wait a moment."
    assert dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint == 0
    assert dialog.isModal() is True


def test_shutdown_progress_dialog_has_no_failure_state_api(
    shutdown_progress_dialog: ShutdownProgressDialog,
) -> None:
    """The dialog should not expose any failure or detail mutation surface."""

    dialog = shutdown_progress_dialog

    assert hasattr(dialog, "show_failure_state") is False
    assert hasattr(dialog, "set_detail_text") is False


def test_shutdown_progress_dialog_blocks_close_until_allowed(
    shutdown_progress_dialog: ShutdownProgressDialog,
) -> None:
    """The dialog should stay open until the coordinator explicitly allows close."""

    dialog = shutdown_progress_dialog
    dialog.show()
    assert dialog.isVisible() is True

    dialog.close()
    assert dialog.isVisible() is True

    dialog.allow_close()
    dialog.close()
    assert dialog.isVisible() is False


def test_shutdown_progress_dialog_blocks_escape_until_allowed(
    shutdown_progress_dialog: ShutdownProgressDialog,
) -> None:
    """Ignore Escape while shutdown is active and honor it after completion."""

    dialog = shutdown_progress_dialog
    dialog.show()

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.isVisible() is True

    dialog.allow_close()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.isVisible() is False
