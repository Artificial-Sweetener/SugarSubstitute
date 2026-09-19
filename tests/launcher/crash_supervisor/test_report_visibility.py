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

"""Verify crash presentation without an existing application window."""

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QDialog
from shiboken6 import delete, isValid

from launcher.sugarsubstitute_launcher import crash_report_application
from launcher.sugarsubstitute_launcher.crash_report_application import (
    run_crash_report_application,
)
from sugarsubstitute_shared.crash_reporting.presentation import (
    build_crash_report_presentation,
)
from sugarsubstitute_shared.presentation.error_report_window import (
    SharedErrorReportWindow,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_protocol import (
    BROKER_ENDPOINT_ENV,
    BROKER_TOKEN_ENV,
)
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)


def test_complete_crash_report_embeds_sanitized_text_attachments(
    tmp_path: Path,
) -> None:
    """The clipboard report should carry readable logs without binary dump content."""

    layout = InstallLayout.from_root(tmp_path / "install")
    incident = CrashIncident(
        incident_id="complete-report",
        run_id="complete-report",
        occurred_at_utc="2026-09-19T02:00:00+00:00",
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="Synthetic interruption",
        process_id=42,
        attachments=("python-fault.log", "native.dmp"),
    )
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    directory = store.record(incident)
    (directory / "python-fault.log").write_text(
        f"frame below {layout.root} api_key=private-value\n"
        f"{'x' * 131_072}retained-tail",
        encoding="utf-8",
    )
    (directory / "native.dmp").write_bytes(b"binary dump content")

    presentation = crash_report_application._build_complete_crash_report(
        layout,
        incident,
    )

    assert "[python-fault.log]" in presentation.report_text
    assert "frame below <install-root> api_key=<redacted>" in (presentation.report_text)
    assert "private-value" not in presentation.report_text
    assert "retained-tail" in presentation.report_text
    assert "binary dump content" not in presentation.report_text


@pytest.mark.parametrize("continue_launch", [False, True])
@pytest.mark.parametrize("restart_requested", [False, True])
def test_crash_report_presents_a_visible_standalone_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    continue_launch: bool,
    restart_requested: bool,
) -> None:
    """A report with no surviving app frame must still be visible and dismissible."""

    monkeypatch.delenv(BROKER_ENDPOINT_ENV, raising=False)
    monkeypatch.delenv(BROKER_TOKEN_ENV, raising=False)
    application = QApplication.instance() or QApplication([])
    assert isinstance(application, QApplication)
    initial_widgets = set(application.allWidgets())
    layout = InstallLayout.from_root(tmp_path / "install")
    incident = CrashIncident(
        incident_id="visible-report",
        run_id="visible-report",
        occurred_at_utc="2026-09-15T02:00:00+00:00",
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="Synthetic interruption",
        process_id=42,
    )
    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    store.record(incident)
    observations: list[bool] = []
    restart_calls: list[bool] = []

    def request_supervised_restart() -> bool:
        """Observe the external broker request after durable acknowledgement."""

        restart_calls.append(store.pending() == ())
        return True

    monkeypatch.setattr(
        crash_report_application,
        "request_supervised_application_restart",
        request_supervised_restart,
    )

    def inspect_and_dismiss() -> None:
        """Observe the entered report event loop and dismiss its owned dialogs."""

        observations.append(
            any(
                widget.isVisible() and widget not in initial_widgets
                for widget in application.topLevelWidgets()
            )
        )
        for widget in application.allWidgets():
            if widget not in initial_widgets and isinstance(widget, QDialog):
                if isinstance(widget, SharedErrorReportWindow) and restart_requested:
                    assert widget.content._restart_button is not None
                    widget.content._restart_button.click()
                else:
                    widget.accept()

    QTimer.singleShot(0, inspect_and_dismiss)
    try:
        assert (
            run_crash_report_application(
                layout=layout,
                incident_id=incident.incident_id,
                locale_override="en",
                continue_launch=continue_launch,
            )
            == 0
        )
        assert observations == [True]
        assert restart_calls == (
            [True] if restart_requested and not continue_launch else []
        )
        assert store.pending() == ()
    finally:
        for widget in application.topLevelWidgets():
            if widget not in initial_widgets and isValid(widget):
                widget.close()
                delete(widget)


def test_expanding_standalone_report_keeps_actions_on_screen() -> None:
    """Details growth near a screen edge must preserve visible recovery actions."""

    application = QApplication.instance() or QApplication([])
    assert isinstance(application, QApplication)
    incident = CrashIncident(
        incident_id="report-expansion",
        run_id="report-expansion",
        occurred_at_utc="2026-09-15T02:00:00+00:00",
        kind=CrashKind.PYTHON_UNHANDLED,
        boundary=CrashBoundary.PROCESS_MAIN,
        attribution=CrashAttribution.CONFIRMED,
        summary="Synthetic interruption",
        process_id=42,
    )
    window = SharedErrorReportWindow(
        presentation=build_crash_report_presentation(incident), restart=lambda: None
    )
    try:
        window.show()
        available = window.screen().availableGeometry()
        window.move(available.left(), available.bottom() - window.height() + 1)
        expanded = QSignalSpy(window.content._body_height_animation.finished)
        window.content._details_button.click()
        assert expanded.count() or expanded.wait(1000)
        assert available.contains(window.geometry())
        assert window.content.rect().contains(window.content._footer.geometry())
    finally:
        window.close()
        delete(window)
