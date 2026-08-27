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

"""Provide exact-lifetime wheel-intent test ownership."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PySide6.QtWidgets import QApplication

from tests.presentation.widgets.wheel_intent.support import WheelIntentOwner


@pytest.fixture
def wheel_owner(
    qt_application_owner: QApplication,
) -> Generator[WheelIntentOwner, None, None]:
    """Own every controller and widget constructed by one wheel test."""

    owner = WheelIntentOwner(qt_application_owner)
    yield owner
    owner.destroy_all()
