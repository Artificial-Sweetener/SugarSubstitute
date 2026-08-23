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

"""Provide exact-lifetime GPL license dialog fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PySide6.QtWidgets import QApplication

from tests.presentation.dialogs.license.support import LicenseDialogOwner


@pytest.fixture
def license_dialog_owner(
    qt_application_owner: QApplication,
) -> Generator[LicenseDialogOwner, None, None]:
    """Own every license dialog and parent constructed by one test."""

    _ = qt_application_owner
    owner = LicenseDialogOwner()
    yield owner
    owner.destroy_all()
