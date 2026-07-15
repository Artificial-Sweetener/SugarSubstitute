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

"""Tests for the shutdown recovery dialog contract."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.shutdown_recovery_dialog import (
    ShutdownRecoveryDialog,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "shutdown recovery dialog contract tests require non-xdist execution",
        allow_module_level=True,
    )


def test_shutdown_recovery_dialog_uncertain_copy_matches_specification() -> None:
    """The uncertain shutdown copy should match the required UX contract."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownRecoveryDialog()

    dialog.show_uncertain_outcome(
        "Shutdown could not be confirmed before the verification timeout."
    )

    assert dialog.windowTitle() == "Could Not Finish Closing"
    assert (
        dialog.primary_label.text()
        == "Substitute could not confirm that shutdown finished."
    )
    assert (
        dialog.secondary_label.text()
        == "You can retry shutdown or close Substitute anyway."
    )

    dialog.allow_close()
    dialog.close()
    app.processEvents()


def test_shutdown_recovery_dialog_failure_copy_matches_specification() -> None:
    """The failed shutdown copy should match the required UX contract."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownRecoveryDialog()

    dialog.show_failed_outcome("The termination command timed out before completion.")

    assert (
        dialog.primary_label.text() == "Substitute could not finish closing completely."
    )
    assert (
        dialog.secondary_label.text()
        == "You can retry shutdown or close Substitute anyway."
    )

    dialog.allow_close()
    dialog.close()
    app.processEvents()


def test_shutdown_recovery_dialog_retry_is_default_button() -> None:
    """Retry should remain the default focused action."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownRecoveryDialog()

    assert dialog.retry_button.isDefault() is True

    dialog.allow_close()
    dialog.close()
    app.processEvents()


def test_shutdown_recovery_dialog_blocks_close_button_and_escape() -> None:
    """The dialog should stay open until the coordinator handles an explicit action."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownRecoveryDialog()
    dialog.show_failed_outcome("The termination command timed out before completion.")
    dialog.show()
    app.processEvents()

    assert dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint == 0

    dialog.close()
    app.processEvents()
    assert dialog.isVisible() is True

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    app.processEvents()
    assert dialog.isVisible() is True

    dialog.allow_close()
    dialog.close()
    app.processEvents()
    assert dialog.isVisible() is False


def test_shutdown_recovery_dialog_hides_details_by_default() -> None:
    """Diagnostic details should stay hidden until the user explicitly reveals them."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownRecoveryDialog()
    dialog.show_uncertain_outcome(
        "Shutdown could not be confirmed before the verification timeout."
    )

    assert dialog.details_label.isHidden() is True
    assert dialog.details_toggle_button.text() == "Show Details"

    dialog.allow_close()
    dialog.close()
    app.processEvents()


def test_shutdown_recovery_dialog_details_show_sanitized_text_only() -> None:
    """The details region should show only the sanitized detail passed to the dialog."""

    app = QApplication.instance() or QApplication([])
    dialog = ShutdownRecoveryDialog()
    detail_text = "Shutdown could not be confirmed before the verification timeout."
    dialog.show_uncertain_outcome(detail_text)
    dialog.show()
    app.processEvents()

    dialog.details_toggle_button.click()
    app.processEvents()

    assert dialog.details_label.isVisible() is True
    assert dialog.details_label.text() == detail_text
    assert "SUCCESS:" not in dialog.details_label.text()
    assert "taskkill" not in dialog.details_label.text().lower()

    dialog.allow_close()
    dialog.close()
