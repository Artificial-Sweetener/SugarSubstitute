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

"""Exercise startup report visibility and dismissal through the real Qt host."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog
from shiboken6 import delete

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.presentation.errors import present_startup_failure_report
from sugarsubstitute_shared.presentation.error_report_view import SharedErrorReportView


@pytest.mark.parametrize("dismissal", ["button", "window"])
def test_startup_report_dismissal_releases_modal_lifetime(dismissal: str) -> None:
    """Return from startup failure after either report or native window close."""
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication([])
    initial_widgets = set(app.allWidgets())
    observation: dict[str, bool] = {}
    timer = QTimer()
    timer.setInterval(1)
    deadline = QTimer()
    deadline.setSingleShot(True)

    def dismiss_visible_report() -> None:
        """Dismiss only after the real report and its Close action are visible."""
        views = [
            widget
            for widget in app.allWidgets()
            if widget not in initial_widgets
            and isinstance(widget, SharedErrorReportView)
            and widget.isVisible()
        ]
        if not views:
            return
        view = views[0]
        buttons = [
            button
            for button in view.findChildren(QAbstractButton)
            if button.text() == "Close" and button.isVisible() and button.isEnabled()
        ]
        if not buttons:
            return
        timer.stop()
        host = view.window()
        observation["visible"] = host.isVisible()
        observation["tool_window"] = host.windowType() == Qt.WindowType.Tool
        if dismissal == "window":
            host.close()
        else:
            buttons[0].click()

    def interrupt_stuck_modal() -> None:
        """Bound a failed close without leaving a nested modal event loop behind."""
        observation["deadline_expired"] = True
        for widget in app.allWidgets():
            if widget not in initial_widgets and isinstance(widget, QDialog):
                widget.reject()

    timer.timeout.connect(dismiss_visible_report)
    deadline.timeout.connect(interrupt_stuck_modal)
    try:
        timer.start()
        deadline.start(3000)
        present_startup_failure_report(
            ErrorReport(
                kind=ErrorReportKind.COMFY_CONNECTION,
                title="ComfyUI failed to start",
                message="Synthetic backend startup failure.",
                stage="managed_startup",
            )
        )
    finally:
        timer.stop()
        deadline.stop()
        delete(timer)
        delete(deadline)
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert observation.get("visible") is True
    assert observation.get("tool_window") is False
    assert not observation.get("deadline_expired"), (
        "Closing the report stranded its modal loop"
    )
    assert not any(
        widget not in initial_widgets
        and isinstance(widget, SharedErrorReportView)
        and widget.isVisible()
        for widget in app.allWidgets()
    )
