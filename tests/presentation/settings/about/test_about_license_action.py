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

"""Verify the About page license action at the modal boundary."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QAbstractButton, QWidget

from substitute.application.about import GPL_V3_LICENSE_HTML
from tests.presentation.settings.about.about_settings_harness import (
    AboutInfoServiceDouble,
    AboutPageFactory,
    application,
    bind_refreshed_snapshot,
)


def test_about_license_button_opens_gpl_modal(
    monkeypatch: pytest.MonkeyPatch,
    about_page_factory: AboutPageFactory,
) -> None:
    """Open a modal containing the application GPLv3 license text."""

    opened_dialogs: list[_RecordedLicenseDialog] = []

    class RecordedLicenseDialog(_RecordedLicenseDialog):
        """Record license dialog construction for this interaction."""

        def __init__(
            self,
            *,
            license_html: str,
            parent: QWidget | None = None,
        ) -> None:
            """Store dialog arguments and publish the created instance."""

            super().__init__(license_html=license_html, parent=parent)
            opened_dialogs.append(self)

    monkeypatch.setattr(
        "substitute.presentation.settings.about_page.LicenseDialog",
        RecordedLicenseDialog,
    )
    service = AboutInfoServiceDouble()
    page = about_page_factory(service, None)
    bind_refreshed_snapshot(page, service)
    button = page.findChild(QAbstractButton, "AboutReadLicenseButton")
    assert button is not None

    button.click()
    application().processEvents()

    assert len(opened_dialogs) == 1
    assert opened_dialogs[0].license_html == GPL_V3_LICENSE_HTML
    assert opened_dialogs[0].exec_calls == 1


class _RecordedLicenseDialog:
    """Record license dialog construction and execution."""

    def __init__(
        self,
        *,
        license_html: str,
        parent: QWidget | None = None,
    ) -> None:
        """Store dialog construction arguments."""

        self.license_html = license_html
        self.parent = parent
        self.exec_calls = 0

    def exec(self) -> int:
        """Record a modal execution request."""

        self.exec_calls += 1
        return 0
