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

"""Widget contract tests for the qfluent error report dialog."""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from qfluentwidgets import PrimaryPushButton  # type: ignore[import-untyped]

from substitute.application.errors import (
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
    SubstituteOperationContext,
)
from substitute.presentation.dialogs.error_report_dialog import (
    ErrorReportDialog,
    ReportSeverityGlyphWidget,
)


def _app() -> QApplication:
    """Return a QApplication for widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_error_report_dialog_renders_summary_and_full_report() -> None:
    """Dialog should show a compact summary and keep the full report available."""

    app = _app()
    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="CUDA out of memory",
        stage="listen",
        workflow_id="wf-1",
        prompt_id="pid-1",
        exception_type="RuntimeError",
    )
    dialog = ErrorReportDialog(
        report=report,
        report_text="Traceback line 1\nTraceback line 2",
    )

    try:
        assert dialog._title_label.text() == "KSampler failed"
        assert isinstance(dialog._icon_widget, ReportSeverityGlyphWidget)
        title_metrics = dialog._title_label.fontMetrics()
        title_rect = title_metrics.tightBoundingRect(dialog._title_label.text())
        title_top = title_metrics.ascent() + title_rect.top()
        title_bottom = title_top + title_rect.height()
        message_metrics = dialog._message_label.fontMetrics()
        message_rect = message_metrics.tightBoundingRect(dialog._message_label.text())
        message_label_top = title_metrics.height() + 4
        message_top = message_label_top + message_metrics.ascent() + message_rect.top()
        message_bottom = message_top + message_rect.height()
        expected_icon_size = max(
            16,
            max(title_bottom, message_bottom) - min(title_top, message_top) - 1,
        )
        assert dialog._icon_widget.size().width() == expected_icon_size
        assert dialog._icon_widget.size().height() == expected_icon_size
        assert dialog._icon_widget.icon_path().endswith("Error_light.svg")
        assert dialog._message_label.minimumWidth() == (
            720 - (24 * 2) - expected_icon_size - 12
        )
        assert (
            dialog._message_label.height()
            >= dialog._message_label.fontMetrics().height()
        )
        assert dialog.yesButton.isHidden()
        assert dialog._close_button.text() == "Close"
        assert isinstance(dialog._close_button, PrimaryPushButton)
        assert dialog._close_button.icon().isNull()
        assert dialog._copy_button.icon().isNull()
        assert dialog.viewLayout.spacing() == 0
        assert dialog._body_layout.spacing() == 12
        assert "Traceback line 1" in dialog._report_editor.toPlainText()
        assert dialog._report_editor.isHidden()

        dialog._toggle_details()

        assert not dialog._report_editor.isHidden()
        assert dialog._details_button.text() == "Hide report"
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_error_report_dialog_uses_warning_presentation_for_warning_reports() -> None:
    """Warning reports should keep the modal shell but use warning presentation."""

    app = _app()
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.CUBE_LIBRARY_DRIFT,
            severity=DiagnosticSeverity.WARNING,
            title="Cube Library Notice",
            message="The recipe loaded with Cube Library warnings.",
            stage="load_recipe",
            workflow_id="wf-1",
            operation_context=SubstituteOperationContext(
                operation="load_recipe_cube_library_drift",
                values={"message_count": 3},
            ),
        ),
        report_text="Cube Library warnings\nCube 'CubeA' changed.",
    )

    try:
        summary_text = {
            label.text()
            for label in dialog._summary_frame.findChildren(QLabel)
            if label.text()
        }

        assert dialog._icon_widget.icon_path().endswith("Warning_light.svg")
        assert "Affected cubes" in summary_text
        assert "3" in summary_text
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_error_report_dialog_wraps_long_header_message() -> None:
    """Long report messages should wrap instead of being clipped to one line."""

    app = _app()
    long_message = (
        "This diagnostic message is intentionally long enough to require wrapping "
        "inside the fixed-width modal header instead of being cut off."
    )
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
            title="Long diagnostic",
            message=long_message,
            stage="test",
        ),
        report_text="report",
    )

    try:
        line_height = dialog._message_label.fontMetrics().height()

        assert dialog._message_label.wordWrap()
        assert dialog._message_label.height() > line_height
        assert dialog._message_label.sizeHint().height() > line_height
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_error_report_dialog_constrains_body_under_height_pressure() -> None:
    """Dialog body should scroll instead of forcing the modal beyond its parent."""

    app = _app()
    parent = QWidget()
    parent.resize(720, 360)
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.EXECUTION,
            title="KSampler failed",
            message="CUDA out of memory",
            stage="listen",
        ),
        report_text="\n".join(f"Traceback line {index}" for index in range(80)),
        parent=parent,
    )

    try:
        assert dialog.widget.maximumHeight() == 312
        assert dialog._body_scroll_area.widgetResizable()
        assert dialog._report_editor.minimumHeight() == 160

        dialog._toggle_details()
        dialog.show()
        app.processEvents()

        assert dialog.widget.height() <= dialog.widget.maximumHeight()
    finally:
        dialog.close()
        parent.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_error_report_dialog_recenters_after_report_expansion() -> None:
    """Expanded report content should keep the modal centered in the mask."""

    app = _app()
    parent = QWidget()
    parent.resize(1024, 768)
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.EXECUTION,
            title="KSampler failed",
            message="CUDA out of memory",
            stage="listen",
        ),
        report_text="\n".join(f"Traceback line {index}" for index in range(80)),
        parent=parent,
    )

    try:
        dialog.show()
        app.processEvents()

        dialog._toggle_details()
        app.processEvents()

        assert dialog.size() == parent.size()
        assert dialog.widget.pos().x() == (dialog.width() - dialog.widget.width()) // 2
        assert (
            dialog.widget.pos().y() == (dialog.height() - dialog.widget.height()) // 2
        )
    finally:
        dialog.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_error_report_dialog_animates_report_show_and_hide() -> None:
    """Report disclosure should animate height and hide details after collapse."""

    app = _app()
    previous_reduced_motion = app.property("substitute.reduce_motion")
    app.setProperty("substitute.reduce_motion", False)
    parent = QWidget()
    parent.resize(1024, 768)
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.EXECUTION,
            title="KSampler failed",
            message="CUDA out of memory",
            stage="listen",
        ),
        report_text="\n".join(f"Traceback line {index}" for index in range(80)),
        parent=parent,
    )

    try:
        dialog.show()
        app.processEvents()
        collapsed_height = dialog._body_scroll_area.height()

        dialog._toggle_details()
        app.processEvents()

        assert not dialog._report_editor.isHidden()
        assert dialog._body_height_animation.state() == QAbstractAnimation.State.Running

        QTest.qWait(dialog._body_height_animation.duration() + 40)
        app.processEvents()
        expanded_height = dialog._body_scroll_area.height()
        assert expanded_height > collapsed_height

        dialog._toggle_details()
        app.processEvents()

        assert not dialog._report_editor.isHidden()
        assert dialog._body_height_animation.state() == QAbstractAnimation.State.Running

        QTest.qWait(dialog._body_height_animation.duration() + 40)
        app.processEvents()
        assert dialog._report_editor.isHidden()
        collapsed_target_height, _ = dialog._body_height_for(False)
        assert dialog._body_scroll_area.height() == collapsed_target_height
    finally:
        dialog.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.setProperty("substitute.reduce_motion", previous_reduced_motion)
        app.processEvents()


def test_error_report_dialog_footer_excludes_open_console_action() -> None:
    """Footer should only show copy and accent close actions."""

    app = _app()
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.EXECUTION,
            title="KSampler failed",
            message="CUDA out of memory",
            stage="listen",
        ),
        report_text="Traceback",
        open_console=lambda: None,
    )

    try:
        assert not hasattr(dialog, "_console_button")
        assert dialog._copy_button.text() == "Copy report"
        assert isinstance(dialog._close_button, PrimaryPushButton)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_error_report_dialog_copies_complete_report_to_clipboard() -> None:
    """Copy report should place the complete report text on the clipboard."""

    app = _app()
    report_text = "Full report\nTraceback line 1"
    dialog = ErrorReportDialog(
        report=ErrorReport(
            kind=ErrorReportKind.PROMPT_VALIDATION,
            title="Prompt validation failed",
            message="Invalid prompt",
            stage="queue",
        ),
        report_text=report_text,
    )

    try:
        dialog._copy_report()

        assert QApplication.clipboard().text() == report_text
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
