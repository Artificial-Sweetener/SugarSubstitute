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

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel
from qfluentwidgets import PrimaryPushButton, TextBrowser  # type: ignore[import-untyped]

from substitute.application.about import GPL_V3_LICENSE_HTML
from tests.presentation.dialogs.license.support import LicenseDialogOwner


def test_license_dialog_uses_parent_relative_size_and_scrollable_text(
    license_dialog_owner: LicenseDialogOwner,
) -> None:
    """License dialog should prefer bounded width and parent-relative height."""

    dialog = license_dialog_owner.build(
        parent_size=QSize(1000, 800),
        license_html="<p>GPL text line 1 GPL text line 2</p>",
    )

    assert dialog.widget.minimumWidth() == 780
    assert dialog.widget.maximumWidth() == 780
    assert dialog.widget.minimumHeight() == 656
    assert dialog.widget.maximumHeight() == 656
    assert isinstance(dialog._license_browser, TextBrowser)
    assert dialog._license_browser.isReadOnly()
    assert "GPL text line 1 GPL text line 2" in dialog._license_browser.toPlainText()
    assert dialog._license_browser.minimumHeight() == 548
    assert dialog._license_browser.maximumHeight() == 548
    assert isinstance(dialog._close_button, PrimaryPushButton)
    assert dialog._close_button.text() == "Close"
    rendered_labels = {label.text() for label in dialog.findChildren(QLabel)}
    assert "Freedom-focused summary." not in rendered_labels
    assert "GNU General Public License v3" not in rendered_labels


def test_license_dialog_yields_width_under_narrow_parent(
    license_dialog_owner: LicenseDialogOwner,
) -> None:
    """Narrow parents should reduce modal width instead of forcing full width."""

    dialog = license_dialog_owner.build(
        parent_size=QSize(420, 520),
        license_html="<p>GPL text.</p>",
    )

    assert dialog.widget.minimumWidth() == 388
    assert dialog.widget.maximumWidth() == 388
    assert dialog.widget.minimumHeight() == 426
    assert dialog.widget.maximumHeight() == 426


def test_license_dialog_renders_official_html_without_plain_text_hard_wraps(
    license_dialog_owner: LicenseDialogOwner,
) -> None:
    """Bundled GPL HTML should render paragraphs without plain-text line wrapping."""

    dialog = license_dialog_owner.build(
        parent_size=QSize(900, 700),
        license_html=GPL_V3_LICENSE_HTML,
    )

    rendered_text = dialog._license_browser.toPlainText()
    assert (
        "The GNU General Public License is a free, copyleft license for "
        "software and other kinds of works."
    ) in rendered_text
    assert (
        "The GNU General Public License is a free, copyleft license for\n"
        "software and other kinds of works."
    ) not in rendered_text
