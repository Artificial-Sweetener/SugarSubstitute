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

"""Prove installer feedback advances while its producer remains blocked."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from launcher.sugarsubstitute_launcher.ui.installation_activity_presenter import (
    InstallationActivityPresenter,
)
from tests.launcher.support import launcher_test_application


def test_installation_activity_reports_operation_and_elapsed_heartbeat() -> None:
    """Advance visible elapsed time without invented completion progress."""

    application = launcher_test_application()
    elapsed = 10.0
    label = QLabel()
    presenter = InstallationActivityPresenter(
        label=label,
        parent=label,
        clock=lambda: elapsed,
    )

    presenter.start("Fetching SugarCubes")
    assert label.text() == "Fetching SugarCubes — 0:00 elapsed"

    elapsed = 160.0
    presenter.refresh()
    assert label.text() == "Fetching SugarCubes — 2:30 elapsed"

    presenter.stop()
    elapsed = 220.0
    presenter.refresh()
    assert label.text() == "Fetching SugarCubes — 2:30 elapsed"
    label.deleteLater()
    application.processEvents()
