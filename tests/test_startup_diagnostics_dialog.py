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

"""Widget tests for recoverable Comfy startup diagnostics summary dialog."""

from __future__ import annotations

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QWidget
from qfluentwidgets import InfoBarIcon, PushButton, Theme  # type: ignore[import-untyped]

from substitute.application.comfy_startup_diagnostics.summary import (
    render_startup_diagnostics_report,
)
from substitute.domain.comfy_startup_diagnostics import (
    ComfyStartupIncident,
    ComfyStartupIncidentKind,
    ComfyStartupIncidentSeverity,
)
from substitute.presentation.dialogs.startup_diagnostics_dialog import (
    StartupDiagnosticsDialog,
    StartupDiagnosticsGlyphWidget,
)
from tests.theme_switch_test_helpers import fluent_theme, process_events


def _app() -> QApplication:
    """Return a QApplication for widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_startup_diagnostics_dialog_renders_grouped_incidents() -> None:
    """Dialog should summarize recoverable incidents without fatal error styling."""

    app = _app()
    parent = QWidget()
    parent.resize(1024, 768)
    incidents = (_incident("fingerprint-a", "BrokenNode"),)
    report_text = render_startup_diagnostics_report(incidents)
    dialog = StartupDiagnosticsDialog(
        incidents=incidents,
        report_text=report_text,
        parent=parent,
    )

    try:
        assert dialog._title_label.text() == "ComfyUI started with issues"
        assert isinstance(dialog._icon_widget, StartupDiagnosticsGlyphWidget)
        assert "Warning" in dialog._icon_widget.icon_path()
        assert "BrokenNode" in dialog._report_editor.toPlainText()
        label_text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
        assert "Error: Extension failed to load" in label_text
        assert "Python could not parse the extension's source code." in label_text
        assert "BrokenNode • nodes.py:42" in label_text
        assert "Update the extension first." in label_text
        assert "Likely cause:" not in label_text
        assert "Suggested action:" not in label_text
        assert "Open docs" not in label_text
        assert len(_summary_tiles(dialog)) == 3
        assert {"Errors", "Warnings", "Ignored"}.issubset(
            {label.text() for label in dialog.findChildren(QLabel)}
        )
        assert InfoBarIcon.ERROR.path(Theme.LIGHT) in _summary_icon_paths(dialog)
        assert InfoBarIcon.INFORMATION.path(Theme.LIGHT) in _summary_icon_paths(dialog)
        assert _button_texts(dialog) >= {
            "Repository",
            "Report issue",
            "Copy report",
            "Ignore selected",
            "Close",
        }
        assert dialog._close_button.text() == "Close"
        assert dialog._ignore_button.text() == "Ignore selected"
        assert dialog._copy_button.text() == "Copy report"
    finally:
        dialog.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_startup_diagnostics_dialog_omits_links_without_urls() -> None:
    """Incident rows should not show external link buttons without trusted URLs."""

    app = _app()
    dialog = StartupDiagnosticsDialog(
        incidents=(_incident("fingerprint-a", "BrokenNode", include_links=False),),
        report_text="report",
    )

    try:
        assert "Repository" not in _button_texts(dialog)
        assert "Report issue" not in _button_texts(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_startup_diagnostics_dialog_link_buttons_open_urls_without_closing() -> None:
    """Incident link buttons should open URLs without accepting or rejecting."""

    app = _app()
    opened_urls: list[str] = []

    def record_opened_url(url: str) -> bool:
        """Record a URL open request and report success."""

        opened_urls.append(url)
        return True

    dialog = StartupDiagnosticsDialog(
        incidents=(_incident("fingerprint-a", "BrokenNode"),),
        report_text="report",
        url_opener=record_opened_url,
    )

    try:
        for button in dialog.findChildren(PushButton):
            if button.text() == "Repository":
                button.click()
                break

        assert opened_urls == ["https://github.com/example/BrokenNode"]
        assert dialog.result() == 0
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_startup_diagnostics_dialog_returns_selected_ignores() -> None:
    """Checking incident rows should expose selected fingerprints for persistence."""

    app = _app()
    incidents = (
        _incident("fingerprint-a", "BrokenNode"),
        _incident("fingerprint-b", "OtherNode"),
    )
    dialog = StartupDiagnosticsDialog(
        incidents=incidents,
        report_text=render_startup_diagnostics_report(incidents),
    )

    try:
        checkboxes = dialog.findChildren(QCheckBox)
        checkboxes[0].setChecked(True)

        assert dialog.selected_ignored_fingerprints() == frozenset({"fingerprint-a"})
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_startup_diagnostics_dialog_copies_report_to_clipboard() -> None:
    """Copy report should place the full diagnostics text on the clipboard."""

    app = _app()
    report_text = "ComfyUI startup diagnostics\nBrokenNode"
    dialog = StartupDiagnosticsDialog(
        incidents=(_incident("fingerprint-a", "BrokenNode"),),
        report_text=report_text,
    )

    try:
        dialog._copy_report()

        assert QApplication.clipboard().text() == report_text
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_startup_diagnostics_dialog_stays_within_parent_bounds() -> None:
    """Dialog should cap its content height against the owner window."""

    app = _app()
    parent = QWidget()
    parent.resize(720, 420)
    incidents = tuple(
        _incident(f"fingerprint-{index}", f"Node{index}") for index in range(8)
    )
    dialog = StartupDiagnosticsDialog(
        incidents=incidents,
        report_text=render_startup_diagnostics_report(incidents),
        parent=parent,
    )

    try:
        assert dialog.widget.maximumHeight() == 372
    finally:
        dialog.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_startup_diagnostics_summary_tiles_render_for_light_theme() -> None:
    """Light theme should render light summary surfaces with dark foregrounds."""

    with fluent_theme(Theme.LIGHT):
        app = _app()
        parent = QWidget()
        parent.resize(1024, 768)
        parent.show()
        dialog = StartupDiagnosticsDialog(
            incidents=(_incident("fingerprint-a", "BrokenNode"),),
            report_text="report",
            parent=parent,
        )
        dialog.show()
        process_events()

        try:
            tiles = _summary_tiles(dialog)
            assert len(tiles) == 3
            assert _average_widget_lightness(tiles[0]) > 180
            label_styles = {
                label.styleSheet()
                for label in dialog._summary_frame.findChildren(QLabel)
            }
            assert label_styles
            assert all("#000000" in style for style in label_styles)
        finally:
            dialog.close()
            dialog.deleteLater()
            parent.close()
            parent.deleteLater()
            app.processEvents()


def _incident(
    fingerprint: str,
    source: str,
    *,
    include_links: bool = True,
) -> ComfyStartupIncident:
    """Return one deterministic recoverable startup incident."""

    values: dict[str, object] = {"location": "nodes.py:42"}
    if include_links:
        values.update(
            {
                "repository_url": f"https://github.com/example/{source}",
                "issues_url": f"https://github.com/example/{source}/issues",
            }
        )
    return ComfyStartupIncident(
        kind=ComfyStartupIncidentKind.CUSTOM_NODE_IMPORT_FAILED,
        severity=ComfyStartupIncidentSeverity.ERROR,
        title="Extension failed to load",
        message="SyntaxError: broken custom node",
        source=source,
        exception_type="SyntaxError",
        fingerprint=fingerprint,
        log_excerpt=("Cannot import custom node",),
        impact=f"ComfyUI is ready, but {source} did not load.",
        cause="Python could not parse the extension's source code.",
        remediation=(
            "Update the extension first. If it still fails, report it to the maintainer."
        ),
        values=values,
    )


def _button_texts(dialog: StartupDiagnosticsDialog) -> set[str]:
    """Return visible qfluent button texts from the dialog."""

    return {button.text() for button in dialog.findChildren(PushButton)}


def _summary_tiles(dialog: StartupDiagnosticsDialog) -> list[QWidget]:
    """Return rounded summary tiles in the visible dialog header area."""

    return [
        widget
        for widget in dialog.findChildren(QWidget)
        if widget.objectName() == "StartupDiagnosticsSummaryTile"
    ]


def _summary_icon_paths(dialog: StartupDiagnosticsDialog) -> set[str]:
    """Return resource paths for rendered summary tile icons."""

    paths: set[str] = set()
    for widget in dialog.findChildren(QWidget):
        if widget.objectName() != "StartupDiagnosticsSummaryTileIcon":
            continue
        icon_path = getattr(widget, "icon_path", None)
        if callable(icon_path):
            path = icon_path()
            if isinstance(path, str):
                paths.add(path)
    return paths


def _average_widget_lightness(widget: QWidget) -> float:
    """Return sampled average RGB lightness from a rendered widget."""

    image = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    samples = [
        image.pixelColor(x, y).lightnessF()
        for y in range(0, image.height(), 2)
        for x in range(0, image.width(), 2)
    ]
    return (sum(samples) / len(samples)) * 255
