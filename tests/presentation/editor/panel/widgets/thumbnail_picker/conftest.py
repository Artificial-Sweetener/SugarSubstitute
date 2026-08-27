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

"""Provide exact-lifetime thumbnail-picker test ownership."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PySide6.QtWidgets import QApplication

from tests.presentation.editor.panel.widgets.thumbnail_picker.support import (
    ThumbnailPickerOwner,
)


@pytest.fixture
def thumbnail_owner(
    qt_application_owner: QApplication,
) -> Generator[ThumbnailPickerOwner, None, None]:
    """Own every native widget root constructed by one picker test."""

    owner = ThumbnailPickerOwner(qt_application_owner)
    yield owner
    owner.destroy_all()
