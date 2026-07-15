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

"""Tests for the shared pending restart dialog."""

from __future__ import annotations

import os
from typing import cast

from PySide6.QtWidgets import QApplication
import pytest

from substitute.application.restart_requirements import (
    RestartRequirementItem,
    RestartRequirementSnapshot,
    RestartScope,
)
from substitute.presentation.dialogs.restart_required_dialog import (
    RestartRequiredDialog,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "dialog Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


def _app() -> QApplication:
    """Return the shared QApplication used by dialog tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_restart_required_dialog_renders_header_and_items() -> None:
    """Dialog should show restart copy and every pending item label."""

    _app()
    dialog = RestartRequiredDialog(snapshot=_snapshot())

    assert dialog.title_label.text() == "Restart required"
    assert dialog.body_label.text() == "These changes will apply after restart."
    assert dialog.item_labels() == ("Model folder", "Theme")
    assert len(dialog.item_rows) == 2

    dialog.close()


def test_restart_required_dialog_configures_actions() -> None:
    """Dialog should expose Restart now and Later actions."""

    _app()
    dialog = RestartRequiredDialog(snapshot=_snapshot())

    assert dialog.restart_now_button.text() == "Restart now"
    assert dialog.later_button.text() == "Later"

    dialog.close()


def test_restart_required_dialog_restart_now_accepts() -> None:
    """Restart now should resolve the dialog affirmatively."""

    _app()
    dialog = RestartRequiredDialog(snapshot=_snapshot())

    dialog.restart_now_button.click()

    assert dialog.restart_now_selected() is True

    dialog.close()


def test_restart_required_dialog_later_rejects() -> None:
    """Later should close the dialog without accepting restart intent."""

    _app()
    dialog = RestartRequiredDialog(snapshot=_snapshot())

    dialog.later_button.click()

    assert dialog.restart_now_selected() is False

    dialog.close()


def _snapshot() -> RestartRequirementSnapshot:
    """Build a snapshot with multiple pending restart items."""

    return RestartRequirementSnapshot(
        items=(
            RestartRequirementItem(
                key="comfy.model_root",
                label="Model folder",
                active_value="E:\\ImageGen Models",
                saved_value="F:\\Models",
                scope=RestartScope.FULL_APP,
                detail="ComfyUI will use the selected model folder after restart.",
            ),
            RestartRequirementItem(
                key="appearance.theme",
                label="Theme",
                active_value="Dark",
                saved_value="Light",
                scope=RestartScope.WINDOW,
            ),
        ),
        required_scope=RestartScope.FULL_APP,
    )
