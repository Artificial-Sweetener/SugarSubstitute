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

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.shutdown_progress_dialog import (
    ShutdownProgressDialog,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "shutdown progress dialog contract tests require non-xdist execution",
        allow_module_level=True,
    )


def test_shutdown_progress_dialog_matches_required_copy() -> None:
    """The dialog should expose only the fixed in-progress shutdown copy."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownProgressDialog()

    assert dialog.windowTitle() == "Closing Substitute"
    assert dialog.headline_label.text() == "Closing Substitute..."
    assert dialog.body_label.text() == "Please wait a moment."
    assert dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint == 0

    dialog.allow_close()
    dialog.close()
    app.processEvents()


def test_shutdown_progress_dialog_has_no_failure_state_api() -> None:
    """The dialog should not expose any failure or detail mutation surface."""

    dialog = ShutdownProgressDialog()

    assert hasattr(dialog, "show_failure_state") is False
    assert hasattr(dialog, "set_detail_text") is False

    dialog.allow_close()
    dialog.close()


def test_shutdown_progress_dialog_blocks_close_until_allowed() -> None:
    """The dialog should stay open until the coordinator explicitly allows close."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownProgressDialog()
    dialog.show()
    app.processEvents()

    dialog.close()
    app.processEvents()
    assert dialog.isVisible() is True

    dialog.allow_close()
    dialog.close()
    app.processEvents()
    assert dialog.isVisible() is False
