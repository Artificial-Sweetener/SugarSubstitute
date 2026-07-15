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

"""Widget tests for the About GPLv3 license dialog."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from qfluentwidgets import PrimaryPushButton, TextBrowser  # type: ignore[import-untyped]

from substitute.application.about import GPL_V3_LICENSE_HTML
from substitute.presentation.dialogs.license_dialog import LicenseDialog

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "License dialog Qt tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_license_dialog_uses_parent_relative_size_and_scrollable_text() -> None:
    """License dialog should prefer bounded width and parent-relative height."""

    app = _app()
    parent = QWidget()
    parent.resize(1000, 800)
    dialog = LicenseDialog(
        license_html="<p>GPL text line 1 GPL text line 2</p>",
        parent=parent,
    )

    try:
        assert dialog.widget.minimumWidth() == 780
        assert dialog.widget.maximumWidth() == 780
        assert dialog.widget.minimumHeight() == 656
        assert dialog.widget.maximumHeight() == 656
        assert isinstance(dialog._license_browser, TextBrowser)
        assert dialog._license_browser.isReadOnly()
        assert "GPL text line 1 GPL text line 2" in (
            dialog._license_browser.toPlainText()
        )
        assert dialog._license_browser.minimumHeight() == 548
        assert dialog._license_browser.maximumHeight() == 548
        assert isinstance(dialog._close_button, PrimaryPushButton)
        assert dialog._close_button.text() == "Close"
        rendered_labels = {label.text() for label in dialog.findChildren(QLabel)}
        assert "Freedom-focused summary." not in rendered_labels
        assert "GNU General Public License v3" not in rendered_labels
    finally:
        dialog.close()
        parent.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_license_dialog_yields_width_under_narrow_parent() -> None:
    """Narrow parents should reduce modal width instead of forcing full width."""

    app = _app()
    parent = QWidget()
    parent.resize(420, 520)
    dialog = LicenseDialog(
        license_html="<p>GPL text.</p>",
        parent=parent,
    )

    try:
        assert dialog.widget.minimumWidth() == 388
        assert dialog.widget.maximumWidth() == 388
        assert dialog.widget.minimumHeight() == 426
        assert dialog.widget.maximumHeight() == 426
    finally:
        dialog.close()
        parent.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_license_dialog_renders_official_html_without_plain_text_hard_wraps() -> None:
    """Bundled GPL HTML should render paragraphs without plain-text line wrapping."""

    app = _app()
    parent = QWidget()
    parent.resize(900, 700)
    dialog = LicenseDialog(
        license_html=GPL_V3_LICENSE_HTML,
        parent=parent,
    )

    try:
        rendered_text = dialog._license_browser.toPlainText()
        assert (
            "The GNU General Public License is a free, copyleft license for "
            "software and other kinds of works."
        ) in rendered_text
        assert (
            "The GNU General Public License is a free, copyleft license for\n"
            "software and other kinds of works."
        ) not in rendered_text
    finally:
        dialog.close()
        parent.close()
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])
