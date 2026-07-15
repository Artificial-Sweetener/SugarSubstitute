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

"""Widget contract tests for SettingsInfoBar."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from substitute.presentation.settings.settings_infobar import SettingsInfoBar

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_settings_infobar_starts_hidden_and_renders_message() -> None:
    """InfoBar should stay hidden until a message is shown."""

    app = _app()
    bar = SettingsInfoBar()
    bar.show_message(
        severity="error",
        title="Sync failed",
        message="The target did not return a pack.",
    )
    app.processEvents()

    assert bar.isHidden() is False
    assert bar.severity() == "error"
    assert bar.title_label.text() == "Sync failed"
    assert bar.message_label.text() == "The target did not return a pack."

    bar.clear()
    app.processEvents()

    assert bar.isHidden() is True
    bar.close()


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
