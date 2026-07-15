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

"""Qt-backed tests for workspace side-panel host geometry state."""

from __future__ import annotations

import importlib
import os
import sys
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "side-panel host Qt tests require non-xdist execution",
        allow_module_level=True,
    )


def _ensure_qapp() -> QApplication:
    """Return an application instance for side-panel host widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _clear_gui_stubs() -> None:
    """Remove lightweight Qt/qfluent stubs before importing real widgets."""

    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None and not hasattr(qtcore, "QCoreApplication"):
        for name in list(sys.modules):
            if name == "PySide6" or name.startswith("PySide6."):
                sys.modules.pop(name, None)
    qfw = sys.modules.get("qfluentwidgets")
    if qfw is not None and not hasattr(qfw, "ProgressBar"):
        for name in list(sys.modules):
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
                sys.modules.pop(name, None)


def test_side_panel_host_keeps_durable_width_separate_from_rendered_width() -> None:
    """Animated frame width should not replace the durable side-panel width."""

    app = _ensure_qapp()
    _clear_gui_stubs()
    module = importlib.import_module(
        "substitute.presentation.shell.main_window_workspace"
    )

    host = module.WorkspaceSidePanelHost()
    app.processEvents()

    assert host.is_queue_panel_visible() is False
    assert host.panel_width() == 360

    host.set_panel_width(100)

    assert host.panel_width() == 240

    host.begin_width_transition(target_visible=True)
    host.apply_width_transition(0)
    app.processEvents()

    assert host.is_queue_panel_visible() is True
    assert host.rendered_width() == 0
    assert host.panel_width() == 240

    host.finish_width_transition(visible=True)
    app.processEvents()

    assert host.is_queue_panel_visible() is True
    assert host.rendered_width() == 240
    assert host.panel_width() == 240

    host.begin_width_transition(target_visible=False)
    host.apply_width_transition(12)
    app.processEvents()

    assert host.is_queue_panel_visible() is True
    assert host.rendered_width() == 12
    assert host.panel_width() == 240

    host.finish_width_transition(visible=False)
    app.processEvents()

    assert host.is_queue_panel_visible() is False
    assert host.rendered_width() == 0
    assert host.panel_width() == 240

    host.close()
    host.deleteLater()
